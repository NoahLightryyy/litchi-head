"""Direct Eastmoney and Sina realtime quote evidence adapters."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import StockQuote

logger = logging.getLogger(__name__)

SHANGHAI = ZoneInfo("Asia/Shanghai")
QUOTE_TIMEOUT_SECONDS = 5.0
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
SINA_QUOTE_URL = "https://hq.sinajs.cn/list={symbol}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


class EastmoneyQuoteFetcher(Protocol):
    def __call__(self, code: str) -> Mapping[str, Any]:
        """Return one raw Eastmoney quote response."""
        ...


class SinaQuoteFetcher(Protocol):
    def __call__(self, code: str) -> str:
        """Return one raw Sina quote row."""
        ...


class _UpstreamRequestError(RuntimeError):
    """Distinguish transport failures from invalid upstream payloads."""


def _market_prefix(code: str) -> str:
    return "sh" if code.startswith(("5", "6", "9")) else "sz"


def _eastmoney_secid(code: str) -> str:
    market = "1" if _market_prefix(code) == "sh" else "0"
    return f"{market}.{code}"


def _default_eastmoney_fetcher(code: str) -> Mapping[str, Any]:
    import httpx

    response = httpx.get(
        EASTMONEY_QUOTE_URL,
        params={
            "secid": _eastmoney_secid(code),
            "fields": "f57,f58,f43,f44,f45,f46,f47,f48,f60,f86,f169,f170",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=QUOTE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Eastmoney response must be a JSON object")
    return payload


def _default_sina_fetcher(code: str) -> str:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    response = httpx.get(
        SINA_QUOTE_URL.format(symbol=symbol),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://finance.sina.com.cn/",
        },
        timeout=QUOTE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content.decode("gb18030")


def _number(value: object, field: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} is not numeric")
    text = str(value).strip()
    if not text or text == "-":
        raise ValueError(f"{field} is not numeric")
    return float(text)


def _integer(value: object, field: str) -> int:
    number = _number(value, field)
    if number < 0 or not number.is_integer():
        raise ValueError(f"{field} must be a non-negative integer")
    return int(number)


def _failed_result(
    descriptor: SourceDescriptor,
    *,
    error_code: str,
    exc: Exception,
) -> SourceResult[StockQuote]:
    return SourceResult(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.FAILED,
        error_code=error_code,
        error_message=str(exc).strip() or exc.__class__.__name__,
    )


class EastmoneyQuoteSource:
    """Direct single-symbol Eastmoney quote adapter."""

    descriptor = SourceDescriptor(
        source_id="direct-eastmoney-quote",
        upstream_id="eastmoney",
        display_name="东方财富实时行情直连",
        capabilities={EvidenceCapability.REALTIME_QUOTE},
    )

    def __init__(
        self,
        *,
        fetcher: EastmoneyQuoteFetcher = _default_eastmoney_fetcher,
    ) -> None:
        self._fetcher = fetcher

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]:
        if request.capability is not EvidenceCapability.REALTIME_QUOTE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        try:
            try:
                payload = self._fetcher(request.stock_code)
            except Exception as exc:
                raise _UpstreamRequestError(
                    str(exc).strip() or exc.__class__.__name__
                ) from exc
            data = payload.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Eastmoney response is missing data")

            code = str(data.get("f57", "")).strip()
            name = str(data.get("f58", "")).strip()
            if code != request.stock_code or not name:
                raise ValueError("Eastmoney quote identity does not match request")

            quote = StockQuote(
                code=code,
                name=name,
                price=_number(data.get("f43"), "f43") / 100,
                high=_number(data.get("f44"), "f44") / 100,
                low=_number(data.get("f45"), "f45") / 100,
                open_=_number(data.get("f46"), "f46") / 100,
                volume=_integer(data.get("f47"), "f47") * 100,
                amount=_number(data.get("f48"), "f48"),
                prev_close=_number(data.get("f60"), "f60") / 100,
                fetched_at=datetime.fromtimestamp(
                    _integer(data.get("f86"), "f86"),
                    tz=SHANGHAI,
                ),
                change=_number(data.get("f169"), "f169") / 100,
                change_pct=_number(data.get("f170"), "f170") / 100,
            )
        except _UpstreamRequestError as exc:
            logger.warning("Eastmoney quote request failed: %s", exc)
            return _failed_result(
                self.descriptor,
                error_code="upstream_request_failed",
                exc=exc,
            )
        except Exception as exc:
            logger.exception("Eastmoney quote payload is invalid")
            return _failed_result(
                self.descriptor,
                error_code="invalid_upstream_payload",
                exc=exc,
            )

        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[quote],
        )


def _sina_fields(raw: str) -> list[str]:
    text = raw.strip()
    if '="' in text:
        text = text.split('="', 1)[1].rsplit('"', 1)[0]
    fields = text.split(",")
    if len(fields) < 33:
        raise ValueError("Sina quote row has fewer than 33 fields")
    return fields


class SinaQuoteSource:
    """Direct single-symbol Sina quote adapter."""

    descriptor = SourceDescriptor(
        source_id="direct-sina-quote",
        upstream_id="sina",
        display_name="新浪实时行情直连",
        capabilities={EvidenceCapability.REALTIME_QUOTE},
    )

    def __init__(
        self,
        *,
        fetcher: SinaQuoteFetcher = _default_sina_fetcher,
    ) -> None:
        self._fetcher = fetcher

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]:
        if request.capability is not EvidenceCapability.REALTIME_QUOTE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )

        try:
            try:
                raw = self._fetcher(request.stock_code)
            except Exception as exc:
                raise _UpstreamRequestError(
                    str(exc).strip() or exc.__class__.__name__
                ) from exc
            fields = _sina_fields(raw)
            name = fields[0].strip()
            if not name:
                raise ValueError("Sina quote identity is empty")
            quote_at = datetime.fromisoformat(
                f"{fields[30].strip()}T{fields[31].strip()}"
            ).replace(tzinfo=SHANGHAI)
            price = _number(fields[3], "current")
            prev_close = _number(fields[2], "prev_close")
            change = price - prev_close
            change_pct = change / prev_close * 100 if prev_close else 0.0

            quote = StockQuote(
                code=request.stock_code,
                name=name,
                price=price,
                high=_number(fields[4], "high"),
                low=_number(fields[5], "low"),
                open_=_number(fields[1], "open"),
                volume=_integer(fields[8], "volume"),
                amount=_number(fields[9], "amount"),
                prev_close=prev_close,
                fetched_at=quote_at,
                change=change,
                change_pct=change_pct,
            )
        except _UpstreamRequestError as exc:
            logger.warning("Sina quote request failed: %s", exc)
            return _failed_result(
                self.descriptor,
                error_code="upstream_request_failed",
                exc=exc,
            )
        except Exception as exc:
            logger.exception("Sina quote payload is invalid")
            return _failed_result(
                self.descriptor,
                error_code="invalid_upstream_payload",
                exc=exc,
            )

        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[quote],
        )


__all__ = [
    "EastmoneyQuoteSource",
    "SinaQuoteSource",
]

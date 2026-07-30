"""Direct Sina and Tencent RAW completed daily K-line adapters."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.kline import MarketCode, RawDailyBar, market_code_for
from src.data.providers.quotes import USER_AGENT, _market_prefix

logger = logging.getLogger(__name__)

SHANGHAI = ZoneInfo("Asia/Shanghai")
KLINE_TIMEOUT_SECONDS = 8.0
SINA_RAW_DAILY_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
    "var%20_{symbol}_240_{datalen}=/CN_MarketDataService.getKLineData"
)
TENCENT_RAW_DAILY_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


class SinaDailyFetcher(Protocol):
    def __call__(self, code: str, start: date, end: date) -> str:
        """Return one Sina unadjusted daily response."""
        ...


class TencentDailyFetcher(Protocol):
    def __call__(
        self,
        code: str,
        start: date,
        end: date,
    ) -> Mapping[str, Any]:
        """Return one Tencent unadjusted daily response."""
        ...


class _UpstreamRequestError(RuntimeError):
    """Distinguish transport failures from invalid successful payloads."""


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def _request_dates(request: EvidenceRequest) -> tuple[date, date]:
    if request.start_at is None or request.end_at is None:
        raise ValueError("RAW daily K-line request requires start_at and end_at")
    start = request.start_at.date()
    end = request.end_at.date()
    if start > end:
        raise ValueError("RAW daily K-line start date must not exceed end date")
    return start, end


def _aware_local_now(now_provider: Callable[[], datetime]) -> datetime:
    now = now_provider()
    if now.tzinfo is None:
        raise ValueError("now_provider must return a timezone-aware datetime")
    return now.astimezone(SHANGHAI)


def _decimal(value: object, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} is not numeric")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} is not numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{field} is not finite")
    return number


def _integer(value: object, field: str) -> int:
    number = _decimal(value, field)
    if number < 0 or number != number.to_integral_value():
        raise ValueError(f"{field} must be a non-negative integer")
    return int(number)


def _completed_in_window(
    trade_date: date,
    *,
    start: date,
    end: date,
    now: datetime,
) -> bool:
    # KR-1 deliberately excludes the current session. Same-day promotion needs
    # the stable multi-poll state machine planned for KR-3.
    return start <= trade_date <= end and trade_date < now.date()


def _default_sina_fetcher(code: str, start: date, end: date) -> str:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    calendar_days = (end - start).days + 1
    datalen = min(max(calendar_days * 2 + 10, 20), 1023)
    response = httpx.get(
        SINA_RAW_DAILY_URL.format(symbol=symbol, datalen=datalen),
        params={
            "symbol": symbol,
            "scale": "240",
            "ma": "no",
            "datalen": str(datalen),
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://finance.sina.com.cn/",
        },
        timeout=KLINE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def _default_tencent_fetcher(
    code: str,
    start: date,
    end: date,
) -> Mapping[str, Any]:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    count = min(max((end - start).days + 10, 20), 1023)
    response = httpx.get(
        TENCENT_RAW_DAILY_URL,
        params={
            # The trailing empty adjustment field requests the raw ``day`` key.
            "param": (
                f"{symbol},day,{start.isoformat()},{end.isoformat()},{count},"
            )
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://gu.qq.com/",
        },
        timeout=KLINE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Tencent RAW daily response must be an object")
    return payload


def _failed(
    descriptor: SourceDescriptor,
    exc: Exception,
    *,
    error_code: str,
) -> SourceResult[RawDailyBar]:
    return SourceResult(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        capability=EvidenceCapability.KLINE,
        status=SourceStatus.FAILED,
        error_code=error_code,
        error_message=str(exc).strip() or exc.__class__.__name__,
    )


def _success(
    descriptor: SourceDescriptor,
    bars: list[RawDailyBar],
) -> SourceResult[RawDailyBar]:
    return SourceResult(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        capability=EvidenceCapability.KLINE,
        status=(
            SourceStatus.SUCCESS_DATA if bars else SourceStatus.SUCCESS_EMPTY
        ),
        items=bars,
    )


class SinaRawDailyKlineSource:
    """Direct Sina RAW daily bars with share-granular volume."""

    descriptor = SourceDescriptor(
        source_id="direct-sina-raw-daily",
        upstream_id="sina",
        display_name="新浪 RAW 日线直连",
        capabilities={EvidenceCapability.KLINE},
    )

    def __init__(
        self,
        *,
        fetcher: SinaDailyFetcher = _default_sina_fetcher,
        now_provider: Callable[[], datetime] = _now_shanghai,
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider

    def fetch(self, request: EvidenceRequest) -> SourceResult[RawDailyBar]:
        if request.capability is not EvidenceCapability.KLINE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        try:
            start, end = _request_dates(request)
            try:
                raw = self._fetcher(request.stock_code, start, end)
            except Exception as exc:
                raise _UpstreamRequestError(
                    str(exc).strip() or exc.__class__.__name__
                ) from exc
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            match = re.search(
                r"var\s+_([a-z]{2}\d{6})_\d+_\d+\s*=\s*\((\[.*?\])\);",
                raw,
                flags=re.DOTALL,
            )
            if match is None:
                raise ValueError("Sina RAW daily response wrapper is invalid")
            if match.group(1) != symbol:
                raise ValueError("Sina RAW daily identity does not match request")
            payload = json.loads(match.group(2))
            if not isinstance(payload, list):
                raise ValueError("Sina RAW daily payload must be a list")

            now = _aware_local_now(self._now_provider)
            bars: list[RawDailyBar] = []
            for row in payload:
                if not isinstance(row, Mapping):
                    raise ValueError("Sina RAW daily row must be an object")
                trade_date = date.fromisoformat(str(row.get("day", "")).strip())
                if not _completed_in_window(
                    trade_date,
                    start=start,
                    end=end,
                    now=now,
                ):
                    continue
                bars.append(
                    RawDailyBar(
                        code=request.stock_code,
                        market=market_code_for(request.stock_code),
                        trade_date=trade_date,
                        open=_decimal(row.get("open"), "open"),
                        high=_decimal(row.get("high"), "high"),
                        low=_decimal(row.get("low"), "low"),
                        close=_decimal(row.get("close"), "close"),
                        volume=_integer(row.get("volume"), "volume"),
                        volume_precision=1,
                    )
                )
        except _UpstreamRequestError as exc:
            logger.warning("Sina RAW daily request failed: %s", exc)
            return _failed(
                self.descriptor,
                exc,
                error_code="upstream_request_failed",
            )
        except Exception as exc:
            logger.exception("Sina RAW daily payload is invalid")
            return _failed(
                self.descriptor,
                exc,
                error_code="invalid_upstream_payload",
            )
        return _success(self.descriptor, bars)


class TencentRawDailyKlineSource:
    """Direct Tencent RAW daily bars with whole-lot volume precision."""

    descriptor = SourceDescriptor(
        source_id="direct-tencent-raw-daily",
        upstream_id="tencent",
        display_name="腾讯 RAW 日线直连",
        capabilities={EvidenceCapability.KLINE},
    )

    def __init__(
        self,
        *,
        fetcher: TencentDailyFetcher = _default_tencent_fetcher,
        now_provider: Callable[[], datetime] = _now_shanghai,
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider

    def fetch(self, request: EvidenceRequest) -> SourceResult[RawDailyBar]:
        if request.capability is not EvidenceCapability.KLINE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        if market_code_for(request.stock_code) is MarketCode.BSE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=EvidenceCapability.KLINE,
                status=SourceStatus.UNSUPPORTED,
                error_code="independent_upstream_missing",
                error_message="Tencent RAW historical daily bars are unavailable for BSE",
            )
        try:
            start, end = _request_dates(request)
            try:
                payload = self._fetcher(request.stock_code, start, end)
            except Exception as exc:
                raise _UpstreamRequestError(
                    str(exc).strip() or exc.__class__.__name__
                ) from exc
            if payload.get("code") != 0:
                raise ValueError("Tencent RAW daily response code is not zero")
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            data = payload.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Tencent RAW daily response is missing data")
            symbol_data = data.get(symbol)
            if not isinstance(symbol_data, Mapping):
                raise ValueError("Tencent RAW daily identity does not match request")
            raw_rows = symbol_data.get("day")
            if not isinstance(raw_rows, list):
                raise ValueError("Tencent RAW daily rows are missing")

            now = _aware_local_now(self._now_provider)
            bars: list[RawDailyBar] = []
            for row in raw_rows:
                if not isinstance(row, list) or len(row) < 6:
                    raise ValueError("Tencent RAW daily row has fewer than 6 fields")
                trade_date = date.fromisoformat(str(row[0]).strip())
                if not _completed_in_window(
                    trade_date,
                    start=start,
                    end=end,
                    now=now,
                ):
                    continue
                volume = _decimal(row[5], "volume_lots") * 100
                if volume != volume.to_integral_value() or volume < 0:
                    raise ValueError(
                        "Tencent RAW daily volume must normalize to whole shares"
                    )
                bars.append(
                    RawDailyBar(
                        code=request.stock_code,
                        market=market_code_for(request.stock_code),
                        trade_date=trade_date,
                        open=_decimal(row[1], "open"),
                        close=_decimal(row[2], "close"),
                        high=_decimal(row[3], "high"),
                        low=_decimal(row[4], "low"),
                        volume=int(volume),
                        volume_precision=100,
                    )
                )
        except _UpstreamRequestError as exc:
            logger.warning("Tencent RAW daily request failed: %s", exc)
            return _failed(
                self.descriptor,
                exc,
                error_code="upstream_request_failed",
            )
        except Exception as exc:
            logger.exception("Tencent RAW daily payload is invalid")
            return _failed(
                self.descriptor,
                exc,
                error_code="invalid_upstream_payload",
            )
        return _success(self.descriptor, bars)


__all__ = [
    "SinaRawDailyKlineSource",
    "TencentRawDailyKlineSource",
]

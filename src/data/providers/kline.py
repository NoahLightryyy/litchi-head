"""Direct Sina and Tencent RAW completed daily K-line adapters."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
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
from src.data.kline_store import KlineQueryChunkProof, KlineSourceAudit
from src.data.providers.quotes import USER_AGENT, _market_prefix

logger = logging.getLogger(__name__)

SHANGHAI = ZoneInfo("Asia/Shanghai")
KLINE_TIMEOUT_SECONDS = 8.0
SINA_RAW_DAILY_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
    "var%20_{symbol}_240_{datalen}=/CN_MarketDataService.getKLineData"
)
TENCENT_RAW_DAILY_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SINA_ADAPTER_VERSION = "sina-raw-daily-v2"
TENCENT_ADAPTER_VERSION = "tencent-raw-daily-v2"
TENCENT_QUERY_CALENDAR_DAYS = 1000


class SinaDailyFetcher(Protocol):
    def __call__(
        self,
        code: str,
        start: date,
        end: date,
    ) -> str | bytes:
        """Return one Sina unadjusted daily response."""
        ...


class TencentDailyFetcher(Protocol):
    def __call__(
        self,
        code: str,
        start: date,
        end: date,
    ) -> Mapping[str, Any] | bytes:
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


def _default_sina_fetcher(
    code: str,
    start: date,
    end: date,
) -> bytes:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    datalen = _sina_datalen(start, end)
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
    return response.content


def _default_tencent_fetcher(
    code: str,
    start: date,
    end: date,
) -> bytes:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    count = min(max((end - start).days + 10, 20), 1023)
    response = httpx.get(
        TENCENT_RAW_DAILY_URL,
        params={
            # The trailing empty adjustment field requests the raw ``day`` key.
            "param": (f"{symbol},day,{start.isoformat()},{end.isoformat()},{count},")
        },
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://gu.qq.com/",
        },
        timeout=KLINE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _sina_datalen(start: date, end: date) -> int:
    calendar_days = (end - start).days + 1
    return min(max(calendar_days * 2 + 10, 20), 1023)


def _canonical_response(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sina_response(response: str | bytes) -> tuple[str, bytes]:
    if isinstance(response, bytes):
        return response.decode("utf-8"), response
    return response, response.encode("utf-8")


def _tencent_response(
    response: Mapping[str, Any] | bytes,
) -> tuple[Mapping[str, Any], bytes]:
    if isinstance(response, bytes):
        payload = json.loads(response)
        if not isinstance(payload, Mapping):
            raise ValueError("Tencent RAW daily response must be an object")
        return payload, response
    return response, _canonical_response(response)


def _response_proof(
    *,
    start: date,
    end: date,
    fetched_at: datetime,
    response: bytes,
    row_count: int,
    complete: bool,
) -> KlineQueryChunkProof:
    return KlineQueryChunkProof(
        query_start=start,
        query_end=end,
        fetched_at=fetched_at,
        response_hash=hashlib.sha256(response).hexdigest(),
        response_bytes=len(response),
        row_count=row_count,
        complete=complete,
    )


def _audit_result(
    descriptor: SourceDescriptor,
    *,
    adapter_version: str,
    status: SourceStatus,
    fetched_at: datetime,
    bars: list[RawDailyBar] | None = None,
    chunks: list[KlineQueryChunkProof] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> KlineSourceAudit:
    return KlineSourceAudit(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        adapter_version=adapter_version,
        status=status,
        fetched_at=fetched_at,
        raw_bars=tuple(bars or ()),
        query_chunks=tuple(chunks or ()),
        error_code=error_code,
        error_message=error_message,
    )


def _source_result_from_audit(
    descriptor: SourceDescriptor,
    audit: KlineSourceAudit,
) -> SourceResult[RawDailyBar]:
    return SourceResult(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        capability=EvidenceCapability.KLINE,
        status=audit.status,
        items=(list(audit.raw_bars) if audit.status is SourceStatus.SUCCESS_DATA else []),
        fetched_at=audit.fetched_at,
        error_code=audit.error_code,
        error_message=audit.error_message,
    )


def _sina_payload(
    raw: str,
    *,
    expected_symbol: str,
) -> list[Mapping[str, Any]]:
    match = re.search(
        r"var\s+_([a-z]{2}\d{6})_\d+_\d+\s*=\s*\((\[.*?\])\);",
        raw,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Sina RAW daily response wrapper is invalid")
    if match.group(1) != expected_symbol:
        raise ValueError("Sina RAW daily identity does not match request")
    payload = json.loads(match.group(2))
    if not isinstance(payload, list):
        raise ValueError("Sina RAW daily payload must be a list")
    if any(not isinstance(row, Mapping) for row in payload):
        raise ValueError("Sina RAW daily row must be an object")
    return payload


def _sina_bars(
    rows: list[Mapping[str, Any]],
    *,
    code: str,
    start: date,
    end: date,
    now: datetime,
) -> tuple[list[RawDailyBar], list[date]]:
    bars: list[RawDailyBar] = []
    raw_dates: list[date] = []
    for row in rows:
        trade_date = date.fromisoformat(str(row.get("day", "")).strip())
        raw_dates.append(trade_date)
        if not _completed_in_window(
            trade_date,
            start=start,
            end=end,
            now=now,
        ):
            continue
        bars.append(
            RawDailyBar(
                code=code,
                market=market_code_for(code),
                trade_date=trade_date,
                open=_decimal(row.get("open"), "open"),
                high=_decimal(row.get("high"), "high"),
                low=_decimal(row.get("low"), "low"),
                close=_decimal(row.get("close"), "close"),
                volume=_integer(row.get("volume"), "volume"),
                volume_precision=1,
            )
        )
    return bars, raw_dates


def _tencent_rows(
    payload: Mapping[str, Any],
    *,
    expected_symbol: str,
) -> list[list[Any]]:
    if payload.get("code") != 0:
        raise ValueError("Tencent RAW daily response code is not zero")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("Tencent RAW daily response is missing data")
    symbol_data = data.get(expected_symbol)
    if not isinstance(symbol_data, Mapping):
        raise ValueError("Tencent RAW daily identity does not match request")
    raw_rows = symbol_data.get("day")
    if not isinstance(raw_rows, list):
        raise ValueError("Tencent RAW daily rows are missing")
    if any(not isinstance(row, list) or len(row) < 6 for row in raw_rows):
        raise ValueError("Tencent RAW daily row has fewer than 6 fields")
    return raw_rows


def _tencent_bar(
    row: list[Any],
    *,
    code: str,
    trade_date: date,
) -> RawDailyBar:
    volume = _decimal(row[5], "volume_lots") * 100
    if volume != volume.to_integral_value() or volume < 0:
        raise ValueError("Tencent RAW daily volume must normalize to whole shares")
    return RawDailyBar(
        code=code,
        market=market_code_for(code),
        trade_date=trade_date,
        open=_decimal(row[1], "open"),
        close=_decimal(row[2], "close"),
        high=_decimal(row[3], "high"),
        low=_decimal(row[4], "low"),
        volume=int(volume),
        volume_precision=100,
    )


class SinaRawDailyKlineSource:
    """Direct Sina RAW daily bars with share-granular volume."""

    adapter_version = SINA_ADAPTER_VERSION
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
        return _source_result_from_audit(
            self.descriptor,
            self.fetch_audited(request),
        )

    def fetch_audited(self, request: EvidenceRequest) -> KlineSourceAudit:
        """Fetch once and prove whether Sina covered the requested window."""

        if request.capability is not EvidenceCapability.KLINE:
            raise ValueError("audited Sina K-line fetch requires KLINE capability")
        chunks: list[KlineQueryChunkProof] = []
        raw_bytes: bytes | None = None
        rows: list[Mapping[str, Any]] = []
        fetched_at = datetime.now(UTC)
        try:
            start, end = _request_dates(request)
            try:
                response = self._fetcher(request.stock_code, start, end)
            except Exception as exc:
                fetched_at = _aware_local_now(self._now_provider)
                raise _UpstreamRequestError(str(exc).strip() or exc.__class__.__name__) from exc
            fetched_at = _aware_local_now(self._now_provider)
            if isinstance(response, bytes):
                raw_bytes = response
            raw, raw_bytes = _sina_response(response)
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            rows = _sina_payload(raw, expected_symbol=symbol)
            bars, raw_dates = _sina_bars(
                rows,
                code=request.stock_code,
                start=start,
                end=end,
                now=fetched_at,
            )
            complete = bool(raw_dates) and min(raw_dates) <= start
            chunks.append(
                _response_proof(
                    start=start,
                    end=end,
                    fetched_at=fetched_at,
                    response=raw_bytes,
                    row_count=len(rows),
                    complete=complete,
                )
            )
            if not complete:
                return _audit_result(
                    self.descriptor,
                    adapter_version=SINA_ADAPTER_VERSION,
                    status=SourceStatus.STALE,
                    fetched_at=fetched_at,
                    bars=bars,
                    chunks=chunks,
                    error_code="kline_source_window_not_covered",
                    error_message=(
                        "Sina returned a capped recent tail that does not prove "
                        "coverage of the requested start date"
                    ),
                )
        except _UpstreamRequestError as exc:
            logger.warning("Sina RAW daily request failed: %s", exc)
            return _audit_result(
                self.descriptor,
                adapter_version=SINA_ADAPTER_VERSION,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                error_code="upstream_request_failed",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        except Exception as exc:
            logger.exception("Sina RAW daily payload is invalid")
            if raw_bytes is not None:
                chunks.append(
                    _response_proof(
                        start=start,
                        end=end,
                        fetched_at=fetched_at,
                        response=raw_bytes,
                        row_count=len(rows),
                        complete=False,
                    )
                )
            return _audit_result(
                self.descriptor,
                adapter_version=SINA_ADAPTER_VERSION,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                chunks=chunks,
                error_code="invalid_upstream_payload",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        return _audit_result(
            self.descriptor,
            adapter_version=SINA_ADAPTER_VERSION,
            status=(SourceStatus.SUCCESS_DATA if bars else SourceStatus.SUCCESS_EMPTY),
            fetched_at=fetched_at,
            bars=bars,
            chunks=chunks,
        )


class TencentRawDailyKlineSource:
    """Direct Tencent RAW daily bars with whole-lot volume precision."""

    adapter_version = TENCENT_ADAPTER_VERSION
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
        return _source_result_from_audit(
            self.descriptor,
            self.fetch_audited(request),
        )

    def fetch_audited(self, request: EvidenceRequest) -> KlineSourceAudit:
        """Fetch deterministic bounded chunks and prove each response."""

        if request.capability is not EvidenceCapability.KLINE:
            raise ValueError("audited Tencent K-line fetch requires KLINE capability")
        if market_code_for(request.stock_code) is MarketCode.BSE:
            return _audit_result(
                self.descriptor,
                adapter_version=TENCENT_ADAPTER_VERSION,
                status=SourceStatus.UNSUPPORTED,
                fetched_at=_aware_local_now(self._now_provider),
                error_code="independent_upstream_missing",
                error_message=("Tencent RAW historical daily bars are unavailable for BSE"),
            )
        chunks: list[KlineQueryChunkProof] = []
        bars_by_date: dict[date, RawDailyBar] = {}
        chunk_start: date | None = None
        chunk_end: date | None = None
        fetched_at = datetime.now(UTC)
        current_response_bytes: bytes | None = None
        current_raw_rows: list[list[Any]] = []
        try:
            start, end = _request_dates(request)
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            chunk_start = start
            while chunk_start <= end:
                chunk_end = min(
                    chunk_start + timedelta(days=TENCENT_QUERY_CALENDAR_DAYS - 1),
                    end,
                )
                current_response_bytes = None
                current_raw_rows = []
                try:
                    response = self._fetcher(
                        request.stock_code,
                        chunk_start,
                        chunk_end,
                    )
                except Exception as exc:
                    fetched_at = _aware_local_now(self._now_provider)
                    raise _UpstreamRequestError(str(exc).strip() or exc.__class__.__name__) from exc
                fetched_at = _aware_local_now(self._now_provider)
                if isinstance(response, bytes):
                    current_response_bytes = response
                payload, current_response_bytes = _tencent_response(response)
                current_raw_rows = _tencent_rows(
                    payload,
                    expected_symbol=symbol,
                )
                seen_in_chunk: set[date] = set()
                for row in current_raw_rows:
                    trade_date = date.fromisoformat(str(row[0]).strip())
                    if not chunk_start <= trade_date <= chunk_end:
                        raise ValueError("Tencent RAW daily row is outside its query chunk")
                    if trade_date in seen_in_chunk or trade_date in bars_by_date:
                        raise ValueError("Tencent RAW daily response has duplicate trade date")
                    seen_in_chunk.add(trade_date)
                    if not _completed_in_window(
                        trade_date,
                        start=start,
                        end=end,
                        now=fetched_at,
                    ):
                        continue
                    bars_by_date[trade_date] = _tencent_bar(
                        row,
                        code=request.stock_code,
                        trade_date=trade_date,
                    )
                chunks.append(
                    _response_proof(
                        start=chunk_start,
                        end=chunk_end,
                        fetched_at=fetched_at,
                        response=current_response_bytes,
                        row_count=len(current_raw_rows),
                        complete=True,
                    )
                )
                chunk_start = chunk_end + timedelta(days=1)
        except _UpstreamRequestError as exc:
            logger.warning("Tencent RAW daily request failed: %s", exc)
            return _audit_result(
                self.descriptor,
                adapter_version=TENCENT_ADAPTER_VERSION,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                bars=[bars_by_date[trade_date] for trade_date in sorted(bars_by_date)],
                chunks=chunks,
                error_code="upstream_request_failed",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        except Exception as exc:
            logger.exception("Tencent RAW daily payload is invalid")
            if (
                current_response_bytes is not None
                and chunk_start is not None
                and chunk_end is not None
            ):
                chunks.append(
                    _response_proof(
                        start=chunk_start,
                        end=chunk_end,
                        fetched_at=fetched_at,
                        response=current_response_bytes,
                        row_count=len(current_raw_rows),
                        complete=False,
                    )
                )
            return _audit_result(
                self.descriptor,
                adapter_version=TENCENT_ADAPTER_VERSION,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                bars=[bars_by_date[trade_date] for trade_date in sorted(bars_by_date)],
                chunks=chunks,
                error_code="invalid_upstream_payload",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        bars = [bars_by_date[trade_date] for trade_date in sorted(bars_by_date)]
        return _audit_result(
            self.descriptor,
            adapter_version=TENCENT_ADAPTER_VERSION,
            status=(SourceStatus.SUCCESS_DATA if bars else SourceStatus.SUCCESS_EMPTY),
            fetched_at=fetched_at,
            bars=bars,
            chunks=chunks,
        )


__all__ = [
    "SinaRawDailyKlineSource",
    "TencentRawDailyKlineSource",
]

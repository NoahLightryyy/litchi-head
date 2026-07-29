"""东方财富与腾讯一分钟分时行情直连适配器。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.intraday import (
    IntradayBar,
    IntradayBarState,
    IntradayCheckpoint,
    IntradaySourceSeries,
)
from src.data.providers.quotes import USER_AGENT, _eastmoney_secid, _market_prefix

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
INTRADAY_TIMEOUT_SECONDS = 5.0
EASTMONEY_INTRADAY_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
TENCENT_INTRADAY_URL = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"


class IntradayFetcher(Protocol):
    def __call__(self, code: str) -> Mapping[str, Any]:
        """返回一个上游的一分钟行情响应。"""
        ...


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def _default_eastmoney_fetcher(code: str) -> Mapping[str, Any]:
    import httpx

    response = httpx.get(
        EASTMONEY_INTRADAY_URL,
        params={
            "secid": _eastmoney_secid(code),
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "ndays": "1",
            "iscr": "0",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=INTRADAY_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Eastmoney intraday response must be an object")
    return payload


def _default_tencent_fetcher(code: str) -> Mapping[str, Any]:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    response = httpx.get(
        TENCENT_INTRADAY_URL,
        params={"code": symbol},
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://gu.qq.com/",
        },
        timeout=INTRADAY_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Tencent intraday response must be an object")
    return payload


def _number(value: object, field: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field} is not numeric")
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{field} is not numeric") from exc


def _integer(value: object, field: str) -> int:
    number = _number(value, field)
    if number < 0 or not number.is_integer():
        raise ValueError(f"{field} must be a non-negative integer")
    return int(number)


def _state(timestamp: datetime, now: datetime) -> IntradayBarState:
    current_minute = now.replace(second=0, microsecond=0)
    next_minute = current_minute.replace(second=0, microsecond=0)
    next_minute = next_minute + timedelta(minutes=1)
    if timestamp > next_minute:
        raise ValueError("intraday row timestamp is in the future")
    return (
        IntradayBarState.FINAL
        if timestamp <= current_minute
        else IntradayBarState.PROVISIONAL
    )


def _failed(
    descriptor: SourceDescriptor,
    exc: Exception,
    *,
    error_code: str,
) -> SourceResult[IntradaySourceSeries]:
    return SourceResult(
        source_id=descriptor.source_id,
        upstream_id=descriptor.upstream_id,
        capability=EvidenceCapability.INTRADAY,
        status=SourceStatus.FAILED,
        error_code=error_code,
        error_message=str(exc).strip() or exc.__class__.__name__,
    )


class EastmoneyIntradaySource:
    """东方财富一分钟 OHLC、成交量与成交额。"""

    descriptor = SourceDescriptor(
        source_id="direct-eastmoney-intraday",
        upstream_id="eastmoney",
        display_name="东方财富一分钟行情直连",
        capabilities={EvidenceCapability.INTRADAY},
    )

    def __init__(
        self,
        *,
        fetcher: IntradayFetcher = _default_eastmoney_fetcher,
        now_provider: Callable[[], datetime] = _now_shanghai,
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider

    def fetch(
        self,
        request: EvidenceRequest,
    ) -> SourceResult[IntradaySourceSeries]:
        if request.capability is not EvidenceCapability.INTRADAY:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        try:
            payload = self._fetcher(request.stock_code)
            data = payload.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Eastmoney intraday response is missing data")
            code = str(data.get("code", "")).strip()
            name = str(data.get("name", "")).strip()
            if code != request.stock_code or not name:
                raise ValueError("Eastmoney intraday identity does not match request")
            raw_rows = data.get("trends")
            if not isinstance(raw_rows, list) or not raw_rows:
                raise ValueError("Eastmoney intraday trends are empty")

            now = self._aware_now()
            bars: list[IntradayBar] = []
            checkpoints: list[IntradayCheckpoint] = []
            cumulative_volume = 0
            cumulative_amount = 0.0
            for raw_row in raw_rows:
                fields = str(raw_row).split(",")
                if len(fields) < 8:
                    raise ValueError("Eastmoney intraday row has fewer than 8 fields")
                timestamp = datetime.strptime(
                    fields[0].strip(),
                    "%Y-%m-%d %H:%M",
                ).replace(tzinfo=SHANGHAI)
                row_state = _state(timestamp, now)
                volume = _integer(fields[5], "volume") * 100
                amount = _number(fields[6], "amount")
                cumulative_volume += volume
                cumulative_amount += amount
                bar = IntradayBar(
                    code=code,
                    timestamp=timestamp,
                    open=_number(fields[1], "open"),
                    close=_number(fields[2], "close"),
                    high=_number(fields[3], "high"),
                    low=_number(fields[4], "low"),
                    volume=volume,
                    amount=amount,
                    state=row_state,
                )
                bars.append(bar)
                checkpoints.append(
                    IntradayCheckpoint(
                        code=code,
                        timestamp=timestamp,
                        close=bar.close,
                        cumulative_volume=cumulative_volume,
                        cumulative_amount=cumulative_amount,
                        state=row_state,
                    )
                )
            series = IntradaySourceSeries(
                code=code,
                name=name,
                checkpoints=checkpoints,
                bars=bars,
                ohlc_supported=True,
            )
        except Exception as exc:
            logger.exception("Eastmoney intraday collection failed")
            return _failed(
                self.descriptor,
                exc,
                error_code="invalid_upstream_payload",
            )
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[series],
        )

    def _aware_now(self) -> datetime:
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        return now.astimezone(SHANGHAI)


class TencentIntradaySource:
    """腾讯分钟收盘价、累计成交量与累计成交额核验源。"""

    descriptor = SourceDescriptor(
        source_id="direct-tencent-intraday",
        upstream_id="tencent",
        display_name="腾讯一分钟行情直连",
        capabilities={EvidenceCapability.INTRADAY},
    )

    def __init__(
        self,
        *,
        fetcher: IntradayFetcher = _default_tencent_fetcher,
        now_provider: Callable[[], datetime] = _now_shanghai,
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider

    def fetch(
        self,
        request: EvidenceRequest,
    ) -> SourceResult[IntradaySourceSeries]:
        if request.capability is not EvidenceCapability.INTRADAY:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        try:
            payload = self._fetcher(request.stock_code)
            if payload.get("code") != 0:
                raise ValueError("Tencent intraday response code is not zero")
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            all_data = payload.get("data")
            if not isinstance(all_data, Mapping):
                raise ValueError("Tencent intraday response is missing data")
            symbol_data = all_data.get(symbol)
            if not isinstance(symbol_data, Mapping):
                raise ValueError("Tencent intraday identity does not match request")
            minute_data = symbol_data.get("data")
            if not isinstance(minute_data, Mapping):
                raise ValueError("Tencent intraday minute data is missing")
            trading_date = datetime.strptime(
                str(minute_data.get("date", "")).strip(),
                "%Y%m%d",
            ).date()
            raw_rows = minute_data.get("data")
            if not isinstance(raw_rows, list) or not raw_rows:
                raise ValueError("Tencent intraday rows are empty")

            qt = symbol_data.get("qt")
            quote_row = qt.get(symbol) if isinstance(qt, Mapping) else None
            name = (
                str(quote_row[1]).strip()
                if isinstance(quote_row, list) and len(quote_row) > 1
                else ""
            )
            if not name:
                raise ValueError("Tencent intraday identity is empty")

            now = self._aware_now()
            checkpoints: list[IntradayCheckpoint] = []
            previous_volume = 0
            previous_amount = 0.0
            for raw_row in raw_rows:
                fields = str(raw_row).split()
                if len(fields) < 3:
                    raise ValueError("Tencent intraday row has fewer than 3 fields")
                clock = datetime.strptime(fields[0], "%H%M").time()
                timestamp = datetime.combine(
                    trading_date,
                    clock,
                    tzinfo=SHANGHAI,
                )
                cumulative_volume = (
                    _integer(fields[2], "cumulative_volume") * 100
                )
                cumulative_amount = (
                    _number(fields[3], "cumulative_amount")
                    if len(fields) >= 4
                    else 0.0
                )
                if (
                    cumulative_volume < previous_volume
                    or cumulative_amount < previous_amount
                ):
                    raise ValueError("Tencent cumulative values must not decrease")
                previous_volume = cumulative_volume
                previous_amount = cumulative_amount
                checkpoints.append(
                    IntradayCheckpoint(
                        code=request.stock_code,
                        timestamp=timestamp,
                        close=_number(fields[1], "close"),
                        cumulative_volume=cumulative_volume,
                        cumulative_amount=cumulative_amount,
                        state=_state(timestamp, now),
                    )
                )
            series = IntradaySourceSeries(
                code=request.stock_code,
                name=name,
                checkpoints=checkpoints,
                bars=[],
                ohlc_supported=False,
            )
        except Exception as exc:
            logger.exception("Tencent intraday collection failed")
            return _failed(
                self.descriptor,
                exc,
                error_code="invalid_upstream_payload",
            )
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[series],
        )

    def _aware_now(self) -> datetime:
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        return now.astimezone(SHANGHAI)


__all__ = [
    "EastmoneyIntradaySource",
    "TencentIntradaySource",
]

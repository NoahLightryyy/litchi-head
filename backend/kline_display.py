"""Explicit single-source RAW daily display, separate from adjusted research data."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.kline import RawDailyBar
from src.data.providers.kline import TencentRawDailyKlineSource

raw_daily_source = TencentRawDailyKlineSource()


class RawDailyDisplay(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    source: Literal["tencent"] = "tencent"
    price_basis: Literal["raw"] = "raw"
    verification: Literal["single_source"] = "single_source"
    status: SourceStatus
    fetched_at: datetime
    data_start: date | None = None
    data_end: date | None = None
    bars: list[RawDailyBar] = Field(default_factory=list)
    error_code: str | None = None


def get_raw_daily_display(symbol: str) -> RawDailyDisplay:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    result = raw_daily_source.fetch(EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code=symbol,
        start_at=now - timedelta(days=90),
        end_at=now - timedelta(days=1),
    ))
    bars = sorted(result.items, key=lambda bar: bar.trade_date) if (
        result.status is SourceStatus.SUCCESS_DATA
    ) else []
    return RawDailyDisplay(
        symbol=symbol, status=result.status, fetched_at=result.fetched_at,
        bars=bars, data_start=bars[0].trade_date if bars else None,
        data_end=bars[-1].trade_date if bars else None, error_code=result.error_code,
    )

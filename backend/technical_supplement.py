"""Reproducible research facts: provider-adjusted prices and raw-share volume."""

from __future__ import annotations

from datetime import date, datetime
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from backend.indicators import calc_all, calc_kdj
from src.data.kline import RawDailyBar
from src.data.providers.tencent_qfq import ProviderQfqBar


class TechnicalPoint(BaseModel):
    trade_date: date
    ma: dict[str, float | None]
    rsi14: float | None
    macd: dict[str, float | None]
    kdj: dict[str, float | None]


def technical_points(bars: list[RawDailyBar] | list[ProviderQfqBar]) -> list[TechnicalPoint]:
    rows = [bar.model_dump() for bar in bars]
    calculated, kdj = calc_all(rows), calc_kdj(rows)
    return [
        TechnicalPoint(
            trade_date=bars[i].trade_date,
            ma={key: values[i] for key, values in calculated["ma_series"].items()},
            rsi14=calculated["rsi_series"][i],
            macd={key: values[i] for key, values in calculated["macd_series"].items()},
            kdj={key: values[i] for key, values in kdj.items()},
        )
        for i in range(max(0, len(bars) - 20), len(bars))
    ]


class AdjustedEvidence(BaseModel):
    status: Literal["available", "unavailable"] = "unavailable"
    price_basis: Literal["provider_qfq_current"] = "provider_qfq_current"
    source: Literal["tencent"] = "tencent"
    fetched_at: datetime | None = None
    data_start: date | None = None
    data_end: date | None = None
    bar_count: int = 0
    response_hash: str | None = None
    indicators: list[TechnicalPoint] = Field(default_factory=list)
    reason: str | None = "尚未读取前复权数据"
    methodology: str = (
        "腾讯当前前复权价格；指标在整段前复权序列上独立计算，不拼接未复权价格。"
        "这是来源提供的复权口径，非逐笔官方除权审计，也不能用于过去时点无未来信息回测。"
        "成交量另取原始股数，不按价格复权比例缩放。"
    )


class VolumeEvidence(BaseModel):
    status: Literal["available", "partial", "unavailable"] = "unavailable"
    data_date: date | None = None
    sample_bars: int = 0
    volume_basis: Literal["raw_shares"] = "raw_shares"
    latest_shares: int | None = None
    previous5_mean_shares: float | None = None
    previous20_mean_shares: float | None = None
    ratio_to_previous5: float | None = None
    ratio_to_previous20: float | None = None
    comparison: Literal["above_both", "below_both", "equal_both", "mixed", "insufficient"] = (
        "insufficient"
    )
    methodology: str = (
        "最新已结束交易日成交股数，分别除以前5/20根已结束日线的平均成交股数；均值不含当日。"
        "这是日成交量对比，不是盘中量比；不自动证明反转、主力买入或买入信号。"
        "量能可有数据但条件未出现；送转、配股等股本变化仍需结合公司公告解释。"
    )


def build_volume_evidence(bars: list[RawDailyBar]) -> VolumeEvidence:
    if not bars:
        return VolumeEvidence()
    last = bars[-1]
    avg5 = mean(b.volume for b in bars[-6:-1]) if len(bars) >= 6 else None
    avg20 = mean(b.volume for b in bars[-21:-1]) if len(bars) >= 21 else None
    r5 = last.volume / avg5 if avg5 is not None and avg5 > 0 else None
    r20 = last.volume / avg20 if avg20 is not None and avg20 > 0 else None
    result = VolumeEvidence(
        status="partial",
        data_date=last.trade_date,
        sample_bars=len(bars),
        latest_shares=last.volume,
        previous5_mean_shares=avg5,
        previous20_mean_shares=avg20,
        ratio_to_previous5=r5,
        ratio_to_previous20=r20,
    )
    if r5 is not None and r20 is not None:
        result.status = "available"
        if r5 > 1 and r20 > 1:
            result.comparison = "above_both"
        elif r5 < 1 and r20 < 1:
            result.comparison = "below_both"
        elif r5 == 1 and r20 == 1:
            result.comparison = "equal_both"
        else:
            result.comparison = "mixed"
    return result


def build_adjusted_evidence(
    raw: list[RawDailyBar], adjusted: list[ProviderQfqBar], fetched_at: datetime, response_hash: str
) -> AdjustedEvidence:
    if not raw or not adjusted:
        raise ValueError("No history to align")
    if [b.trade_date for b in raw] != [b.trade_date for b in adjusted] or any(
        b.code != raw[0].code for b in adjusted
    ):
        raise ValueError("Adjusted identity or coverage differs from raw history")
    return AdjustedEvidence(
        status="available",
        fetched_at=fetched_at,
        data_start=adjusted[0].trade_date,
        data_end=adjusted[-1].trade_date,
        bar_count=len(adjusted),
        response_hash=response_hash,
        reason=None,
        indicators=technical_points(adjusted),
    )

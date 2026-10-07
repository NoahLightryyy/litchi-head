"""Dual-source completed RAW daily history and reproducible research indicators.

Research context only: this does not replace adjusted-price or trading gates.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from backend.indicators import calc_all, calc_kdj
from src.data.evidence import EvidenceCapability, EvidenceEnvelope, EvidenceRequest
from src.data.kline import RawDailyBar
from src.data.kline_runtime import KLINE_RAW_EVIDENCE_POLICY, get_raw_daily_kline_runtime

logger = logging.getLogger(__name__)


class TechnicalPoint(BaseModel):
    trade_date: date
    ma: dict[str, float | None]
    rsi14: float | None
    macd: dict[str, float | None]
    kdj: dict[str, float | None]


class TechnicalResearch(BaseModel):
    stock_code: str
    status: Literal["available", "unavailable"]
    fetched_at: datetime
    price_basis: Literal["raw"] = "raw"
    sources: list[str] = Field(default_factory=list)
    diagnostics: dict[str, str] = Field(default_factory=dict)
    bars: list[RawDailyBar] = Field(default_factory=list)
    indicators: list[TechnicalPoint] = Field(default_factory=list)
    methodology: str = (
        "已结束日线；价格元、成交量股。MA为5/10/20/60日简单均线；"
        "RSI14使用Wilder平滑，完全横盘为50；MACD12/26/9以SMA初始化EMA，柱=DIF-DEA（未乘2）；"
        "KDJ9/3/3以完整9根计算RSV，K=D初始50，递推权重1/3，平价窗口RSV=50，J=3K-2D。"
        "预热不足返回null；指标序列仅保留最近20根，计算使用全部已校验历史。"
    )
    limitations: list[str] = Field(default_factory=lambda: [
        "未复权：除权除息可能造成价格断点，不能将跨断点变化直接解释为交易动量；复权与公司行为尚未校验。",
        "本次最多回看240个自然日，实际覆盖以bars日期为准；不足以代表多年趋势。",
        "仅作为研究资料，不替代正式四层K线准入，不代表涨跌概率。",
    ])


def build_technical_research(code: str, envelope: EvidenceEnvelope) -> TechnicalResearch:
    if envelope.request.stock_code != code:
        raise ValueError("Technical evidence identity mismatch")
    result = TechnicalResearch(
        stock_code=code, status="unavailable", fetched_at=envelope.collected_at,
        diagnostics={r.source_id: r.error_code or r.status.value for r in envelope.source_results},
    )
    if not envelope.complete or not envelope.items:
        logger.warning("Technical research unavailable: code=%s sources=%s",
                       code, result.diagnostics)
        result.limitations.append("双源日线未通过完整性校验，本次不计算指标。")
        return result
    bars = sorted([RawDailyBar.model_validate(item) for item in envelope.items],
                  key=lambda bar: bar.trade_date)
    if any(bar.code != code for bar in bars):
        raise ValueError("Foreign bar in technical evidence")
    if len({bar.trade_date for bar in bars}) != len(bars):
        raise ValueError("Duplicate technical evidence date")
    rows = [bar.model_dump() for bar in bars]
    calculated = calc_all(rows)
    kdj = calc_kdj(rows)
    result.status = "available"
    result.sources = sorted(envelope.assessment.successful_upstream_ids)
    result.bars = bars
    result.indicators = [TechnicalPoint(
        trade_date=bars[i].trade_date,
        ma={key: values[i] for key, values in calculated["ma_series"].items()},
        rsi14=calculated["rsi_series"][i],
        macd={key: values[i] for key, values in calculated["macd_series"].items()},
        kdj={key: values[i] for key, values in kdj.items()},
    ) for i in range(max(0, len(bars) - 20), len(bars))]
    return result


def get_technical_research(code: str) -> TechnicalResearch:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    request = EvidenceRequest(capability=EvidenceCapability.KLINE, stock_code=code,
                              start_at=now - timedelta(days=240), end_at=now - timedelta(days=1))
    envelope = get_raw_daily_kline_runtime().service.collect(request, KLINE_RAW_EVIDENCE_POLICY)
    result = build_technical_research(code, envelope)
    logger.info("Technical research: code=%s status=%s bars=%s sources=%s",
                code, result.status, len(result.bars), result.sources)
    return result

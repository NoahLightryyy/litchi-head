"""Completed RAW history with separate provider-QFQ indicators and volume facts.

Research context only: this does not replace official adjustment audits or trading gates.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from backend.technical_supplement import (
    AdjustedEvidence,
    TechnicalPoint,
    VolumeEvidence,
    build_adjusted_evidence,
    build_volume_evidence,
    technical_points,
)
from src.data.evidence import EvidenceCapability, EvidenceEnvelope, EvidenceRequest
from src.data.kline import RawDailyBar
from src.data.kline_runtime import get_raw_daily_kline_runtime
from src.data.providers.tencent_qfq import fetch_qfq_daily
from src.data.research_policy import RESEARCH_KLINE_POLICY

logger = logging.getLogger(__name__)


class TechnicalResearch(BaseModel):
    stock_code: str
    status: Literal["available", "unavailable"]
    fetched_at: datetime
    price_basis: Literal["raw"] = "raw"
    sources: list[str] = Field(default_factory=list)
    diagnostics: dict[str, str] = Field(default_factory=dict)
    bars: list[RawDailyBar] = Field(default_factory=list)
    indicators: list[TechnicalPoint] = Field(default_factory=list)
    adjusted: AdjustedEvidence = Field(default_factory=AdjustedEvidence)
    volume: VolumeEvidence = Field(default_factory=VolumeEvidence)
    methodology: str = (
        "已结束日线；价格元、成交量股。MA为5/10/20/60日简单均线；"
        "RSI14使用Wilder平滑，完全横盘为50；MACD12/26/9以SMA初始化EMA，柱=DIF-DEA（未乘2）；"
        "KDJ9/3/3以完整9根计算RSV，K=D初始50，递推权重1/3，平价窗口RSV=50，J=3K-2D。"
        "预热不足返回null；指标序列仅保留最近20根，计算使用全部已校验历史。"
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "未复权：除权除息可能造成价格断点，不能将跨断点变化直接解释为交易动量；复权与公司行为尚未校验。",
            "本次最多回看240个自然日，实际覆盖以bars日期为准；不足以代表多年趋势。",
            "仅作为研究资料，不替代正式四层K线准入，不代表涨跌概率。",
        ]
    )


def build_technical_research(code: str, envelope: EvidenceEnvelope) -> TechnicalResearch:
    if envelope.request.stock_code != code:
        raise ValueError("Technical evidence identity mismatch")
    result = TechnicalResearch(
        stock_code=code,
        status="unavailable",
        fetched_at=envelope.collected_at,
        diagnostics={r.source_id: r.error_code or r.status.value for r in envelope.source_results},
    )
    if not envelope.complete or not envelope.items:
        logger.warning(
            "Technical research unavailable: code=%s sources=%s", code, result.diagnostics
        )
        result.limitations.append("未取得通过校验的日线，本次不计算指标；原因见来源诊断。")
        return result
    bars = sorted(
        [RawDailyBar.model_validate(item) for item in envelope.items],
        key=lambda bar: bar.trade_date,
    )
    if any(bar.code != code for bar in bars):
        raise ValueError("Foreign bar in technical evidence")
    if len({bar.trade_date for bar in bars}) != len(bars):
        raise ValueError("Duplicate technical evidence date")
    result.status = "available"
    result.sources = sorted(envelope.assessment.successful_upstream_ids)
    result.bars = bars
    result.indicators = technical_points(bars)
    result.volume = build_volume_evidence(bars)
    return result


def _collect_technical_research(code: str) -> TechnicalResearch:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    request = EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code=code,
        start_at=now - timedelta(days=240),
        end_at=now - timedelta(days=1),
    )
    envelope = get_raw_daily_kline_runtime().service.collect(request, RESEARCH_KLINE_POLICY)
    result = build_technical_research(code, envelope)
    if result.bars:
        try:
            adjusted, fetched_at, response_hash = fetch_qfq_daily(
                code, result.bars[0].trade_date, result.bars[-1].trade_date
            )
            result.adjusted = build_adjusted_evidence(
                result.bars, adjusted, fetched_at, response_hash
            )
            result.limitations[0] = (
                "已补充当前前复权价格与指标；原始bars/indicators仍为未复权口径，"
                "价格趋势优先使用adjusted.indicators，不混用两种价格均线或支撑位。"
            )
        except Exception:
            logger.warning("Adjusted research unavailable: code=%s", code, exc_info=True)
            result.adjusted.reason = "本次前复权数据未取得或日期未对齐；成交量资料仍可单独使用。"
    logger.info(
        "Technical research: code=%s status=%s bars=%s sources=%s",
        code,
        result.status,
        len(result.bars),
        result.sources,
    )
    return result


class _CachedResearch:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.expires = 0.0
        self.value: TechnicalResearch | None = None


@lru_cache(maxsize=128)
def _cache_entry(code: str) -> _CachedResearch:
    return _CachedResearch()


def get_technical_research(code: str) -> TechnicalResearch:
    """Per-symbol single flight. Reuse good facts for 5 min, partial results for 30 s."""
    entry = _cache_entry(code)
    with entry.lock:
        if entry.value is not None and time.monotonic() < entry.expires:
            return entry.value.model_copy(deep=True)
        value = _collect_technical_research(code)
        entry.value = value
        entry.expires = time.monotonic() + (300 if value.adjusted.status == "available" else 30)
        return value.model_copy(deep=True)

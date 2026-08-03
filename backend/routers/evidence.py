"""统一证据聚合路由。"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from backend.async_utils import run_sync
from backend.config import RATE_LIMIT_QUOTE_AGGREGATE
from backend.limiter import limiter
from src.data.collector import DataCollector
from src.data.evidence import (
    EvidenceCapability,
    EvidenceEnvelope,
    EvidenceRequest,
    SourceStatus,
)
from src.data.intraday import (
    IntradayBar,
    IntradayBattlefieldEngine,
    IntradayBattlefieldEnvelope,
    IntradaySourceDiagnostic,
    IntradaySourceSeries,
)
from src.data.intraday_runtime import (
    INTRADAY_EVIDENCE_POLICY,
    get_intraday_evidence_runtime,
)
from src.data.news_runtime import NEWS_EVIDENCE_POLICY, get_news_evidence_runtime
from src.data.quote_runtime import (
    REALTIME_QUOTE_EVIDENCE_POLICY,
    get_realtime_quote_evidence_runtime,
)

logger = logging.getLogger("backend.evidence")
router = APIRouter(prefix="/api/v1/evidence")
collector = DataCollector()

news_evidence_service = get_news_evidence_runtime().service
quote_evidence_service = get_realtime_quote_evidence_runtime().service
intraday_runtime = get_intraday_evidence_runtime()
intraday_evidence_service = intraday_runtime.service
intraday_history_coordinator = intraday_runtime.history
intraday_battlefield_engine = IntradayBattlefieldEngine()


class NewsAggregateRequest(BaseModel):
    """新闻聚合请求。时间必须带时区，避免跨节点产生日期歧义。"""

    symbol: str = Field(pattern=r"^\d{6}$")
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_range(self) -> "NewsAggregateRequest":
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include timezone")
        if self.start_time > self.end_time:
            raise ValueError("start_time must not be later than end_time")
        return self


class QuoteAggregateRequest(BaseModel):
    """单只股票实时行情聚合请求。"""

    symbol: str = Field(pattern=r"^\d{6}$")


class IntradayBattlefieldRequest(BaseModel):
    """单只股票 L1 分时战况请求。"""

    symbol: str = Field(pattern=r"^\d{6}$")


def resolve_stock_name(stock_code: str) -> str:
    """从现有股票主数据解析名称；失败时保留代码匹配能力。"""
    try:
        stocks = collector.get_all_stocks()
    except Exception:
        logger.exception("股票名称解析失败: stock_code=%s", stock_code)
        return ""
    return next(
        (stock.name for stock in stocks if stock.code == stock_code),
        "",
    )


@router.post("/news/aggregate", response_model=EvidenceEnvelope)
async def aggregate_news(payload: NewsAggregateRequest) -> EvidenceEnvelope:
    """并发采集独立新闻上游，返回统一状态、条目和完整性评估。"""
    stock_name = await run_sync(resolve_stock_name, payload.symbol)
    request = EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code=payload.symbol,
        stock_name=stock_name,
        start_at=payload.start_time,
        end_at=payload.end_time,
    )
    return await run_sync(
        news_evidence_service.collect,
        request,
        NEWS_EVIDENCE_POLICY,
    )


@router.post("/quotes/aggregate", response_model=EvidenceEnvelope)
@limiter.limit(RATE_LIMIT_QUOTE_AGGREGATE)
async def aggregate_quotes(
    request: Request,
    payload: QuoteAggregateRequest,
) -> EvidenceEnvelope:
    """并发采集并校验东方财富、新浪两条实时行情。"""
    evidence_request = EvidenceRequest(
        capability=EvidenceCapability.REALTIME_QUOTE,
        stock_code=payload.symbol,
    )
    return await run_sync(
        quote_evidence_service.collect,
        evidence_request,
        REALTIME_QUOTE_EVIDENCE_POLICY,
    )


@router.post(
    "/intraday/battlefield",
    response_model=IntradayBattlefieldEnvelope,
)
@limiter.limit(RATE_LIMIT_QUOTE_AGGREGATE)
async def intraday_battlefield(
    request: Request,
    payload: IntradayBattlefieldRequest,
) -> IntradayBattlefieldEnvelope:
    """返回双源核验后的分钟曲线、L1 战况和精简逐源诊断。"""
    evidence_request = EvidenceRequest(
        capability=EvidenceCapability.INTRADAY,
        stock_code=payload.symbol,
    )
    envelope = await run_sync(
        intraday_evidence_service.collect,
        evidence_request,
        INTRADAY_EVIDENCE_POLICY,
    )
    bars = [IntradayBar.model_validate(item) for item in envelope.items]
    verified_series = tuple(
        (
            result.source_id,
            IntradaySourceSeries.model_validate(result.items[0]),
        )
        for result in envelope.source_results
        if result.status is SourceStatus.SUCCESS_DATA and result.items
    )
    history = (
        await run_sync(
            intraday_history_coordinator.prepare,
            payload.symbol,
            as_of=bars[-1].timestamp,
            verified_series=verified_series,
        )
        if envelope.complete and bars
        else None
    )
    snapshot = (
        intraday_battlefield_engine.analyze(
            bars,
            volume_baseline=history.baseline if history else None,
        )
        if envelope.complete and bars
        else None
    )
    if snapshot is not None and history is not None:
        snapshot.limitations.extend(
            limitation
            for limitation in history.limitations
            if limitation not in snapshot.limitations
        )
    diagnostics: list[IntradaySourceDiagnostic] = []
    for result in envelope.source_results:
        series = IntradaySourceSeries.model_validate(result.items[0]) if result.items else None
        diagnostics.append(
            IntradaySourceDiagnostic(
                source_id=result.source_id,
                upstream_id=result.upstream_id,
                status=result.status,
                fetched_at=result.fetched_at,
                error_code=result.error_code,
                error_message=result.error_message,
                checkpoint_count=len(series.checkpoints) if series else 0,
                latest_timestamp=(
                    series.checkpoints[-1].timestamp if series and series.checkpoints else None
                ),
            )
        )
    return IntradayBattlefieldEnvelope(
        symbol=payload.symbol,
        complete=envelope.complete,
        collected_at=envelope.collected_at,
        assessment=envelope.assessment,
        source_diagnostics=diagnostics,
        bars=bars,
        snapshot=snapshot,
    )


__all__ = ["router"]

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


__all__ = ["router"]

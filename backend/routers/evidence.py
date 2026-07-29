"""统一证据聚合路由。"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from backend.async_utils import run_sync
from src.data.collector import DataCollector
from src.data.evidence import (
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
)
from src.data.evidence_service import DataEvidenceService
from src.data.providers.news import EastmoneyNewsSource, SinaNewsSource

logger = logging.getLogger("backend.evidence")
router = APIRouter(prefix="/api/v1/evidence")
collector = DataCollector()

_registry = EvidenceSourceRegistry()
_registry.register(EastmoneyNewsSource())
_registry.register(SinaNewsSource())
news_evidence_service = DataEvidenceService(_registry, max_workers=2)


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
    policy = EvidencePolicy(
        capability=EvidenceCapability.NEWS,
        min_independent_upstreams=2,
    )
    return await run_sync(news_evidence_service.collect, request, policy)


__all__ = ["router"]

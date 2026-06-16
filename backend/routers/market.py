"""市场数据路由 —— /api/market/*

提供指数行情、板块排行、板块详情、AI 宏观简报等接口。
"""

from __future__ import annotations

import time
import logging
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.data.collector import DataCollector
from src.data.models import StockQuote as BackendQuote

logger = logging.getLogger("backend.market")
router = APIRouter(prefix="/api/market")
collector = DataCollector()

# ── 响应模型（匹配 frontend/lib/types/market.ts） ──────────────


class IndexQuoteResp(BaseModel):
    """三大指数行情（匹配 MarketIndex 类型）"""
    code: str
    name: str
    price: float = 0.0
    change: float = 0.0  # 涨跌额（与 change_pct 同值，类型兼容用）
    change_pct: float = 0.0


class SectorItemResp(BaseModel):
    """板块排行条目（匹配 SectorItem 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float = 0.0
    heat: str = "medium"
    top_stocks: list[str] = Field(default_factory=list)
    rank: int = 0


class SectorStockResp(BaseModel):
    """板块内个股（匹配 SectorStock 类型）"""
    code: str
    name: str
    price: float = 0.0
    change_pct: float = 0.0
    fund_flow: float = 0.0
    ai_rating: str = "B"


class ChainNodeResp(BaseModel):
    """产业链节点（匹配 ChainNode 类型）"""
    name: str
    companies: list[str] = Field(default_factory=list)
    is_bottleneck: bool = False


class ChainStageResp(BaseModel):
    """产业链阶段（匹配 ChainStage 类型）"""
    stage: str
    description: str = ""
    nodes: list[ChainNodeResp] = Field(default_factory=list)


class SectorDetailResp(BaseModel):
    """板块详情（匹配 SectorDetail 类型）"""
    id: str
    name: str
    change_pct: float = 0.0
    fund_flow: float = 0.0
    heat: str = "medium"
    chain_map: list[ChainStageResp] = Field(default_factory=list)
    ai_analysis: str = ""
    stocks: list[SectorStockResp] = Field(default_factory=list)


class MacroBriefResp(BaseModel):
    """AI 宏观简报（匹配 MacroBrief 类型）"""
    summary: str = "暂无数据"
    generated_at: str = ""
    market_style: str = ""
    risk_tips: list[str] = Field(default_factory=list)
    hot_topics: list[str] = Field(default_factory=list)


# ── 辅助函数 ──────────────────────────────────────────────────

_INDEX_CODES: list[tuple[str, str]] = [
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
]

def _pick_index(quotes: list[BackendQuote], code: str, name: str) -> IndexQuoteResp:
    for q in quotes:
        if q.code == code:
            return IndexQuoteResp(
                code=q.code, name=name, price=q.price,
                change=q.change, change_pct=q.change_pct,
            )
    return IndexQuoteResp(code=code, name=name)


def _enrich_sector_item(code: str, name: str, rank: int) -> SectorItemResp:
    """组装板块条目（heat/top_stocks 由业务层后续接入真实数据源）"""
    return SectorItemResp(
        id=code, name=name, rank=rank,
        change_pct=0.0, fund_flow=0.0,
    )


# ── 路由 ──────────────────────────────────────────────────────


@router.get("/indices")
async def get_indices():
    """三大指数实时行情"""
    t0 = time.time()
    quotes = collector.get_realtime_quotes()
    indices = [_pick_index(quotes, code, name) for code, name in _INDEX_CODES]
    return {
        "data": [i.model_dump() for i in indices],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/sectors")
async def get_sectors(sort: str = Query("fund_flow", description="排序维度")):
    """板块排行（行业 + 概念，akshare 原始数据）"""
    t0 = time.time()
    industry = collector.get_industry_boards()
    concept = collector.get_concept_boards()
    items: list[SectorItemResp] = []
    for i, b in enumerate(industry):
        items.append(_enrich_sector_item(b.code, b.name, i + 1))
    for i, b in enumerate(concept):
        items.append(_enrich_sector_item(b.code, b.name, len(industry) + i + 1))
    return {
        "data": [i.model_dump() for i in items],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/sector/{sector_id:str}")
async def get_sector_detail(sector_id: str):
    """板块详情（akshare 原始数据，chain_map 待接入真实产业链数据源）"""
    t0 = time.time()
    industry = collector.get_industry_boards()
    concept = collector.get_concept_boards()
    found = next((b for b in industry if b.code == sector_id), None)
    if found is None:
        found = next((b for b in concept if b.code == sector_id), None)
    if found is None:
        return {"data": None, "meta": {"cached": False, "latency_ms": 0}}

    detail = SectorDetailResp(
        id=found.code, name=found.name,
    )
    return {
        "data": detail.model_dump(),
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/brief")
async def get_macro_brief():
    """AI 宏观简报"""
    t0 = time.time()
    quotes = collector.get_realtime_quotes()
    indices = [_pick_index(quotes, code, name) for code, name in _INDEX_CODES]
    lines: list[str] = []
    for i in indices:
        if i.price > 0:
            lines.append(f"  {i.name}: {i.price:.2f}（{i.change_pct:+.2f}%）")

    summary = "暂无数据" if not lines else " | ".join(lines)
    brief = MacroBriefResp(
        summary=summary,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    return {
        "data": brief.model_dump(),
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }

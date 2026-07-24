"""财务数据路由 —— /api/stocks/{code}/financials + /valuation

提供个股财务指标（ROE/毛利率/负债率等）和估值比率（PE/PB/PS）。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from backend.async_utils import run_sync
from src.data.collector import DataCollector

logger = logging.getLogger("backend.financials")
router = APIRouter(prefix="/api/stocks")
collector = DataCollector()


@router.get("/{code:str}/financials")
async def get_financials(code: str):
    """个股财务指标（ROE/毛利率/负债率等）

    返回最近 N 个报告期的财务指标列表，最新在前。
    """
    t0 = time.time()
    items = await run_sync(collector.get_financials, code)
    return {
        "data": [i.model_dump() for i in items[:10]],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/indicators")
async def get_indicators(code: str):
    """个股动态关键指标（按行业注册表）

    返回该股票所属行业的关键指标列表（5-10 个）。
    基于 PD 动态指标体系：行业 → 产业链位置 → 注册表选择。
    """
    t0 = time.time()
    result = await run_sync(collector.get_dynamic_indicators, code)
    return {
        "data": result,
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/valuation")
async def get_valuation(code: str):
    """个股估值比率（PE/PB/PS + 总市值）

    基于最新财报指标 + 当前股价计算。
    无财务数据或无行情时返回 null。
    """
    t0 = time.time()
    val = await run_sync(collector.get_valuation, code)
    return {
        "data": val.model_dump() if val is not None else None,
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }

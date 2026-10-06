"""财务数据路由 —— /api/stocks/{code}/financials + /valuation

提供个股财务指标（ROE/毛利率/负债率等）和估值比率（PE/PB/PS）。
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter

from backend.async_utils import BoundedSyncRunner, run_sync
from backend.financial_display import FinancialResponse, enrich, income_statements
from src.data.collector import DataCollector

logger = logging.getLogger("backend.financials")
router = APIRouter(prefix="/api/stocks")
collector = DataCollector()
margin_runner = BoundedSyncRunner(max_workers=2, thread_name_prefix="margin-display")


@router.get("/{code:str}/financials", response_model=FinancialResponse)
async def get_financials(code: str):
    """个股财务指标（ROE/毛利率/负债率等）

    返回最近 N 个报告期的财务指标列表，最新在前。
    """
    t0 = time.time()
    items = await run_sync(collector.get_financials, code)
    items = items[:10]
    statements = []
    if any(i.gross_margin is None for i in items):
        try:
            statements = await asyncio.wait_for(margin_runner.run(income_statements, code), 12)
        except TimeoutError:
            logger.warning("Gross margin enrichment timed out: %s", code)
    return {
        "data": enrich(items, statements),
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
        "meta": {
            "cached": False,
            "latency_ms": round((time.time() - t0) * 1000),
            "reason": "缺少可核验时点及股本范围的总市值，暂不计算" if val is None else None,
        },
    }

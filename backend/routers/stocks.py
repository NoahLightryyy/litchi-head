"""个股数据路由 —— /api/stocks/*

提供个股行情、K 线、新闻、技术指标、资金流向等接口。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Query

from backend.async_utils import run_sync
from src.data.collector import DataCollector

logger = logging.getLogger("backend.stocks")
router = APIRouter(prefix="/api/stocks")
collector = DataCollector()


@router.get("/search")
async def search_stocks(q: str = Query("", description="搜索关键词")):
    """搜索股票"""
    t0 = time.time()
    if not q:
        return {"data": [], "meta": {"cached": False, "latency_ms": 0}}
    stocks = await run_sync(collector.get_all_stocks)
    results = [s.model_dump() for s in stocks if q.upper() in s.code or q in s.name]
    return {
        "data": results[:20],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/quote")
async def get_quote(code: str):
    """个股实时行情（含 enrich 字段）"""
    t0 = time.time()
    quote = await run_sync(collector.get_realtime_quote, code)
    if quote is None:
        return {"data": None, "meta": {"cached": False, "latency_ms": 0}}
    d = quote.model_dump()
    # 补充前端需要的字段（akshare 不直接提供）
    d["turnover_rate"] = d.get("turnover_rate", 0.0)
    d["fund_flow"] = d.get("fund_flow", 0.0)
    d["market_cap"] = d.get("market_cap", 0.0)
    d["open"] = d.pop("open_", 0.0)  # 对齐前端类型
    return {
        "data": d,
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/kline")
async def get_kline(
    code: str,
    period: str = Query("daily", description="日线/周线/月线"),
    start: str = Query("", description="开始日期 YYYY-MM-DD"),
    end: str = Query("", description="结束日期 YYYY-MM-DD"),
):
    """个股 K 线数据"""
    t0 = time.time()
    klines = await run_sync(collector.get_klines, code, period=period, start=start, end=end)
    return {
        "data": [k.model_dump() for k in klines],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/news")
async def get_news(code: str):
    """个股新闻"""
    t0 = time.time()
    news = await run_sync(collector.get_news, code)
    return {
        "data": [n.model_dump() for n in news[:20]],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/technical-indicators")
async def get_technical_indicators(
    code: str,
    period: str = Query("daily", description="日线/周线/月线"),
):
    """个股技术指标（MA/RSI/MACD/布林带）

    从 K 线数据离线计算，支持日/周/月线。
    """
    from backend.indicators import calc_all  # noqa: PLC0415

    t0 = time.time()
    klines = await run_sync(collector.get_klines, code, period=period)
    if not klines:
        return {"data": None, "meta": {"cached": False, "latency_ms": 0}}

    # K 线序列需足够长（至少 60 日）
    raw = [k.model_dump() for k in klines]
    if len(raw) < 60:
        # 数据不足时仍尝试计算
        pass

    indicators = calc_all(raw)
    return {
        "data": indicators,
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }


@router.get("/{code:str}/capital-flow")
async def get_capital_flow(code: str):
    """个股资金流向（主力/散户/机构净流入）"""
    t0 = time.time()
    items = await run_sync(collector.get_capital_flow, code)
    return {
        "data": [i.model_dump() for i in items],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }

"""个股数据路由 —— /api/stocks/*

提供个股行情、K 线、新闻、技术指标、资金流向等接口。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel

from backend.async_utils import run_sync
from backend.intraday_display import FiveDayDisplay, get_five_day_display
from backend.kline_display import RawDailyDisplay, get_raw_daily_display
from backend.quote_display import DisplayQuote, get_display_quote
from src.data.collector import DataCollector
from src.data.fundamental_research import FundamentalResearch, get_fundamental_research

logger = logging.getLogger("backend.stocks")
router = APIRouter(prefix="/api/stocks")
collector = DataCollector()


@router.get("/{code}/kline-raw-display", response_model=RawDailyDisplay)
async def raw_daily_display(
    code: str = Path(pattern=r"^\d{6}$"),
    days: int = Query(90, ge=30, le=950),
) -> RawDailyDisplay:
    """Single-source unadjusted completed daily bars; never replaces adjusted evidence."""
    return await run_sync(get_raw_daily_display, code, days=days)


@router.get("/search")
async def search_stocks(q: str = Query("", description="搜索关键词")):
    """搜索股票"""
    t0 = time.time()
    if not q:
        return {"data": [], "meta": {"cached": False, "latency_ms": 0}}
    stocks = await run_sync(collector.get_all_stocks)
    results = [s.model_dump() for s in stocks if q.upper() in s.code or q in s.name]
    cached = collector.cache_hit.get("all_stocks", False)
    latency = round((time.time() - t0) * 1000)
    return {
        "data": results[:20],
        "meta": {"cached": cached, "latency_ms": latency},
    }


class QuoteDisplayMeta(BaseModel):
    cached: bool = False
    latency_ms: int


class QuoteDisplayResponse(BaseModel):
    data: DisplayQuote | None
    meta: QuoteDisplayMeta


@router.get("/{code}/quote", response_model=QuoteDisplayResponse)
async def get_quote(code: str = Path(pattern=r"^\d{6}$")) -> QuoteDisplayResponse:
    """Single-source dated display; never depends on fetching the entire market."""
    started = time.monotonic()
    quote = await run_sync(get_display_quote, code)
    return QuoteDisplayResponse(
        data=quote, meta=QuoteDisplayMeta(latency_ms=round((time.monotonic() - started) * 1000)),
    )


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
    cache_key = f"klines:{code}:{period}:"
    cached = collector.cache_hit.get(cache_key, False)
    latency = round((time.time() - t0) * 1000)
    return {
        "data": [k.model_dump() for k in klines],
        "meta": {"cached": cached, "latency_ms": latency},
    }


@router.get("/{code:str}/news", deprecated=True)
async def get_news(code: str):
    """个股新闻"""
    t0 = time.time()
    news = await run_sync(collector.get_news, code)
    cached = collector.cache_hit.get(f"news:{code}", False)
    latency = round((time.time() - t0) * 1000)
    return {
        "data": [n.model_dump() for n in news[:20]],
        "meta": {"cached": cached, "latency_ms": latency},
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

    indicators = calc_all(raw)
    cached = collector.cache_hit.get(f"klines:{code}:{period}:", False)
    latency = round((time.time() - t0) * 1000)
    return {
        "data": indicators,
        "meta": {"cached": cached, "latency_ms": latency},
    }


@router.get("/{code:str}/capital-flow")
async def get_capital_flow(code: str):
    """个股资金流向（主力/散户/机构净流入）"""
    t0 = time.time()
    items = await run_sync(collector.get_capital_flow, code)
    cached = collector.cache_hit.get(f"capital_flow:{code}", False)
    latency = round((time.time() - t0) * 1000)
    return {
        "data": [i.model_dump() for i in items],
        "meta": {"cached": cached, "latency_ms": latency},
    }


@router.get("/{code}/intraday-five-day-display", response_model=FiveDayDisplay)
async def five_day_display(code: str = Path(pattern=r"^\d{6}$")) -> FiveDayDisplay:
    """Display only; single-source minute history is not verified research evidence."""
    return await run_sync(get_five_day_display, code)


@router.get("/{code}/fundamental-research", response_model=FundamentalResearch)
async def fundamental_research(code: str = Path(pattern=r"^\d{6}$")) -> FundamentalResearch:
    """Versioned statement facts, publication dates, formulas and missing-data reasons."""
    return await run_sync(get_fundamental_research, code)

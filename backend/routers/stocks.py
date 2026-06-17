"""个股数据路由 —— /api/stocks/*

提供个股行情、K 线、新闻、资金流向等接口。
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.data.collector import DataCollector
from src.data.providers.base import safe_float, safe_str
from backend.async_utils import run_sync

logger = logging.getLogger("backend.stocks")
router = APIRouter(prefix="/api/stocks")
collector = DataCollector()


# ── 资金流向模型 ──────────────────────────────────────────────────


class CapitalFlowItem(BaseModel):
    """个股资金流向数据点"""

    date: str = ""
    main_net_inflow: float = Field(default=0.0, description="主力净流入（大单+超大单）")
    retail_net_inflow: float = Field(default=0.0, description="小单净流入（散户）")
    institutional_net_inflow: float = Field(default=0.0, description="大单净流入（机构）")


# ── 辅助函数 ──────────────────────────────────────────────────


def _detect_market(code: str) -> str:
    """根据股票代码判断市场

    Args:
        code: 6 位股票代码

    Returns:
        "sh"（上海）/ "sz"（深圳）/ "bj"（北京）
    """
    if not code:
        return "sh"
    # 北京交易所: 4xxxxx, 8xxxxx
    if code.startswith(("4", "8")):
        return "bj"
    # 上海: 6xxxxx
    if code.startswith("6"):
        return "sh"
    # 深圳: 0xxxxx, 3xxxxx
    return "sz"


def _capital_flow_from_akshare(code: str) -> list[CapitalFlowItem]:
    """通过 akshare 获取个股资金流向

    列映射（东方财富接口）：
      日期 → date
      主力净流入-净额 → main_net_inflow
      小单净流入-净额 → retail_net_inflow
      大单净流入-净额 → institutional_net_inflow

    Args:
        code: 股票代码

    Returns:
        CapitalFlowItem 列表（失败时返回空列表）
    """
    import akshare as ak  # noqa: PLC0415

    try:
        market = _detect_market(code)
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df is None or df.empty:
            return []

        results: list[CapitalFlowItem] = []
        for _, row in df.iterrows():
            try:
                results.append(
                    CapitalFlowItem(
                        date=safe_str(row.get("日期", "")),
                        main_net_inflow=safe_float(row.get("主力净流入-净额", 0.0)),
                        retail_net_inflow=safe_float(row.get("小单净流入-净额", 0.0)),
                        institutional_net_inflow=safe_float(row.get("大单净流入-净额", 0.0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        return results
    except Exception:
        logger.exception("获取资金流向失败: code=%s", code)
        return []


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
    items = await run_sync(_capital_flow_from_akshare, code)
    return {
        "data": [i.model_dump() for i in items],
        "meta": {"cached": False, "latency_ms": round((time.time() - t0) * 1000)},
    }

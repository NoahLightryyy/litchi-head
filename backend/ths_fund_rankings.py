"""Source-scoped THS net inflow rankings; acquisition time is not quote time."""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from src.data.providers.quotes import SHANGHAI

logger = logging.getLogger(__name__)
router = APIRouter()
ThsPeriod = Literal["latest", "3", "5", "10", "20"]
TTL_SECONDS = 120
SCOPE = "同花顺沪深个股资金净流入降序前50项；仅采用该来源统计，不等同东方财富主力净流入"
DATE_NOTE = "来源未提供数据日期及统计截止日；采集时间不代表行情时间。"


class FundFlowRow(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    code: str
    name: str
    price: float | None
    net_inflow: float


class FundFlowResult(BaseModel):
    source: Literal["ths"] = "ths"
    metric: Literal["net_inflow"] = "net_inflow"
    period: ThsPeriod = "latest"
    unit: Literal["CNY"] = "CNY"
    status: Literal["partial", "unavailable"]
    data: list[FundFlowRow] = []
    data_as_of: None = None
    fetched_at: datetime
    cached: bool = False
    scope: str = SCOPE
    reason: str = DATE_NOTE


def amount(text: str) -> float:
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(万|亿)?", text.strip().replace(",", ""))
    if not match:
        raise ValueError("invalid fund flow amount")
    value = float(Decimal(match[1]) * {None: 1, "万": 10000, "亿": 100000000}[match[2]])
    if not math.isfinite(value):
        raise ValueError("non-finite fund flow amount")
    return value


def parse_page(document: str, now: datetime, period: ThsPeriod = "latest") -> FundFlowResult:
    soup = BeautifulSoup(document, "html.parser")
    active = soup.select_one('thead th.cur a[field="zjjlr"]')
    if active is None:
        raise ValueError("net inflow order is unconfirmed")
    table = active.find_parent("table")
    if table is None:
        raise ValueError("missing funds table")
    labels = [cell.get_text(strip=True) for cell in table.select("thead th")]
    expected = (["序号", "股票代码", "股票简称", "最新价", "涨跌幅", "换手率",
                 "流入资金(元)", "流出资金(元)", "净额(元)", "成交额(元)"]
                if period == "latest" else
                ["序号", "股票代码", "股票简称", "最新价", "阶段涨跌幅", "连续换手率",
                 "资金流入净额(元)"])
    if labels != expected:
        raise ValueError("unexpected funds columns or period")
    net_column = 8 if period == "latest" else 6
    rows: list[FundFlowRow] = []
    seen: set[str] = set()
    for row in table.select("tbody tr"):
        cells = [cell.get_text(strip=True) for cell in row.select("td")]
        if len(cells) != len(expected):
            raise ValueError("malformed funds row")
        code, name = cells[1:3]
        if (cells[0] != str(len(rows) + 1) or not re.fullmatch(r"\d{6}", code)
                or not name or code in seen):
            raise ValueError("invalid ranking identity")
        net = amount(cells[net_column])
        if rows and net > rows[-1].net_inflow:
            raise ValueError("source is not ordered by net inflow")
        price = None if cells[3] in {"--", "-"} else amount(cells[3])
        if price is not None and price <= 0:
            raise ValueError("invalid stock price")
        rows.append(FundFlowRow(code=code, name=name, price=price, net_inflow=net))
        seen.add(code)
    if not rows or len(rows) > 50:
        raise ValueError("empty or oversized source ranking")
    return FundFlowResult(status="partial", data=rows, period=period, fetched_at=now)


async def fetch_page(period: ThsPeriod = "latest") -> str:
    board = "" if period == "latest" else f"board/{period}/"
    url = f"https://data.10jqka.com.cn/funds/ggzjl/{board}field/zjjlr/order/desc/page/1/"
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text


_cache: dict[str, tuple[float, FundFlowResult]] = {}
_locks: dict[str, asyncio.Lock] = {}


@router.get("/fund-flow/ths", response_model=FundFlowResult)
async def fund_flow(period: ThsPeriod = "latest", refresh: bool = False) -> FundFlowResult:
    async with _locks.setdefault(period, asyncio.Lock()):
        cached = _cache.get(period)
        if not refresh and cached and time.monotonic() - cached[0] < TTL_SECONDS:
            return cached[1].model_copy(update={"cached": True})
        try:
            document = await asyncio.wait_for(fetch_page(period), timeout=10)
            result = parse_page(document, datetime.now(SHANGHAI), period)
            _cache[period] = (time.monotonic(), result)
            return result
        except Exception as exc:
            _cache.pop(period, None)
            logger.warning(
                "THS funds ranking failed: period=%s error=%s", period, type(exc).__name__
            )
            return FundFlowResult(
                status="unavailable", period=period, fetched_at=datetime.now(SHANGHAI),
                reason="同花顺资金净流入暂不可用，可重试或查看东方财富主力榜。",
            )

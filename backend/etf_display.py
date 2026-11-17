"""Sina ETF display data, with complete directory snapshots and strict quote identity."""

from __future__ import annotations

import asyncio
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import HttpUrl

from backend.async_utils import BoundedSyncRunner
from backend.etf_contract import EtfCatalog, EtfDetail, EtfIdentity, EtfQuote
from src.data.providers.quotes import SHANGHAI

logger = logging.getLogger(__name__)
BASE = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center."
HEADERS = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"}
PAGE_SIZE = 100
# 来源自报总数可能与实际列表不一致；实际条数低于该比例视为真实截断并拒绝。
MIN_REPORTED_COVERAGE = 0.95
_cache: tuple[float, EtfCatalog] | None = None
_cache_lock = threading.Lock()
_runner = BoundedSyncRunner(max_workers=2, thread_name_prefix="etf-display")


def _count(client: httpx.Client) -> int:
    response = client.get(BASE + "getHQNodeStockCount", params={"node": "etf_hq_fund"})
    response.raise_for_status()
    raw = response.json()
    if not re.fullmatch(r"\d+", str(raw)) or not 1 <= int(raw) <= 5000:
        raise ValueError("ETF directory count invalid")
    return int(raw)


def parse_catalog_page(raw: Any) -> list[EtfIdentity]:
    if not isinstance(raw, list) or len(raw) > PAGE_SIZE:
        raise ValueError("ETF directory page invalid")
    items: list[EtfIdentity] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("ETF directory row invalid")
        symbol = str(row.get("symbol", ""))
        code = str(row.get("code", ""))
        name = row.get("name")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not re.fullmatch(r"(?:sh|sz)\d{6}", symbol)
        ):
            raise ValueError("ETF identity invalid")
        exchange = "SH" if symbol.startswith("sh") else "SZ"
        items.append(EtfIdentity(code=code, symbol=symbol, exchange=exchange, name=name.strip()))
    return items


def fetch_catalog() -> EtfCatalog:
    with httpx.Client(timeout=8, headers=HEADERS) as client:
        count = _count(client)
        pages = math.ceil(count / PAGE_SIZE)

        def page(number: int) -> list[EtfIdentity]:
            response = client.get(
                BASE + "getHQNodeData",
                params={
                    "page": number,
                    "num": PAGE_SIZE,
                    "sort": "symbol",
                    "asc": 1,
                    "node": "etf_hq_fund",
                },
            )
            response.raise_for_status()
            return parse_catalog_page(response.json())

        with ThreadPoolExecutor(max_workers=4) as pool:
            chunks = list(pool.map(page, range(1, pages + 1)))
        # 分页必须连续：出现不满页之后不允许再有数据，否则是中途截断。
        short_page_seen = False
        for chunk in chunks:
            if short_page_seen and chunk:
                raise ValueError("ETF directory truncated")
            if len(chunk) < PAGE_SIZE:
                short_page_seen = True
        items = [item for chunk in chunks for item in chunk]
        symbols = [item.symbol for item in items]
        if (
            not items
            or len(set(symbols)) != len(items)
            or len({item.code for item in items}) != len(items)
        ):
            raise ValueError("ETF directory repeats identities")
        if symbols != sorted(symbols) or page(pages + 1) or _count(client) != count:
            raise ValueError("ETF directory changed during collection")
        # 来源自报总数与实际列表可以有小幅差异（实测新浪报 938、实际 927）；
        # 列表自身一致时接受并披露，差异过大仍按截断拒绝。
        if len(items) < math.ceil(count * MIN_REPORTED_COVERAGE):
            raise ValueError("ETF directory truncated")
        if len(items) != count:
            logger.warning(
                "ETF directory count mismatch accepted: reported=%s actual=%s", count, len(items)
            )
        return EtfCatalog(
            items=tuple(items), fetched_at=datetime.now(SHANGHAI), reported_count=count
        )


def catalog_snapshot() -> EtfCatalog:
    global _cache
    with _cache_lock:
        if _cache and time.monotonic() - _cache[0] < 3600:
            return _cache[1]
        result = fetch_catalog()
        _cache = (time.monotonic(), result)
        return result


def cached_catalog() -> EtfCatalog | None:
    """Return the in-memory catalog without triggering a fetch."""
    cache = _cache  # 不加锁：抓取期间锁被长时间持有，这里只读一次引用
    if cache and time.monotonic() - cache[0] < 3600:
        return cache[1]
    return None


async def get_catalog() -> EtfCatalog:
    return await asyncio.wait_for(_runner.run(catalog_snapshot), timeout=45)


def parse_quote(raw: str, identity: EtfIdentity, now: datetime) -> EtfQuote:
    match = re.fullmatch(r'\s*var\s+hq_str_([a-z]{2}\d{6})="([^"]*)";?\s*', raw)
    if not match or match.group(1) != identity.symbol:
        raise ValueError("ETF quote identity mismatch")
    fields = match.group(2).split(",")
    if len(fields) < 33 or not fields[0].strip():
        raise ValueError("ETF quote row incomplete")
    stamp = datetime.fromisoformat(fields[30] + "T" + fields[31]).replace(tzinfo=SHANGHAI)
    if stamp > now + timedelta(seconds=5):
        raise ValueError("ETF quote timestamp is in the future")
    price, previous = float(fields[3]), float(fields[2])
    if previous <= 0:
        raise ValueError("ETF previous close invalid")

    def optional_price(index: int) -> float | None:
        value = float(fields[index])
        if not math.isfinite(value) or value < 0:
            raise ValueError("ETF OHLC invalid")
        return value if value > 0 else None

    high, low = optional_price(4), optional_price(5)
    if high is not None and low is not None and (low > high or not low <= price <= high):
        raise ValueError("ETF OHLC inconsistent")
    return EtfQuote(
        price=price,
        previous_close=previous,
        change=price - previous,
        change_pct=(price - previous) / previous * 100,
        open=optional_price(1),
        high=high,
        low=low,
        quoted_at=stamp,
        source_name=fields[0].strip(),
    )


def fetch_quote(identity: EtfIdentity) -> EtfQuote:
    response = httpx.get("https://hq.sinajs.cn/list=" + identity.symbol, headers=HEADERS, timeout=8)
    response.raise_for_status()
    return parse_quote(response.text, identity, datetime.now(SHANGHAI))


async def detail(identity: EtfIdentity, catalog: EtfCatalog) -> EtfDetail:
    quote = None
    limitations = ["来源：新浪。价格为场内交易价格，不是基金净值。"]
    try:
        quote = await asyncio.wait_for(_runner.run(fetch_quote, identity), timeout=10)
    except Exception:
        logger.exception("ETF quote unavailable: symbol=%s", identity.symbol)
        limitations.append("ETF行情暂时不可用，可稍后刷新；基金身份仍可查看")
    return EtfDetail(
        identity=identity,
        quote=quote,
        status="ready" if quote else "partial",
        source_url=HttpUrl("https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf"),
        catalog_fetched_at=catalog.fetched_at,
        fetched_at=datetime.now(SHANGHAI),
        limitations=limitations,
    )

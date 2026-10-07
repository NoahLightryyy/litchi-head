"""Unified identity search and explicitly source-scoped gainer discovery."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from backend.async_utils import run_sync
from backend.discovery_rankings import router as rankings_router
from backend.routers.stocks import collector
from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.quotes import SHANGHAI, SinaQuoteSource

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery")
router.include_router(rankings_router)


class SearchHit(BaseModel):
    code: str
    name: str
    kind: Literal["stock", "industry", "concept"]


class SearchResult(BaseModel):
    data: list[SearchHit]
    failed_sources: list[str]
    total: int


class Gainer(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    code: str
    name: str
    price: float
    change_pct: float
    quoted_at: datetime


class GainersResult(BaseModel):
    data: list[Gainer]
    source: Literal["sina"] = "sina"
    scope: str = "新浪沪深A股涨幅榜前20名候选；不含完整北交所市场，不代表全市场热度"
    fetched_at: datetime
    cached: bool = False
    failed_count: int = 0
    error: bool = False


_catalog_cache: tuple[float, list[SearchHit]] | None = None
_gainers_cache: tuple[float, GainersResult] | None = None
_gainers_lock = asyncio.Lock()


def board_catalog() -> list[SearchHit]:
    global _catalog_cache
    if _catalog_cache and time.monotonic() - _catalog_cache[0] < 3600:
        return _catalog_cache[1]
    response = httpx.get("https://quote.eastmoney.com/center/api/sidemenu_new.json", timeout=8)
    response.raise_for_status()
    rows = response.json()["bklist"]
    items = [SearchHit(code=row["code"], name=row["name"],
                       kind="industry" if row["type"] == 2 else "concept")
             for row in rows if row.get("market") == 90 and row.get("type") in (2, 3)
             and re.fullmatch(r"BK\d+", str(row.get("code", "")))]
    if not items:
        raise ValueError("Empty board directory")
    _catalog_cache = (time.monotonic(), items)
    return items


def stock_catalog() -> list[SearchHit]:
    items = collector.get_all_stocks()
    if not items:
        raise ValueError("Stock directory unavailable")
    return [SearchHit(code=s.code, name=s.name, kind="stock") for s in items]


@router.get("/search", response_model=SearchResult)
async def search(q: str = Query("", max_length=80)) -> SearchResult:
    query = q.strip().casefold()
    if not query:
        return SearchResult(data=[], total=0, failed_sources=[])
    outcomes = await asyncio.gather(run_sync(stock_catalog), run_sync(board_catalog),
                                    return_exceptions=True)
    matches: dict[tuple[str, str], SearchHit] = {}
    failed = []
    for name, outcome in zip(("股票目录", "板块目录"), outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning("Discovery source failed: %s %s", name, type(outcome).__name__)
            failed.append(name)
            continue
        for hit in outcome:
            if query in hit.code.casefold() or query in hit.name.casefold():
                matches[(hit.kind, hit.code)] = hit
    ordered = sorted(matches.values(), key=lambda hit: (
        not (query == hit.code.casefold() or query == hit.name.casefold()), hit.kind, hit.code))
    return SearchResult(data=ordered[:100], total=len(ordered), failed_sources=failed)


def fetch_gainers() -> GainersResult:
    response = httpx.get(
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",
        params={"page": "1", "num": "20", "sort": "changepercent", "asc": "0", "node": "hs_a"},
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"}, timeout=8,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty gainer candidates")
    codes = list(dict.fromkeys(str(row.get("code", "")) for row in rows))
    codes = [code for code in codes if re.fullmatch(r"\d{6}", code)][:20]
    if not codes:
        raise ValueError("No valid gainer identities")

    def quote(code: str) -> Gainer | None:
        try:
            result = SinaQuoteSource().fetch(EvidenceRequest(
                capability=EvidenceCapability.REALTIME_QUOTE, stock_code=code))
            if result.status != SourceStatus.SUCCESS_DATA or len(result.items) != 1:
                return None
            item = result.items[0]
            stamp = item.fetched_at
            if item.code != code or item.price <= 0 or stamp is None or stamp.tzinfo is None:
                return None
            if stamp > datetime.now(SHANGHAI):
                return None
            return Gainer(code=code, name=item.name, price=item.price,
                          change_pct=item.change_pct, quoted_at=stamp)
        except Exception:
            logger.exception("Gainer quote failed: %s", code)
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        quotes = [item for item in pool.map(quote, codes) if item is not None]
    quotes.sort(key=lambda item: (-item.change_pct, item.code))
    return GainersResult(data=quotes, fetched_at=datetime.now(SHANGHAI),
                         failed_count=len(codes)-len(quotes), error=not quotes)


@router.get("/gainers", response_model=GainersResult)
async def gainers() -> GainersResult:
    global _gainers_cache
    async with _gainers_lock:
        if _gainers_cache and time.monotonic() - _gainers_cache[0] < 120:
            return _gainers_cache[1].model_copy(update={"cached": True})
        try:
            result = await run_sync(fetch_gainers)
            if result.data:
                _gainers_cache = (time.monotonic(), result)
            return result
        except Exception:
            logger.exception("Gainers unavailable")
            if _gainers_cache:
                return _gainers_cache[1].model_copy(update={"cached": True, "error": True})
            return GainersResult(data=[], fetched_at=datetime.now(SHANGHAI), error=True)

"""Bounded, display-only company news search. Never used by decision evidence."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import math
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

from src.data.providers.cninfo import (
    CNINFO_HEADERS,
    CNINFO_PAGE_SIZE,
    CNINFO_QUERY_URL,
    CNINFO_STOCK_LIST_URL,
    _direct_payload_to_items,
    _lookup_org_id,
    _validated_direct_page_items,
)
from src.data.providers.news import EASTMONEY_SEARCH_URL, USER_AGENT, _parse_datetime

logger = logging.getLogger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE_BUDGET = 10.0
MAX_PAGES = 6
CACHE_SECONDS = 120.0
SourceState = Literal["success", "partial", "empty", "failed"]


class NewsOrigin(BaseModel):
    source: str
    publisher: str
    url: str


class DisplayNewsItem(BaseModel):
    id: str
    title: str
    kind: Literal["announcement", "report", "mention"]
    published_at: str | None
    time_precision: Literal["date", "second", "unknown"]
    association: Literal["official_code", "title_match", "excerpt_match"]
    provenance: list[NewsOrigin]


class NewsSourceState(BaseModel):
    source: Literal["eastmoney", "cninfo"]
    status: SourceState
    matched: int = 0
    scanned: int = 0
    total_candidates: int | None = None
    error_code: str | None = None


class NewsDisplay(BaseModel):
    schema_version: Literal[1] = 1
    symbol: str = Field(pattern=r"^\d{6}$")
    company_name: str | None = None
    status: Literal["ready", "partial", "empty", "failed"]
    start_date: str
    end_date: str
    fetched_at: datetime
    cached: bool = False
    items: list[DisplayNewsItem]
    sources: list[NewsSourceState]
    purpose: Literal["display_only"] = "display_only"


class RawResult(BaseModel):
    source: Literal["eastmoney", "cninfo"]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    name: str | None = None
    total: int | None = None
    error: str | None = None


def clean(value: object) -> str:
    if not isinstance(value, str) or value.strip().lower() in {
        "nan",
        "none",
        "null",
        "inf",
        "infinity",
    }:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def safe_url(value: object) -> str:
    url = clean(value)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        return ""
    return url


def matches(text: str, symbol: str, name: str | None) -> bool:
    return bool(
        (name and name in text) or re.search(rf"(?<![\w])(?:SZ|SH|BJ)?{symbol}(?![\w])", text)
    )


async def fetch_search(client: httpx.AsyncClient, symbol: str) -> RawResult:
    result = RawResult(source="eastmoney")
    try:
        async with asyncio.timeout(SOURCE_BUDGET):
            for page in range(1, MAX_PAGES + 1):
                query = {
                    "uid": "",
                    "keyword": symbol,
                    "type": ["cmsArticleWebOld"],
                    "client": "web",
                    "clientType": "web",
                    "clientVersion": "curr",
                    "param": {
                        "cmsArticleWebOld": {
                            "searchScope": "default",
                            "sort": "default",
                            "pageIndex": page,
                            "pageSize": 50,
                            "preTag": "",
                            "postTag": "",
                        }
                    },
                }
                response = await client.get(
                    EASTMONEY_SEARCH_URL,
                    params={
                        "cb": "callback",
                        "param": json.dumps(query, ensure_ascii=False),
                        "_": "0",
                    },
                    headers={"User-Agent": USER_AGENT, "Referer": "https://so.eastmoney.com/"},
                )
                response.raise_for_status()
                match = re.fullmatch(r"\s*[\w.]+\((.*)\)\s*;?\s*", response.text, re.DOTALL)
                if not match:
                    raise ValueError("invalid JSONP")
                payload = json.loads(match[1])
                total = payload["hitsTotal"]
                if (
                    payload["code"] != 0
                    or isinstance(total, bool)
                    or not isinstance(total, int)
                    or total < 0
                ):
                    raise ValueError("invalid total")
                if result.total is not None and total != result.total:
                    raise ValueError("search changed during pagination")
                result.total = total
                rows = payload["result"]["cmsArticleWebOld"]
                if not isinstance(rows, list) or len(rows) != min(
                    50, max(0, total - (page - 1) * 50)
                ):
                    raise ValueError("incomplete page")
                if any(not isinstance(row, dict) for row in rows):
                    raise ValueError("invalid row")
                result.rows.extend(rows)
                if page * 50 >= total:
                    break
            if result.total is not None and len(result.rows) < result.total:
                result.error = "SEARCH_WINDOW_LIMITED"
    except Exception as exc:
        logger.warning("news display search failed symbol=%s type=%s", symbol, type(exc).__name__)
        result.error = "SOURCE_TIMEOUT" if isinstance(exc, TimeoutError) else "SOURCE_UNAVAILABLE"
    return result


async def fetch_announcements(
    client: httpx.AsyncClient, symbol: str, start: str, end: str
) -> RawResult:
    result = RawResult(source="cninfo")
    try:
        async with asyncio.timeout(SOURCE_BUDGET):
            identity = await client.get(CNINFO_STOCK_LIST_URL, headers=CNINFO_HEADERS)
            identity.raise_for_status()
            stock_payload = identity.json()
            org_id = _lookup_org_id(stock_payload, symbol)
            names = {
                clean(row.get("zwjc"))
                for row in stock_payload["stockList"]
                if row.get("code") == symbol
            }
            names.discard("")
            if len(names) == 1:
                result.name = names.pop()
            page_count = 1
            for page in range(1, MAX_PAGES + 1):
                response = await client.post(
                    CNINFO_QUERY_URL,
                    headers=CNINFO_HEADERS,
                    data={
                        "pageNum": str(page),
                        "pageSize": str(CNINFO_PAGE_SIZE),
                        "column": "szse",
                        "tabName": "fulltext",
                        "plate": "",
                        "stock": f"{symbol},{org_id}",
                        "searchkey": "",
                        "secid": "",
                        "category": "",
                        "trade": "",
                        "seDate": f"{start}~{end}",
                        "sortName": "",
                        "sortType": "",
                        "isHLtitle": "false",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if result.total is None:
                    total = payload["totalAnnouncement"]
                    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                        raise ValueError("invalid total")
                    result.total = total
                    page_count = max(1, math.ceil(total / CNINFO_PAGE_SIZE))
                rows = _validated_direct_page_items(
                    payload, expected_total=result.total, page_number=page, page_count=page_count
                )
                # Exact security identity, independent of title relevance.
                if any(row.get("secCode") != symbol or row.get("orgId") != org_id for row in rows):
                    raise ValueError("announcement identity mismatch")
                result.rows.extend(rows)
                if page >= page_count:
                    break
            if len(result.rows) < (result.total or 0):
                result.error = "SEARCH_WINDOW_LIMITED"
    except Exception as exc:
        logger.warning(
            "news display announcements failed symbol=%s type=%s", symbol, type(exc).__name__
        )
        result.error = "SOURCE_TIMEOUT" if isinstance(exc, TimeoutError) else "SOURCE_UNAVAILABLE"
    return result


def normalize(
    result: RawResult, symbol: str, name: str | None, start: str, now: datetime
) -> tuple[list[DisplayNewsItem], NewsSourceState]:
    items: list[DisplayNewsItem] = []
    rejected = False
    unknown_time = False
    for row in result.rows:
        try:
            title = clean(
                row.get("title") if result.source == "eastmoney" else row.get("announcementTitle")
            )
            if not title:
                rejected = True
                continue
            if result.source == "cninfo":
                # Reuse existing row normalization; pagination completeness is tracked separately.
                announcement = _direct_payload_to_items(
                    {"totalAnnouncement": 1, "announcements": [row]}
                )[0]
                stamp = announcement.published_at
                if stamp > now or stamp.date().isoformat() < start:
                    rejected = True
                    continue
                published = stamp.astimezone(SHANGHAI).date().isoformat()
                precision = "date"
                kind, association = "announcement", "official_code"
                publisher, url = "巨潮资讯", safe_url(announcement.url)
            else:
                excerpt = clean(row.get("content"))
                direct = matches(title, symbol, name)
                if not direct and not matches(excerpt, symbol, name):
                    continue
                kind = "report" if direct else "mention"
                association = "title_match" if direct else "excerpt_match"
                raw_date = clean(row.get("date"))
                stamp = _parse_datetime(raw_date) if raw_date else None
                if stamp and stamp > now:
                    rejected = True
                    continue
                if stamp and stamp.astimezone(SHANGHAI).date().isoformat() < start:
                    continue
                precision = "second" if stamp else "unknown"
                published = stamp.isoformat() if stamp else None
                unknown_time |= stamp is None
                publisher, url = (
                    clean(row.get("mediaName")) or "东方财富搜索",
                    safe_url(row.get("url")),
                )
            if not url:
                rejected = True
                continue
            items.append(
                DisplayNewsItem(
                    id=hashlib.sha256(f"{kind}|{title}|{published}".encode()).hexdigest()[:24],
                    title=title,
                    kind=kind,
                    published_at=published,
                    time_precision=precision,
                    association=association,
                    provenance=[NewsOrigin(source=result.source, publisher=publisher, url=url)],
                )
            )
        except (ValueError, TypeError, KeyError):
            rejected = True
            logger.warning("news display invalid row source=%s symbol=%s", result.source, symbol)
    error = result.error or (
        "INVALID_ROWS_SKIPPED" if rejected else "PUBLICATION_TIME_MISSING" if unknown_time else None
    )
    status: SourceState = "success" if items else "empty"
    if error:
        status = "partial" if items or result.rows else "failed"
    return items, NewsSourceState(
        source=result.source,
        status=status,
        matched=len(items),
        scanned=len(result.rows),
        total_candidates=result.total,
        error_code=error,
    )


async def collect_display(
    symbol: str, days: int, *, client: httpx.AsyncClient | None = None, now: datetime | None = None
) -> NewsDisplay:
    if client is None:
        async with httpx.AsyncClient(
            timeout=3.0, follow_redirects=True, limits=httpx.Limits(max_connections=4)
        ) as live:
            return await collect_display(symbol, days, client=live, now=now)
    now = (now or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    start = (now.date() - timedelta(days=days - 1)).isoformat()
    end = now.date().isoformat()
    search, announcements = await asyncio.gather(
        fetch_search(client, symbol),
        fetch_announcements(client, symbol, start, end),
    )
    merged: dict[str, DisplayNewsItem] = {}
    states: list[NewsSourceState] = []
    for raw in (search, announcements):
        items, state = normalize(raw, symbol, announcements.name, start, now)
        states.append(state)
        for item in items:
            if item.id in merged:
                old = merged[item.id]
                old.provenance.extend(p for p in item.provenance if p not in old.provenance)
            else:
                merged[item.id] = item
    items = sorted(merged.values(), key=lambda item: item.published_at or "", reverse=True)
    limited = any(s.status in {"failed", "partial"} for s in states)
    status = (
        ("partial" if limited else "ready")
        if items
        else (
            "failed"
            if any(s.status == "failed" for s in states)
            else "partial"
            if limited
            else "empty"
        )
    )
    return NewsDisplay(
        symbol=symbol,
        company_name=announcements.name,
        status=status,
        start_date=start,
        end_date=end,
        fetched_at=now,
        items=items,
        sources=states,
    )


class NewsDisplayService:
    """Single-flight, finite in-flight keys, two-minute display cache; no evidence writes."""

    def __init__(
        self, collector: Callable[[str, int], Awaitable[NewsDisplay]] = collect_display
    ) -> None:
        self.collector = collector
        self.cache: dict[tuple[str, int], tuple[float, NewsDisplay]] = {}
        self.pending: dict[tuple[str, int], asyncio.Task[NewsDisplay]] = {}

    async def get(self, symbol: str, days: int) -> NewsDisplay:
        key = (symbol, days)
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1].model_copy(deep=True, update={"cached": True})
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= 4:
                raise RuntimeError("NEWS_BUSY")
            task = asyncio.create_task(self._collect(key))
            self.pending[key] = task
        return await asyncio.shield(task)

    async def _collect(self, key: tuple[str, int]) -> NewsDisplay:
        try:
            async with asyncio.timeout(SOURCE_BUDGET + 2):
                result = await self.collector(*key)
            if result.status != "failed":
                if len(self.cache) >= 64 and key not in self.cache:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (time.monotonic(), result)
            return result
        finally:
            self.pending.pop(key, None)

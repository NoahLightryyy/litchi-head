"""Durable channel news archive. Observed ranges never imply complete coverage."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from src.data.providers.global_news import epoch_time, publication_time, text
from src.data.providers.news import SinaNewsSource, _default_sina_fetcher

logger = logging.getLogger(__name__)
CHANNELS = {
    "caixin": "财新数据通",
    "sina": "新浪财经",
    "eastmoney": "东方财富",
    "cls": "财联社",
    "ths": "同花顺财经",
    "futu": "富途财经",
}


class ArchivedArticle(BaseModel):
    id: str
    channel: str
    title: str
    date: str
    source: str
    url: str
    content: str = ""


class ArchiveCoverage(BaseModel):
    channel: str
    source: str
    count: int = 0
    oldest: str | None = None
    newest: str | None = None
    last_success: str | None = None
    history_status: str = "pending"
    error: str | None = None
    complete: bool = False


class ArchivePage(BaseModel):
    data: list[ArchivedArticle]
    total: int
    page: int
    page_size: int = 100
    start_at: str
    end_at: str
    coverage: list[ArchiveCoverage]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "显示已入库报道；发布时间范围不证明连续覆盖。历史接口停止、重复或失败会保留缺口状态。",
            "文章按渠道保留；转载不是独立验证。长期研究仍需财报、公告和行业证据。",
        ]
    )


def fetch_page(channel: str, cursor: str = "") -> tuple[list[ArchivedArticle], str | None]:
    def get(url: str, params: dict) -> dict:
        response = httpx.get(
            url, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": url}
        )
        response.raise_for_status()
        return response.json()

    if channel == "sina":
        page = int(cursor or 1)
        rows, _ = SinaNewsSource._feed(_default_sina_fetcher(page=page, page_size=100))
        normalized = [
            (
                text(r.get("rich_text")),
                publication_time(r.get("create_time")),
                text(r.get("docurl")),
                "",
            )
            for r in rows
        ]
        next_cursor = str(page + 1) if rows else None
    elif channel == "caixin":
        page = int(cursor or 1)
        payload = get(
            "https://cxdata.caixin.com/api/dataplus/sjtPc/news",
            {"pageNum": page, "pageSize": 100, "showLabels": "true"},
        )
        rows = payload["data"]["data"]
        normalized = [
            (
                text(r.get("summary")) or text(r.get("title")),
                epoch_time(r.get("time")),
                text(r.get("url")),
                "",
            )
            for r in rows
        ]
        next_cursor = str(page + 1) if rows else None
    elif channel == "ths":
        page = int(cursor or 1)
        rows = get(
            "https://news.10jqka.com.cn/tapp/news/push/stock",
            {"page": page, "tag": "", "track": "website"},
        )["data"]["list"]
        normalized = [
            (
                text(r.get("title")) or text(r.get("digest")),
                epoch_time(r.get("rtime")),
                text(r.get("url")),
                text(r.get("digest")),
            )
            for r in rows
        ]
        next_cursor = str(page + 1) if rows else None
    elif channel == "cls":
        params = {
            "app": "CailianpressWeb",
            "category": "",
            "last_time": cursor or str(int(time.time())),
            "os": "web",
            "refresh_type": "1",
            "rn": "20",
            "sv": "8.4.6",
        }
        params["sign"] = hashlib.md5(
            hashlib.sha1(urlencode(params).encode()).hexdigest().encode()
        ).hexdigest()
        payload = get("https://www.cls.cn/v1/roll/get_roll_list", params)
        if payload.get("errno") != 0:
            raise ValueError("CLS response failed")
        rows = payload["data"]["roll_data"]
        normalized = [
            (
                text(r.get("title")) or text(r.get("content")),
                epoch_time(r.get("ctime")),
                f"https://www.cls.cn/detail/{int(r['id'])}",
                text(r.get("content")),
            )
            for r in rows
        ]
        next_cursor = str(min(int(r["ctime"]) for r in rows) - 1) if rows else None
    elif channel == "eastmoney":
        data = get(
            "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
            {
                "client": "web",
                "biz": "web_724",
                "fastColumn": "102",
                "sortEnd": cursor,
                "pageSize": "200",
                "req_trace": "1710315450384",
            },
        )["data"]
        rows = data["fastNewsList"]
        normalized = [
            (
                text(r.get("title")) or text(r.get("summary")),
                publication_time(r.get("showTime")),
                f"https://finance.eastmoney.com/a/{int(r['code'])}.html",
                text(r.get("summary")),
            )
            for r in rows
        ]
        next_cursor = str(data.get("sortEnd") or "") or None
    else:
        params = {"pageSize": "100"}
        if cursor:
            params["seqMark"] = cursor
        data = get("https://news.futunn.com/news-site-api/main/get-flash-list", params)["data"][
            "data"
        ]
        rows = data["news"]
        normalized = [
            (
                text(r.get("title")) or text(r.get("content")),
                epoch_time(r.get("time")),
                text(r.get("detailUrl")),
                text(r.get("content")),
            )
            for r in rows
        ]
        next_cursor = str(data.get("seqMark") or "") if data.get("hasMore") else None
    articles = []
    for title, stamp, url, content in normalized:
        if not title or not stamp:
            continue
        date = datetime.fromisoformat(stamp).astimezone(UTC).isoformat()
        identity = hashlib.sha256(f"{channel}\n{url}\n{title}\n{date}".encode()).hexdigest()
        articles.append(
            ArchivedArticle(
                id=identity,
                channel=channel,
                title=title[:4000],
                date=date,
                source=CHANNELS[channel],
                url=url,
                content=content[:4000],
            )
        )
    if rows and not articles:
        raise ValueError("News page contains no usable dated titles")
    return articles, next_cursor


class NewsArchive:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._schema_lock = Lock()
        self._initialized = False

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        with self._schema_lock:
            if not self._initialized:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY,channel TEXT,"
                    "title TEXT,date TEXT,source TEXT,url TEXT,content TEXT)"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS article_time ON articles(date,channel)")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS channels (channel TEXT PRIMARY KEY,cursor TEXT,"
                    "last_success TEXT,history_status TEXT,error TEXT)"
                )
                self._initialized = True
        return conn

    def store(self, articles: list[ArchivedArticle]) -> int:
        with closing(self.connect()) as conn, conn:
            before = conn.total_changes
            conn.executemany(
                "INSERT OR IGNORE INTO articles VALUES (?,?,?,?,?,?,?)",
                [(a.id, a.channel, a.title, a.date, a.source, a.url, a.content) for a in articles],
            )
            return conn.total_changes - before

    def collect(self, channel: str, pages: int = 3) -> None:
        with closing(self.connect()) as conn:
            state = conn.execute("SELECT * FROM channels WHERE channel=?", (channel,)).fetchone()
        cursor = state["cursor"] if state else ""
        status = state["history_status"] if state else "pending"
        success = state["last_success"] if state else None
        error = None
        try:
            latest, following = fetch_page(channel)
            self.store(latest)
            success = datetime.now(UTC).isoformat()
            if not state or (status == "failed" and not cursor):
                cursor = following
                status = "running" if following else "exhausted"
            if status in {"pending", "running", "failed"}:
                for _ in range(pages):
                    if not cursor:
                        status = "exhausted"
                        break
                    articles, following = fetch_page(channel, cursor)
                    added = self.store(articles)
                    if articles and not added:
                        status = "stalled"
                        break
                    cursor = following
                    status = "running" if following else "exhausted"
                    if (
                        articles
                        and min(a.date for a in articles)
                        < (datetime.now(UTC) - timedelta(days=1095)).isoformat()
                    ):
                        status = "window_limit"
                        break
        except Exception as exc:
            logger.warning("Archive collection failed: %s %s", channel, type(exc).__name__)
            error = f"采集未完成（{type(exc).__name__}），已有记录保留"
            status = "failed"
        with closing(self.connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO channels VALUES (?,?,?,?,?)",
                (channel, cursor, success, status, error),
            )

    def query(
        self,
        *,
        days: int = 7,
        channel: str = "",
        keyword: str = "",
        secondary: str = "",
        page: int = 1,
        page_size: int = 100,
        end: datetime | None = None,
    ) -> ArchivePage:
        end = (end or datetime.now(UTC)).astimezone(UTC)
        start = end - timedelta(days=days)
        params: list = [start.isoformat(), end.isoformat()]
        where = "date>=? AND date<=?"
        if channel:
            where += " AND channel=?"
            params.append(channel)
        if keyword:
            where += " AND instr(title || ' ' || content,?)>0"
            params.append(keyword)
        if secondary:
            where += " AND instr(title || ' ' || content,?)>0"
            params.append(secondary)
        with closing(self.connect()) as conn:
            total = conn.execute(f"SELECT count(*) FROM articles WHERE {where}", params).fetchone()[
                0
            ]
            rows = conn.execute(
                f"SELECT * FROM articles WHERE {where} ORDER BY date DESC,id LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            coverage = []
            for key, label in CHANNELS.items():
                agg = conn.execute(
                    "SELECT count(*),min(date),max(date) FROM articles WHERE channel=?", (key,)
                ).fetchone()
                state = conn.execute("SELECT * FROM channels WHERE channel=?", (key,)).fetchone()
                coverage.append(
                    ArchiveCoverage(
                        channel=key,
                        source=label,
                        count=agg[0],
                        oldest=agg[1],
                        newest=agg[2],
                        last_success=state["last_success"] if state else None,
                        history_status=state["history_status"] if state else "pending",
                        error=state["error"] if state else None,
                    )
                )
        return ArchivePage(
            data=[ArchivedArticle(**dict(row)) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            start_at=start.isoformat(),
            end_at=end.isoformat(),
            coverage=coverage,
        )


archive = NewsArchive(os.getenv("LITCHI_NEWS_ARCHIVE", "data/evidence/news_archive.db"))


def collect_archive() -> None:
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(archive.collect, CHANNELS))


async def run_archive_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(collect_archive)
        except Exception:
            logger.exception("News archive loop failed")
        await asyncio.sleep(300)

"""SQLite WAL rolling store for metadata-only news evidence."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.data.models import NewsItem


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class RollingNewsStoreError(RuntimeError):
    """Raised when rolling news evidence cannot be persisted or trusted."""


class SqliteRollingNewsStore:
    """Durable news metadata and continuous collection coverage."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        retention: timedelta = timedelta(days=3),
        max_collection_gap: timedelta = timedelta(minutes=10),
    ) -> None:
        if retention <= timedelta(0):
            raise ValueError("retention must be positive")
        if max_collection_gap <= timedelta(0):
            raise ValueError("max_collection_gap must be positive")
        self._database_path = Path(database_path)
        self._retention = retention
        self._max_collection_gap = max_collection_gap

    def _connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rolling_news (
                source_id TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                source_name TEXT NOT NULL,
                publisher TEXT NOT NULL,
                url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (source_id, external_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rolling_news_source_published
            ON rolling_news(source_id, published_at)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rolling_news_coverage (
                source_id TEXT PRIMARY KEY,
                continuous_since TEXT NOT NULL,
                last_success_at TEXT NOT NULL
            )
            """
        )
        return connection

    def record_success(
        self,
        *,
        source_id: str,
        items: list[NewsItem],
        collected_at: datetime,
    ) -> None:
        """Atomically store one successful poll and advance/reset coverage."""
        collected_utc = _utc(collected_at)
        cutoff = collected_utc - self._retention
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing = connection.execute(
                        """
                        SELECT continuous_since, last_success_at
                        FROM rolling_news_coverage
                        WHERE source_id = ?
                        """,
                        (source_id,),
                    ).fetchone()
                    oldest_item = min(
                        (
                            _utc(item.published_at)
                            for item in items
                            if item.published_at is not None
                        ),
                        default=collected_utc,
                    )
                    continuous_since = oldest_item
                    if existing is not None:
                        previous_success = datetime.fromisoformat(
                            str(existing["last_success_at"])
                        )
                        if collected_utc - previous_success <= self._max_collection_gap:
                            continuous_since = datetime.fromisoformat(
                                str(existing["continuous_since"])
                            )

                    for item in items:
                        if item.published_at is None:
                            raise RollingNewsStoreError(
                                f"news item lacks published_at: {item.external_id}"
                            )
                        connection.execute(
                            """
                            INSERT INTO rolling_news (
                                source_id, external_id, title, published_at,
                                source_name, publisher, url, content_hash
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(source_id, external_id) DO UPDATE SET
                                title = excluded.title,
                                published_at = excluded.published_at,
                                source_name = excluded.source_name,
                                publisher = excluded.publisher,
                                url = excluded.url,
                                content_hash = excluded.content_hash
                            """,
                            (
                                source_id,
                                item.external_id,
                                item.title,
                                _utc(item.published_at).isoformat(),
                                item.source,
                                item.publisher,
                                item.url,
                                item.content_hash,
                            ),
                        )

                    connection.execute(
                        """
                        INSERT INTO rolling_news_coverage (
                            source_id, continuous_since, last_success_at
                        )
                        VALUES (?, ?, ?)
                        ON CONFLICT(source_id) DO UPDATE SET
                            continuous_since = excluded.continuous_since,
                            last_success_at = excluded.last_success_at
                        """,
                        (
                            source_id,
                            continuous_since.isoformat(),
                            collected_utc.isoformat(),
                        ),
                    )
                    connection.execute(
                        "DELETE FROM rolling_news WHERE published_at < ?",
                        (cutoff.isoformat(),),
                    )
        except RollingNewsStoreError:
            raise
        except sqlite3.Error as exc:
            raise RollingNewsStoreError(
                f"failed to record rolling news: {source_id}"
            ) from exc

    def covers(
        self,
        *,
        source_id: str,
        start_at: datetime,
        end_at: datetime,
    ) -> bool:
        """Return true only for a continuously observed and fresh window."""
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT continuous_since, last_success_at
                    FROM rolling_news_coverage
                    WHERE source_id = ?
                    """,
                    (source_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise RollingNewsStoreError(
                f"failed to read rolling coverage: {source_id}"
            ) from exc
        if row is None:
            return False
        continuous_since = datetime.fromisoformat(str(row["continuous_since"]))
        last_success = datetime.fromisoformat(str(row["last_success_at"]))
        return (
            continuous_since <= _utc(start_at)
            and last_success + self._max_collection_gap >= _utc(end_at)
        )

    def query(
        self,
        *,
        source_id: str,
        stock_code: str,
        stock_name: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[NewsItem]:
        """Query metadata and associate it locally by stock name/code."""
        patterns = [
            value
            for value in (stock_name.strip(), stock_code.strip())
            if value
        ]
        if not patterns:
            return []
        association_sql = " OR ".join("title LIKE ?" for _ in patterns)
        params: list[str] = [
            source_id,
            _utc(start_at).isoformat(),
            _utc(end_at).isoformat(),
            *(f"%{value}%" for value in patterns),
        ]
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    f"""
                    SELECT external_id, title, published_at, source_name,
                           publisher, url, content_hash
                    FROM rolling_news
                    WHERE source_id = ?
                      AND published_at BETWEEN ? AND ?
                      AND ({association_sql})
                    ORDER BY published_at DESC
                    """,
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise RollingNewsStoreError(
                f"failed to query rolling news: {source_id}"
            ) from exc

        items: list[NewsItem] = []
        for row in rows:
            published_at = datetime.fromisoformat(str(row["published_at"]))
            title = str(row["title"])
            reason = (
                "stock_name"
                if stock_name and stock_name in title
                else "stock_code"
            )
            items.append(
                NewsItem(
                    external_id=str(row["external_id"]),
                    code=stock_code,
                    title=title,
                    date=published_at.date().isoformat(),
                    published_at=published_at,
                    source=str(row["source_name"]),
                    source_id=source_id,
                    publisher=str(row["publisher"]),
                    url=str(row["url"]),
                    association_reason=reason,
                    content_hash=str(row["content_hash"]),
                )
            )
        return items


__all__ = [
    "RollingNewsStoreError",
    "SqliteRollingNewsStore",
]

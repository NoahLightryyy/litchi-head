"""Shared runtime for concurrent live + rolling news evidence."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.data.evidence import (
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.evidence_service import DataEvidenceService
from src.data.models import NewsItem
from src.data.news_store import SqliteRollingNewsStore
from src.data.providers.news import EastmoneyNewsSource, SinaRollingFeedCollector

logger = logging.getLogger(__name__)

DEFAULT_NEWS_DATABASE = Path("data/evidence/news.db")
DEFAULT_POLL_SECONDS = 300
NEWS_WINDOW = timedelta(days=3)
NEWS_EVIDENCE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.NEWS,
    min_independent_upstreams=2,
    required_upstream_ids={"eastmoney", "sina"},
)


class RollingNewsSource:
    """Evidence adapter backed by continuously collected Sina metadata."""

    descriptor = SourceDescriptor(
        source_id="sina-finance-feed",
        upstream_id="sina",
        display_name="新浪财经快讯（滚动缓存）",
        capabilities={EvidenceCapability.NEWS},
    )

    def __init__(self, store: SqliteRollingNewsStore) -> None:
        self._store = store

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        if request.capability is not EvidenceCapability.NEWS:
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        if request.start_at is None or request.end_at is None:
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.STALE,
                error_code="rolling_window_required",
                error_message="滚动新闻证据必须指定完整时间窗口",
            )
        if not self._store.covers(
            source_id=self.descriptor.source_id,
            start_at=request.start_at,
            end_at=request.end_at,
        ):
            return SourceResult[NewsItem](
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.STALE,
                error_code="rolling_window_not_fully_covered",
                error_message="新浪滚动缓存尚未连续覆盖请求时间窗口",
            )

        items = self._store.query(
            source_id=self.descriptor.source_id,
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            start_at=request.start_at,
            end_at=request.end_at,
        )
        return SourceResult[NewsItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=(
                SourceStatus.SUCCESS_DATA
                if items
                else SourceStatus.SUCCESS_EMPTY
            ),
            items=items,
        )


class NewsEvidenceRuntime:
    """Own the rolling store, upstream collector and aggregate service."""

    def __init__(
        self,
        store: SqliteRollingNewsStore,
        *,
        collector: SinaRollingFeedCollector | None = None,
    ) -> None:
        self.store = store
        self.collector = collector or SinaRollingFeedCollector()
        registry = EvidenceSourceRegistry()
        registry.register(EastmoneyNewsSource())
        registry.register(RollingNewsSource(store))
        self.service = DataEvidenceService(registry, max_workers=2)

    def ingest_once(self, *, collected_at: datetime | None = None) -> int:
        """Fetch one Sina batch and atomically advance rolling coverage."""
        items = self.collector.collect()
        self.store.record_success(
            source_id=RollingNewsSource.descriptor.source_id,
            items=items,
            collected_at=collected_at or datetime.now(UTC),
        )
        return len(items)


_runtime: NewsEvidenceRuntime | None = None


def get_news_evidence_runtime() -> NewsEvidenceRuntime:
    """Return the process-wide lazy runtime without opening SQLite on import."""
    global _runtime
    if _runtime is None:
        database = Path(
            os.getenv("LITCHI_NEWS_DATABASE", str(DEFAULT_NEWS_DATABASE))
        )
        _runtime = NewsEvidenceRuntime(SqliteRollingNewsStore(database))
    return _runtime


def validate_news_poll_seconds(poll_seconds: int) -> int:
    """Validate the operational polling guard before the app starts serving."""
    if poll_seconds < 60:
        raise ValueError("poll_seconds must be at least 60")
    return poll_seconds


async def run_news_ingestion_loop(
    runtime: NewsEvidenceRuntime,
    *,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
) -> None:
    """Poll immediately and then every interval; failures never advance coverage."""
    validate_news_poll_seconds(poll_seconds)
    while True:
        try:
            count = await asyncio.to_thread(runtime.ingest_once)
            logger.info("新浪滚动新闻采集成功: items=%s", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("新浪滚动新闻采集失败，覆盖窗口未推进")
        await asyncio.sleep(poll_seconds)


__all__ = [
    "DEFAULT_NEWS_DATABASE",
    "DEFAULT_POLL_SECONDS",
    "NEWS_EVIDENCE_POLICY",
    "NEWS_WINDOW",
    "NewsEvidenceRuntime",
    "RollingNewsSource",
    "get_news_evidence_runtime",
    "run_news_ingestion_loop",
    "validate_news_poll_seconds",
]

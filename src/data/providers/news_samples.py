"""Additional channel samples for research, never proof of complete coverage."""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import NewsItem
from src.data.providers.caixin_news import fetch_caixin_news
from src.data.providers.global_news import (
    fetch_cls_hot_news,
    fetch_eastmoney_hot_news,
    fetch_futu_hot_news,
    fetch_sina_hot_news,
    fetch_ths_hot_news,
    publication_time,
    text,
)

logger = logging.getLogger(__name__)
SAMPLE_CHANNELS = (
    ("caixin", "财新数据通", fetch_caixin_news),
    ("sina", "新浪财经", fetch_sina_hot_news),
    ("eastmoney", "东方财富", fetch_eastmoney_hot_news),
    ("cls", "财联社", fetch_cls_hot_news),
    ("ths", "同花顺财经", fetch_ths_hot_news),
    ("futu", "富途财经", fetch_futu_hot_news),
)


class ChannelNewsSample:
    """Match explicit stock name/code; samples cannot satisfy admission policy."""

    def __init__(self, channel: str, label: str, fetcher: Callable[[], pd.DataFrame]) -> None:
        self.descriptor = SourceDescriptor(
            source_id=f"{channel}-latest-sample",
            upstream_id=channel,
            display_name=label,
            capabilities={EvidenceCapability.NEWS},
            discovery_only=True,
        )
        self.fetcher = fetcher

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        if request.capability != EvidenceCapability.NEWS:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        if not request.stock_code or request.start_at is None or request.end_at is None:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        try:
            frame = self.fetcher()
            if not frame.empty and not ({"title", "summary"} & set(frame.columns)):
                raise ValueError("News sample has no title column")
            items: list[NewsItem] = []
            dates: list[datetime] = []
            for _, row in frame.head(100).iterrows():
                title = text(row.get("title")) or text(row.get("summary"))
                stamp = publication_time(row.get("date"))
                if not title or not stamp:
                    continue
                published = datetime.fromisoformat(stamp)
                dates.append(published)
                if not request.start_at <= published <= request.end_at:
                    continue
                content = text(row.get("content"))
                body = title + " " + content
                name_match = bool(request.stock_name and request.stock_name in body)
                code_match = bool(re.search(rf"(?<!\d){re.escape(request.stock_code)}(?!\d)", body))
                if not name_match and not code_match:
                    continue
                url = text(row.get("url"))
                digest = hashlib.sha256(f"{title}\n{stamp}\n{url}".encode()).hexdigest()
                items.append(
                    NewsItem(
                        code=request.stock_code,
                        title=title,
                        date=published.date().isoformat(),
                        published_at=published,
                        source=self.descriptor.display_name,
                        source_id=self.descriptor.source_id,
                        publisher=self.descriptor.display_name,
                        content=content[:2000],
                        url=url,
                        external_id=digest,
                        content_hash=digest,
                        association_reason="stock_name" if name_match else "stock_code",
                    )
                )
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.STALE,
                items=items,
                coverage_start_at=min(dates) if dates else None,
                coverage_end_at=max(dates) if dates else None,
                error_code="latest_sample_only",
                error_message="仅最近快讯样本，未证明连续历史覆盖；转载不算独立核验",
            )
        except Exception:
            logger.exception("Research news channel failed: %s", self.descriptor.source_id)
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="sample_fetch_failed",
                error_message="新闻样本请求失败",
            )

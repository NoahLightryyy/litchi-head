from datetime import UTC, datetime

import pandas as pd

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.models import NewsItem
from src.data.news_context import format_news_context
from src.data.providers.news_samples import ChannelNewsSample


def test_sample_matches_only_target_and_window_and_never_claims_complete():
    frame = pd.DataFrame(
        [
            {"title": "三元基因研发进展", "date": "2026-09-30T10:00:00+08:00"},
            {"title": "920344公告", "date": "2026-09-30T11:00:00+08:00"},
            {"title": "19203440不是代码", "date": "2026-09-30T11:00:00+08:00"},
            {"title": "三元基因旧新闻", "date": "2025-09-30T11:00:00+08:00"},
            {"title": "三元基因无时间", "date": None},
        ]
    )
    source = ChannelNewsSample("test", "测试", lambda: frame)
    request = EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code="920344",
        stock_name="三元基因",
        start_at=datetime(2026, 9, 29, tzinfo=UTC),
        end_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    result = source.fetch(request)
    assert len(result.items) == 2
    assert result.status == SourceStatus.STALE
    assert result.error_code == "latest_sample_only"
    assert source.descriptor.discovery_only
    assert all(n.source_id == "test-latest-sample" for n in result.items)


def test_context_balances_channels_keeps_provenance_and_deduplicates():
    news = [
        NewsItem(code="001246", date="2026-09-30", title=f"甲新闻{i}", source="甲")
        for i in range(50)
    ]
    news += [
        NewsItem(
            code="001246",
            date="2026-09-30",
            title="乙新闻",
            source="乙",
            url="https://example.com/b",
        )
    ]
    news += [
        NewsItem(
            code="001246",
            date="2026-09-30",
            title="乙新闻",
            source="丙",
            url="https://example.com/c",
        )
    ]
    lines = format_news_context(news)
    assert len(lines) == 42
    assert "52 条" in lines[0] and "51 组" in lines[0]
    body = "\n".join(lines)
    assert "https://example.com/b" in body and "https://example.com/c" in body
    assert body.count('"标题": "乙新闻"') == 1
    assert "转载不构成独立验证" in body

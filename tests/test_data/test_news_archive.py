from datetime import UTC, datetime
from unittest.mock import patch

from src.data.news_archive import ArchivedArticle, NewsArchive


def article(key="a", channel="cls"):
    return ArchivedArticle(
        id=key,
        channel=channel,
        title="三元基因研发公告",
        date="2026-10-01T12:00:00+00:00",
        source="财联社",
        url="https://example.com/a",
    )


def test_archive_idempotent_persistent_and_paginated(tmp_path):
    store = NewsArchive(tmp_path / "news.db")
    assert store.store([article()]) == 1
    assert store.store([article()]) == 0
    store.store([article("b", "ths")])
    reopened = NewsArchive(tmp_path / "news.db")
    result = reopened.query(
        days=7, keyword="三元基因", end=datetime(2026, 10, 3, tzinfo=UTC), page_size=1
    )
    assert result.total == 2 and len(result.data) == 1
    assert len(reopened.query(days=1, end=datetime(2026, 10, 3, tzinfo=UTC)).data) == 0
    assert all(not source.complete for source in result.coverage)


def test_repeated_history_stops_without_fabricating_coverage(tmp_path):
    store = NewsArchive(tmp_path / "news.db")
    with patch("src.data.news_archive.fetch_page", return_value=([article()], "cursor")):
        store.collect("cls")
    coverage = store.query(days=1095).coverage
    assert next(s for s in coverage if s.channel == "cls").history_status == "stalled"
    with patch("src.data.news_archive.fetch_page", side_effect=TimeoutError):
        store.collect("cls")
    source = next(s for s in store.query(days=1095).coverage if s.channel == "cls")
    assert source.count == 1 and source.error and source.history_status == "failed"
    assert source.last_success and not source.complete

"""新浪滚动新闻存储的持久化、覆盖窗口与本地关联契约。"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.models import NewsItem
from src.data.news_runtime import RollingNewsSource
from src.data.news_store import SqliteRollingNewsStore


def _item(external_id: str, published_at: datetime, title: str) -> NewsItem:
    return NewsItem(
        external_id=external_id,
        code="",
        title=title,
        date=published_at.date().isoformat(),
        published_at=published_at,
        source="新浪财经快讯",
        source_id="sina-finance-feed",
        publisher="新浪财经",
        association_reason="rolling_feed",
        content_hash=f"hash-{external_id}",
    )


def test_store_survives_restart_and_deduplicates_upstream_id(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)
    database = tmp_path / "news.db"
    first = SqliteRollingNewsStore(database)

    first.record_success(
        source_id="sina-finance-feed",
        items=[_item("1", now - timedelta(minutes=1), "平安银行发布公告")],
        collected_at=now,
    )
    first.record_success(
        source_id="sina-finance-feed",
        items=[_item("1", now - timedelta(minutes=1), "平安银行发布公告")],
        collected_at=now + timedelta(minutes=5),
    )

    restarted = SqliteRollingNewsStore(database)
    items = restarted.query(
        source_id="sina-finance-feed",
        stock_code="000001",
        stock_name="平安银行",
        start_at=now - timedelta(days=3),
        end_at=now + timedelta(minutes=5),
    )

    assert [item.external_id for item in items] == ["1"]


def test_coverage_requires_continuous_success_and_resets_after_gap(
    tmp_path: Path,
) -> None:
    store = SqliteRollingNewsStore(
        tmp_path / "news.db",
        max_collection_gap=timedelta(minutes=10),
    )
    start = datetime(2026, 7, 26, 9, 30, tzinfo=UTC)
    end = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)

    store.record_success(
        source_id="sina-finance-feed",
        items=[_item("oldest", start, "市场快讯")],
        collected_at=start,
    )
    for offset in range(5, 3 * 24 * 60 + 1, 5):
        collected_at = start + timedelta(minutes=offset)
        store.record_success(
            source_id="sina-finance-feed",
            items=[],
            collected_at=collected_at,
        )

    assert store.covers(
        source_id="sina-finance-feed",
        start_at=start,
        end_at=end,
    )

    after_gap = end + timedelta(minutes=30)
    store.record_success(
        source_id="sina-finance-feed",
        items=[],
        collected_at=after_gap,
    )

    assert not store.covers(
        source_id="sina-finance-feed",
        start_at=start,
        end_at=after_gap,
    )


def test_store_prunes_items_older_than_three_days(tmp_path: Path) -> None:
    now = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)
    store = SqliteRollingNewsStore(
        tmp_path / "news.db",
        retention=timedelta(days=3),
    )

    store.record_success(
        source_id="sina-finance-feed",
        items=[
            _item("expired", now - timedelta(days=3, seconds=1), "平安银行旧闻"),
            _item("kept", now - timedelta(days=3), "平安银行新近新闻"),
        ],
        collected_at=now,
    )

    items = store.query(
        source_id="sina-finance-feed",
        stock_code="000001",
        stock_name="平安银行",
        start_at=now - timedelta(days=4),
        end_at=now,
    )
    assert [item.external_id for item in items] == ["kept"]


def test_rolling_source_is_stale_until_full_window_is_observed(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)
    store = SqliteRollingNewsStore(tmp_path / "news.db")
    store.record_success(
        source_id="sina-finance-feed",
        items=[_item("1", now - timedelta(minutes=1), "平安银行发布公告")],
        collected_at=now,
    )

    result = RollingNewsSource(store).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.NEWS,
            stock_code="000001",
            stock_name="平安银行",
            start_at=now - timedelta(days=3),
            end_at=now,
        )
    )

    assert result.status is SourceStatus.STALE
    assert result.error_code == "rolling_window_not_fully_covered"


def test_rolling_source_returns_locally_associated_metadata(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 7, 29, 9, 30, tzinfo=UTC)
    store = SqliteRollingNewsStore(
        tmp_path / "news.db",
        max_collection_gap=timedelta(days=4),
    )
    store.record_success(
        source_id="sina-finance-feed",
        items=[
            _item("match", now - timedelta(days=3), "平安银行发布公告"),
            _item("other", now - timedelta(days=2), "其他公司新闻"),
        ],
        collected_at=now,
    )

    result = RollingNewsSource(store).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.NEWS,
            stock_code="000001",
            stock_name="平安银行",
            start_at=now - timedelta(days=3),
            end_at=now,
        )
    )

    assert result.status is SourceStatus.SUCCESS_DATA
    assert [item.external_id for item in result.items] == ["match"]
    assert result.items[0].content == ""


def test_out_of_order_poll_does_not_regress_coverage(tmp_path: Path) -> None:
    store = SqliteRollingNewsStore(
        tmp_path / "news.db",
        max_collection_gap=timedelta(minutes=10),
    )
    start = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
    latest = start + timedelta(minutes=10)
    store.record_success(
        source_id="sina-finance-feed",
        items=[_item("latest", latest, "平安银行最新消息")],
        collected_at=latest,
    )
    store.record_success(
        source_id="sina-finance-feed",
        items=[_item("late-writer", start, "平安银行较早消息")],
        collected_at=start,
    )

    assert store.covers(
        source_id="sina-finance-feed",
        start_at=latest,
        end_at=latest,
    )

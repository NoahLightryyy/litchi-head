"""Homepage market-index multi-source aggregation contract."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.data.collector import HealthStats
from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.index_quote_runtime import IndexQuoteService
from src.data.models import StockQuote
from src.data.providers.quotes import (
    EastmoneyIndexQuoteSource,
    SinaIndexQuoteSource,
    _eastmoney_index_secid,
    _sina_index_symbol,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 27, 14, 11, 23, tzinfo=SHANGHAI)
INDEX_CODES = ("000001", "399001", "399006")


def _quote(
    code: str,
    *,
    price: float = 3943.53,
    fetched_at: datetime = NOW,
) -> StockQuote:
    return StockQuote(
        code=code,
        name={
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
        }[code],
        price=price,
        change=31.01,
        change_pct=0.79,
        volume=100,
        fetched_at=fetched_at,
    )


def _result(
    source_id: str,
    upstream_id: str,
    code: str,
    *,
    status: SourceStatus = SourceStatus.SUCCESS_DATA,
    price: float = 3943.53,
    fetched_at: datetime = NOW,
) -> SourceResult[StockQuote]:
    return SourceResult(
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.MARKET_INDEX,
        status=status,
        items=[_quote(code, price=price, fetched_at=fetched_at)]
        if status is SourceStatus.SUCCESS_DATA
        else [],
        error_code="upstream_failed" if status is SourceStatus.FAILED else None,
        error_message="timeout" if status is SourceStatus.FAILED else None,
    )


class StubIndexSource:
    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        results: dict[str, SourceResult[StockQuote]],
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.MARKET_INDEX},
        )
        self._results = results

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        return self._results[request.stock_code]


def _source(
    source_id: str,
    upstream_id: str,
    *,
    status_by_code: dict[str, SourceStatus] | None = None,
    price_by_code: dict[str, float] | None = None,
) -> StubIndexSource:
    statuses = status_by_code or {}
    prices = price_by_code or {}
    return StubIndexSource(
        source_id,
        upstream_id,
        {
            code: _result(
                source_id,
                upstream_id,
                code,
                status=statuses.get(code, SourceStatus.SUCCESS_DATA),
                price=prices.get(code, 3943.53),
            )
            for code in INDEX_CODES
        },
    )


def _service(
    eastmoney: StubIndexSource,
    sina: StubIndexSource,
    *,
    health_stats: HealthStats | None = None,
) -> IndexQuoteService:
    return IndexQuoteService(
        sources=(eastmoney, sina),
        now_provider=lambda: NOW,
        health_stats=health_stats or HealthStats(),
    )


def test_index_symbol_mapping_does_not_treat_shanghai_index_as_sz_stock() -> None:
    assert _eastmoney_index_secid("000001") == "1.000001"
    assert _eastmoney_index_secid("399001") == "0.399001"
    assert _eastmoney_index_secid("399006") == "0.399006"
    assert _sina_index_symbol("000001") == "sh000001"
    assert _sina_index_symbol("399001") == "sz399001"
    assert _sina_index_symbol("399006") == "sz399006"


def test_eastmoney_index_source_parses_exchange_timestamp() -> None:
    source = EastmoneyIndexQuoteSource(fetcher=lambda code: {"data": {
        "f57": code,
        "f58": "上证指数",
        "f43": 394353,
        "f44": 394623,
        "f45": 390931,
        "f46": 391189,
        "f47": 4304003,
        "f48": 841856038642,
        "f60": 391252,
        "f86": int(NOW.timestamp()),
        "f169": 3101,
        "f170": 79,
    }})

    result = source.fetch(EvidenceRequest(
        capability=EvidenceCapability.MARKET_INDEX,
        stock_code="000001",
    ))

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 3943.53
    assert result.items[0].fetched_at == NOW


def test_sina_index_source_validates_index_symbol() -> None:
    fields = [
        "上证指数", "3911.8908", "3912.5235", "3943.5296", "3946.2303",
        "3909.3122", "0", "0", "430400333", "841856038642",
        *("0" for _ in range(20)), "2026-08-27", "14:11:23", "00",
    ]
    source = SinaIndexQuoteSource(
        fetcher=lambda code: f'var hq_str_sh{code}="{",".join(fields)}";',
    )

    result = source.fetch(EvidenceRequest(
        capability=EvidenceCapability.MARKET_INDEX,
        stock_code="000001",
    ))

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 3943.5296
    assert result.items[0].fetched_at == NOW


def test_two_aligned_sources_produce_complete_indices() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina"),
    ).collect()

    assert result.status == "success"
    assert [item.code for item in result.quotes] == list(INDEX_CODES)
    assert all(item.source_count == 2 for item in result.quotes)
    assert len(result.source_diagnostics) == 6


def test_one_failed_source_returns_partial_with_usable_quotes() -> None:
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina", status_by_code=failed),
    ).collect()

    assert result.status == "partial"
    assert len(result.quotes) == 3
    assert all(item.source_count == 1 for item in result.quotes)
    assert result.failed_sources == ["sina"]
    assert {item.code for item in result.limitations} == {"INDEX_SINGLE_SOURCE"}


def test_one_index_conflict_is_displayed_with_explicit_limitation() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source(
            "sina-index",
            "sina",
            price_by_code={"399001": 3943.55},
        ),
    ).collect()

    assert result.status == "partial"
    assert [item.code for item in result.quotes] == list(INDEX_CODES)
    assert result.quotes[1].source_count == 1
    assert result.quotes[1].display_source == "sina"
    assert result.quotes[1].price == 3943.55
    assert result.missing_codes == []
    assert any(item.code == "INDEX_PRICE_CONFLICT" for item in result.limitations)
    conflicted = [
        item for item in result.source_diagnostics
        if item.index_code == "399001"
    ]
    assert {item.status for item in conflicted} == {SourceStatus.CONFLICTED}


def test_all_indices_conflicted_still_display_individually_valid_source() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source(
            "sina-index",
            "sina",
            price_by_code={code: 3943.55 for code in INDEX_CODES},
        ),
    ).collect()

    assert result.status == "partial"
    assert result.error_code is None
    assert len(result.quotes) == 3
    assert all(item.source_count == 1 for item in result.quotes)
    assert result.failed_sources == ["eastmoney", "sina"]


def test_recent_accepted_cache_is_stale_when_both_sources_fail() -> None:
    eastmoney = _source("eastmoney-index", "eastmoney")
    sina = _source("sina-index", "sina")
    service = _service(eastmoney, sina)
    assert service.collect().status == "success"

    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    eastmoney._results = _source(
        "eastmoney-index", "eastmoney", status_by_code=failed,
    )._results
    sina._results = _source(
        "sina-index", "sina", status_by_code=failed,
    )._results
    service._now_provider = lambda: NOW + timedelta(seconds=20)

    result = service.collect()

    assert result.status == "stale"
    assert len(result.quotes) == 3
    assert all(item.cached for item in result.quotes)


def test_all_sources_failed_without_cache_returns_failed() -> None:
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney", status_by_code=failed),
        _source("sina-index", "sina", status_by_code=failed),
    ).collect()

    assert result.status == "failed"
    assert result.error_code == "MARKET_INDICES_FAILED"
    assert result.quotes == []


def test_successful_empty_sources_return_empty_not_failed() -> None:
    empty = {code: SourceStatus.SUCCESS_EMPTY for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney", status_by_code=empty),
        _source("sina-index", "sina", status_by_code=empty),
    ).collect()

    assert result.status == "empty"
    assert result.quotes == []


def test_source_health_records_failure_separately_from_success() -> None:
    stats = HealthStats()
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}

    _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina", status_by_code=failed),
        health_stats=stats,
    ).collect()

    snapshot = stats.snapshot()
    assert snapshot["market_index:eastmoney"]["success"] == 3
    assert snapshot["market_index:sina"]["failures"] == 3


def test_mixed_source_health_recovers_only_after_complete_successful_batch() -> None:
    stats = HealthStats()
    eastmoney = _source("eastmoney-index", "eastmoney")
    sina = _source("sina-index", "sina", price_by_code={"000001": 4000})
    service = _service(eastmoney, sina, health_stats=stats)
    service.collect()
    snapshot = stats.snapshot()
    assert snapshot["market_index:sina"]["current_status"] == "failed"
    assert snapshot["market_index:sina"]["last_error"] == "来源数据冲突"
    # Two later successful indices must not clear the first index's conflict.
    assert snapshot["market_index:sina"]["success"] == 2
    sina._results = _source("sina-index", "sina")._results
    service.collect()
    snapshot = stats.snapshot()
    assert snapshot["market_index:sina"]["failures"] == 1
    assert snapshot["market_index:sina"]["current_status"] == "healthy"
    assert snapshot["market_index:sina"]["last_error_code"] is None
    assert snapshot["__summary__"]["failing_endpoints"] == 0


def test_partial_empty_source_is_not_healthy_but_peer_quotes_are_displayed() -> None:
    stats = HealthStats()
    service = _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina", status_by_code={"000001": SourceStatus.SUCCESS_EMPTY}),
        health_stats=stats,
    )
    result = service.collect()
    assert len(result.quotes) == 3
    assert result.status == "partial"
    assert stats.snapshot()["market_index:sina"]["current_status"] == "empty"


def test_invalid_peer_cannot_hide_valid_single_source_quote() -> None:
    eastmoney = _source("eastmoney-index", "eastmoney")
    eastmoney._results["000001"].items[0].fetched_at = None
    result = _service(eastmoney, _source("sina-index", "sina")).collect()
    assert len(result.quotes) == 3
    assert result.quotes[0].display_source == "sina"
    assert result.quotes[0].source_count == 1
    assert result.source_diagnostics[0].error_code == "index_quote_invalid"


def test_time_conflict_displays_latest_source_without_caching_consensus() -> None:
    eastmoney = _source("eastmoney-index", "eastmoney")
    sina = _source("sina-index", "sina")
    for result in sina._results.values():
        result.items[0].fetched_at = NOW + timedelta(seconds=4)
    service = _service(eastmoney, sina)
    result = service.collect()
    assert result.status == "partial"
    assert all(quote.display_source == "sina" for quote in result.quotes)
    assert all(quote.source_count == 1 for quote in result.quotes)
    assert service._cache == {}
    assert {item.code for item in result.limitations} == {"INDEX_TIMESTAMP_CONFLICT"}


def test_overlapping_index_collections_publish_by_start_order() -> None:
    stats = HealthStats()
    service = _service(
        _source("eastmoney-index", "eastmoney"), _source("sina-index", "sina"),
        health_stats=stats,
    )
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    old_data = _service(
        _source("eastmoney-index", "eastmoney", status_by_code=failed),
        _source("sina-index", "sina", status_by_code=failed),
    )._collect_all()
    new_data = service._collect_all()
    entered = Event()
    release = Event()

    def fetch():
        if not entered.is_set():
            entered.set()
            assert release.wait(3)
            return old_data
        return new_data

    with patch.object(service, "_collect_all", side_effect=fetch):
        with ThreadPoolExecutor(max_workers=1) as pool:
            old = pool.submit(service.collect)
            try:
                assert entered.wait(3)
                assert service.collect().status == "success"
            finally:
                release.set()
            old.result(timeout=3)
    snapshot = stats.snapshot()
    assert snapshot["__summary__"]["failing_endpoints"] == 0
    assert snapshot["__summary__"]["total_failures"] == 6
    assert snapshot["market_index:sina"]["current_status"] == "healthy"


def test_closed_session_alignment_preserves_intraday_and_price_checks() -> None:
    """Real holiday timestamps agree by completed session, never by date alone."""
    cases = [
        # now, eastmoney time, sina time, price difference, expected limitation
        ("2026-10-06T12:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, None),
        ("2026-09-30T17:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, None),
        ("2026-10-03T12:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T07:00:03+00:00", 0.0, None),
        ("2026-10-08T08:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, None),
        ("2026-10-08T09:15:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-09-30T12:00:00+08:00", "2026-09-30T11:30:00+08:00",
         "2026-09-30T11:31:00+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-09-30T14:00:00+08:00", "2026-09-30T13:59:00+08:00",
         "2026-09-30T13:59:04+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-10-06T12:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-29T15:00:03+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-10-08T17:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-10-06T12:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T14:59:59+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-09-30T15:01:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2027-01-02T12:00:00+08:00", "2026-12-31T16:12:00+08:00",
         "2026-12-31T15:00:03+08:00", 0.0, "INDEX_TIMESTAMP_CONFLICT"),
        ("2026-10-06T12:00:00+08:00", "2026-09-30T16:12:00+08:00",
         "2026-09-30T15:00:03+08:00", 0.02, "INDEX_PRICE_CONFLICT"),
    ]
    for current, east_time, sina_time, price_diff, limitation in cases:
        health = HealthStats()
        sources = tuple(
            StubIndexSource(upstream, upstream, {
                code: _result(upstream, upstream, code,
                              fetched_at=datetime.fromisoformat(stamp),
                              price=3943.53 + difference)
                for code in INDEX_CODES
            })
            for upstream, stamp, difference in (
                ("eastmoney", east_time, 0.0), ("sina", sina_time, price_diff)
            )
        )
        result = IndexQuoteService(
            sources=sources, now_provider=lambda: datetime.fromisoformat(current),
            health_stats=health,
        ).collect()
        assert {item.code for item in result.limitations} == (
            {limitation} if limitation else set()
        ), (current, east_time, sina_time, price_diff)
        assert result.status == ("partial" if limitation else "success")
        assert all(q.source_count == (1 if limitation else 2) for q in result.quotes)
        assert all(d.status == (SourceStatus.CONFLICTED if limitation
                               else SourceStatus.SUCCESS_DATA)
                   for d in result.source_diagnostics)

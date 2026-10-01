"""Identity resolution must not depend on downloading the entire stock universe."""

from unittest.mock import patch

import pytest

from backend import stock_identity as identity
from src.data.evidence import EvidenceCapability, SourceResult, SourceStatus
from src.data.models import StockQuote


@pytest.fixture(autouse=True)
def empty_cache():
    identity._cache.clear()
    yield
    identity._cache.clear()


def result(code: str = "300199", name: str = "翰宇药业") -> SourceResult[StockQuote]:
    return SourceResult(
        source_id="sina", upstream_id="sina",
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.SUCCESS_DATA,
        items=[StockQuote(code=code, name=name, price=23.92, change=0, change_pct=0, volume=1)],
    )


def test_single_symbol_query_and_cache_never_fetch_whole_market():
    with (
        patch.object(identity.SinaQuoteSource, "fetch", return_value=result()) as fetch,
        patch.object(identity.EastmoneyQuoteSource, "fetch") as fallback,
        patch("src.data.collector.DataCollector.get_all_stocks") as all_stocks,
    ):
        assert identity.resolve_stock_name("300199") == "翰宇药业"
        assert identity.resolve_stock_name("300199") == "翰宇药业"
    assert fetch.call_count == 1
    assert fetch.call_args.args[0].stock_code == "300199"
    fallback.assert_not_called()
    all_stocks.assert_not_called()


@pytest.mark.parametrize("bad", [result("000001"), result(name="nan"), result(name="300199")])
def test_bad_identity_is_not_cached_or_forwarded(bad):
    with (
        patch.object(identity.SinaQuoteSource, "fetch", return_value=bad),
        patch.object(identity.EastmoneyQuoteSource, "fetch", return_value=bad),
    ):
        assert identity.resolve_stock_name("300199") == ""
    assert not identity._cache


def test_failed_source_uses_existing_other_adapter():
    failed = SourceResult(
        source_id="sina", upstream_id="sina", capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.FAILED, error_message="timeout",
    )
    with (
        patch.object(identity.SinaQuoteSource, "fetch", return_value=failed),
        patch.object(identity.EastmoneyQuoteSource, "fetch", return_value=result()),
    ):
        assert identity.resolve_stock_name("300199") == "翰宇药业"


def test_saturated_lookup_does_not_queue_unbounded_work():
    for _ in range(4):
        assert identity._slots.acquire(blocking=False)
    try:
        with patch.object(identity.SinaQuoteSource, "fetch") as fetch:
            assert identity.resolve_stock_name("300199") == ""
            fetch.assert_not_called()
    finally:
        for _ in range(4):
            identity._slots.release()

from concurrent.futures import wait
from datetime import datetime, timedelta
from threading import Event
from time import monotonic
from unittest.mock import patch

import pytest

import backend.quote_display as display
from backend.quote_display import get_display_quote
from src.data.evidence import EvidenceCapability, SourceResult, SourceStatus
from src.data.models import StockQuote
from src.data.providers.quotes import SHANGHAI


def result(source, *, failed=False, **changes):
    return SourceResult(
        source_id=f"direct-{source}-quote",
        upstream_id=source,
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.FAILED if failed else SourceStatus.SUCCESS_DATA,
        error_message="offline" if failed else None,
        items=[]
        if failed
        else [
            StockQuote(
                **{
                    "code": "920344",
                    "name": "三元基因",
                    "price": 24.35,
                    "change": 3.32,
                    "change_pct": 15.79,
                    "volume": 13381057,
                    "fetched_at": datetime(2026, 9, 30, 15, 30, tzinfo=SHANGHAI),
                    **changes,
                }
            )
        ],
    )


@pytest.fixture(autouse=True)
def no_live_tencent():
    # Keep all tests offline and drain unfinished fake fetches before unpatching.
    with (
        patch("httpx.get", side_effect=AssertionError("No network in unit tests")) as network,
        patch(
            "backend.quote_display.TencentDisplayQuoteSource.fetch",
            return_value=result("tencent", failed=True),
        ),
    ):
        yield
        with display._pending_lock:
            pending = list(display._pending.values())
        wait(pending, timeout=1)
        with display._pending_lock:
            display._pending.clear()
        network.assert_not_called()


def test_bulk_failure_does_not_block_single_quote():
    with (
        patch(
            "backend.quote_display.EastmoneyQuoteSource.fetch",
            return_value=result("eastmoney", failed=True),
        ),
        patch("backend.quote_display.SinaQuoteSource.fetch", return_value=result("sina")),
    ):
        quote = get_display_quote("920344")
    assert quote is not None and quote.name == "三元基因"
    assert quote.source == "sina" and quote.fetched_at.day == 30
    assert quote.market_cap is None and quote.fund_flow is None


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "000001"},
        {"name": " "},
        {"price": 0},
        {"fetched_at": None},
        {"fetched_at": datetime.now(SHANGHAI) + timedelta(days=1)},
    ],
)
def test_invalid_display_data_is_not_published(changes):
    with (
        patch(
            "backend.quote_display.EastmoneyQuoteSource.fetch",
            return_value=result("eastmoney", **changes),
        ),
        patch(
            "backend.quote_display.SinaQuoteSource.fetch", return_value=result("sina", failed=True)
        ),
    ):
        assert get_display_quote("920344") is None


def test_two_failed_sources_do_not_hide_available_existing_tencent_snapshot():
    with (
        patch(
            "backend.quote_display.EastmoneyQuoteSource.fetch",
            return_value=result("eastmoney", failed=True),
        ),
        patch("backend.quote_display.SinaQuoteSource.fetch", side_effect=RuntimeError("offline")),
        patch(
            "backend.quote_display.TencentDisplayQuoteSource.fetch", return_value=result("tencent")
        ),
    ):
        quote = get_display_quote("920344")
    assert quote is not None and quote.source == "tencent"
    assert quote.verification_status == "single_source"


def test_slow_primary_does_not_block_fast_backup_or_spawn_duplicate_work():
    release = Event()

    def slow(_):
        release.wait(1)
        return result("eastmoney", failed=True)

    with (
        patch("backend.quote_display.EastmoneyQuoteSource.fetch", side_effect=slow) as primary,
        patch("backend.quote_display.SinaQuoteSource.fetch", return_value=result("sina")),
    ):
        try:
            started = monotonic()
            assert get_display_quote("920344") is not None
            assert get_display_quote("920344") is not None
            assert monotonic() - started < 0.5
            assert primary.call_count == 1
        finally:
            release.set()
            with display._pending_lock:
                pending = list(display._pending.values())
            wait(pending, timeout=1)


def test_all_slow_sources_respect_response_budget_and_global_inflight_bound():
    release = Event()

    def slow(_):
        release.wait(1)
        return result("eastmoney", failed=True)

    with (
        patch("backend.quote_display.EastmoneyQuoteSource.fetch", side_effect=slow),
        patch("backend.quote_display.SinaQuoteSource.fetch", side_effect=slow),
        patch("backend.quote_display.TencentDisplayQuoteSource.fetch", side_effect=slow),
        patch("backend.quote_display.DISPLAY_QUOTE_BUDGET_SECONDS", 0.02),
    ):
        try:
            start = monotonic()
            assert get_display_quote("002885") is None
            assert get_display_quote("300750") is None
            assert get_display_quote("688648") is None
            assert monotonic() - start < 0.3
            assert len(display._pending) <= display.MAX_PENDING_QUOTES
        finally:
            release.set()
            with display._pending_lock:
                pending = list(display._pending.values())
            wait(pending, timeout=1)


def test_concurrent_symbols_wait_for_a_slot_instead_of_becoming_false_empty():
    from concurrent.futures import ThreadPoolExecutor
    from time import sleep

    def unavailable(request):
        sleep(0.03)
        return result("eastmoney", failed=True)

    def available(request):
        sleep(0.03)
        return result("tencent", code=request.stock_code)

    with (
        patch("backend.quote_display.EastmoneyQuoteSource.fetch", side_effect=unavailable),
        patch("backend.quote_display.SinaQuoteSource.fetch", side_effect=unavailable),
        patch("backend.quote_display.TencentDisplayQuoteSource.fetch", side_effect=available),
    ):
        with ThreadPoolExecutor(max_workers=10) as clients:
            codes = [f"{2880 + i:06d}" for i in range(10)]
            quotes = list(clients.map(get_display_quote, codes))
    assert [q.code if q else None for q in quotes] == codes

"""Board snapshot pagination, provenance, caching and failure protection."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest

from src.data.providers.eastmoney_boards import EastmoneyBoardSnapshots


def row(number: int = 0) -> dict:
    return {"f12": f"BK{number:04d}", "f13": 90, "f14": f"board{number}",
            "f3": 1.23, "f62": 2500.0, "f124": 1788507572}


def reply(rows: list[dict], total: int | None = None) -> httpx.Response:
    return httpx.Response(200, json={"rc": 0, "data": {
        "total": len(rows) if total is None else total, "diff": rows,
    }})


def test_complete_pages_preserve_identity_values_and_timestamp() -> None:
    calls = []
    def transport(request):
        calls.append(request)
        assert request.url.host == "push2delay.eastmoney.com"
        assert request.url.params["fs"] == "m:90 t:2 f:!50"
        assert request.url.params["fltt"] == "2"
        assert request.extensions["timeout"]["read"] <= 3
        if len(calls) == 1:
            return reply([row(i) for i in range(100)], 101)
        return reply([row(100)], 101)
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    result = service.fetch("industry")
    assert len(result.quotes) == 101
    assert result.quotes[0].change_pct == 1.23
    assert result.quotes[0].fund_flow == 2500.0
    assert result.quotes[0].as_of.isoformat() == "2026-09-04T15:39:32+08:00"
    assert result.source == "eastmoney" and result.possibly_delayed
    assert not result.cached
    assert service.fetch("industry").cached
    assert len(calls) == 2


@pytest.mark.parametrize("patch", [
    {"f13": 1}, {"f12": "000001"}, {"f12": ""}, {"f14": " "},
    {"f124": None}, {"f124": True}, {"f3": "-"}, {"f3": "Infinity"},
    {"f62": "nan"},
])
def test_invalid_identity_or_values_fail_instead_of_generating_data(patch) -> None:
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(
        lambda _: reply([{**row(), **patch}]),
    ))
    with pytest.raises((ValueError, OverflowError)):
        service.fetch("industry")


def test_missing_fund_flow_is_null_not_zero() -> None:
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(
        lambda _: reply([{**row(), "f62": "-"}]),
    ))
    assert service.fetch("concept").quotes[0].fund_flow is None


@pytest.mark.parametrize("second", [
    lambda: reply([row(0)], 101),  # Duplicate ID across pages.
    lambda: reply([], 101),  # Truncated final page.
    lambda: reply([row(100)], 102),  # Moving total, not a complete snapshot.
    lambda: httpx.Response(503),
])
def test_incomplete_snapshot_is_never_cached_or_returned(second) -> None:
    calls = 0
    def transport(_):
        nonlocal calls
        calls += 1
        return reply([row(i) for i in range(100)], 101) if calls % 2 else second()
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    for _ in range(2):
        with pytest.raises((ValueError, httpx.HTTPError)):
            service.fetch("industry")
    assert calls == 4


def test_expired_cache_does_not_hide_network_failure_or_retry_it() -> None:
    clock = [0.0]
    calls = 0
    def transport(request):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise httpx.ReadTimeout("offline", request=request)
        return reply([row()])
    service = EastmoneyBoardSnapshots(
        transport=httpx.MockTransport(transport), clock=lambda: clock[0],
    )
    service.fetch("industry")
    clock[0] = 29.9
    assert service.fetch("industry").cached
    clock[0] = 30
    with pytest.raises(httpx.ReadTimeout):
        service.fetch("industry")
    assert calls == 2


def test_pagination_has_one_total_deadline() -> None:
    clock = [0.0]
    calls = 0
    def transport(_):
        nonlocal calls
        calls += 1
        clock[0] += 5
        return reply([row(i) for i in range((calls-1)*100, calls*100)], 300)
    service = EastmoneyBoardSnapshots(
        transport=httpx.MockTransport(transport), clock=lambda: clock[0],
    )
    with pytest.raises(TimeoutError):
        service.fetch("industry")
    assert calls == 2


def test_concurrent_callers_share_one_fetch() -> None:
    entered, release = Event(), Event()
    calls = 0
    def transport(_):
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(2)
        return reply([row()])
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(service.fetch, "industry") for _ in range(4)]
        assert entered.wait(2)
        release.set()
        results = [f.result() for f in futures]
    assert calls == 1
    assert sum(result.cached for result in results) == 3

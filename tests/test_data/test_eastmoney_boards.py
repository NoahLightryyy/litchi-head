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


def member_row(number: int = 0) -> dict:
    return {
        "f2": 12.34, "f3": 2.5, "f12": f"{number:06d}", "f13": number % 2,
        "f14": f"stock{number}", "f62": 125_000_000.0, "f124": 1788507572,
    }


def test_complete_pages_preserve_identity_values_and_timestamp() -> None:
    calls = []
    def transport(request):
        calls.append(request)
        assert request.url.host == "push2delay.eastmoney.com"
        assert request.url.params["fs"] == "m:90 t:2 f:!50"
        assert request.url.params["fltt"] == "2"
        assert request.url.params["fid"] == "f3"
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


def test_members_use_board_filter_and_complete_pagination() -> None:
    calls = []
    def transport(request):
        calls.append(request)
        assert request.url.host == "push2delay.eastmoney.com"
        assert request.url.params["fs"] == "b:BK1629 f:!50"
        assert request.url.params["fields"] == "f2,f3,f12,f13,f14,f62,f124"
        if len(calls) == 1:
            return reply([member_row(i) for i in range(100)], 101)
        return reply([member_row(100)], 101)
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    result = service.fetch_members("BK1629", "concept")
    assert len(result.members) == 101
    assert result.members[0].price == 12.34
    assert result.members[0].fund_flow == 125_000_000.0
    assert result.members[0].as_of.isoformat() == "2026-09-04T15:39:32+08:00"
    assert result.source == "eastmoney" and result.possibly_delayed
    assert not result.cached and service.fetch_members("BK1629", "concept").cached
    assert len(calls) == 2


@pytest.mark.parametrize("patch", [
    {"f13": 90}, {"f12": "BK1629"}, {"f14": " "}, {"f124": None},
    {"f2": "Infinity"}, {"f3": "nan"}, {"f62": []},
])
def test_invalid_member_identity_or_values_fail_snapshot(patch) -> None:
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(
        lambda _: reply([{**member_row(), **patch}]),
    ))
    with pytest.raises((ValueError, OverflowError)):
        service.fetch_members("BK1629", "concept")


def test_member_unknown_numbers_remain_null() -> None:
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(
        lambda _: reply([{**member_row(), "f2": "-", "f3": None, "f62": "-"}]),
    ))
    member = service.fetch_members("BK1629", "concept").members[0]
    assert member.price is None and member.change_pct is None and member.fund_flow is None


def test_unknown_board_code_is_rejected_before_network() -> None:
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(
        lambda _: pytest.fail("network must not be called"),
    ))
    with pytest.raises(ValueError, match="invalid board code"):
        service.fetch_members("BK1/../", "concept")


def test_large_members_fetch_overlapping_pages_and_preserve_order() -> None:
    from threading import Barrier, Lock
    barrier, lock = Barrier(8), Lock()
    active = peak = 0
    def transport(request):
        nonlocal active, peak
        page = int(request.url.params["pn"])
        assert request.url.params["fid"] == "f12"
        with lock:
            active += 1
            peak = max(peak, active)
        if 2 <= page <= 9:
            barrier.wait(timeout=3)
        with lock:
            active -= 1
        return reply([member_row(i) for i in range((page-1)*100, min(page*100, 3870))], 3870)
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    result = service.fetch_members("BK0596", "concept")
    assert [m.code for m in result.members] == [f"{i:06d}" for i in range(3870)]
    assert peak == 8
    assert service.fetch_members("BK0596", "concept").cached


@pytest.mark.parametrize("failure", ["duplicate", "missing", "total", "http", "deadline"])
def test_failed_member_pages_never_enter_cache(failure) -> None:
    clock = [0.0]
    first_calls = 0
    def transport(request):
        nonlocal first_calls
        if request.url.params["pn"] == "1":
            first_calls += 1
            return reply([member_row(i) for i in range(100)], 101)
        if failure == "http":
            return httpx.Response(503)
        if failure == "deadline":
            clock[0] += 9
        rows = [] if failure == "missing" else [member_row(0 if failure == "duplicate" else 100)]
        return reply(rows, 102 if failure == "total" else 101)
    service = EastmoneyBoardSnapshots(
        transport=httpx.MockTransport(transport), clock=lambda: clock[0],
    )
    for _ in range(2):
        with pytest.raises((ValueError, httpx.HTTPError, TimeoutError)):
            service.fetch_members("BK0596", "concept")
    assert first_calls == 2


@pytest.mark.parametrize("failure", [None, "code", "name", "category", "duplicate", "time", "http"])
def test_single_board_identity_and_quote_are_verified(failure) -> None:
    def transport(request):
        if request.url.path.endswith("sidemenu_new.json"):
            identity = {"code": "BK0596", "name": "融资融券", "market": 90,
                        "type": 1 if failure == "category" else 3}
            rows = [identity] * (2 if failure == "duplicate" else 1)
            return httpx.Response(200, json={"bklist": rows})
        assert request.url.params["fltt"] == "2"
        assert request.url.params["secid"] == "90.BK0596"
        if failure == "http":
            return httpx.Response(502)
        return httpx.Response(200, json={"rc": 0, "data": {
            "f57": "BK0001" if failure == "code" else "BK0596",
            "f58": "wrong" if failure == "name" else "融资融券",
            "f86": None if failure == "time" else 1788507572,
            "f170": -2.43, "f62": 250000000,
        }})
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    if failure:
        with pytest.raises((ValueError, httpx.HTTPError)):
            service.fetch_detail("BK0596")
    else:
        result = service.fetch_detail("BK0596")
        assert result is not None and result.kind == "concept"
        assert result.quotes[0].change_pct == -2.43
        assert result.quotes[0].fund_flow == 250000000
        assert result.quotes[0].as_of.isoformat() == "2026-09-04T15:39:32+08:00"


def test_single_unknown_board_does_not_fetch_quote() -> None:
    def transport(request):
        assert request.url.path.endswith("sidemenu_new.json")
        return httpx.Response(200, json={"bklist": [{"code": "BK0001"}]})
    service = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport))
    assert service.fetch_detail("BK0596") is None

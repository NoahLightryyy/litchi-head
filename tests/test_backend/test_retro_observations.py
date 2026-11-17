from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest

from backend import retro_observations as service
from backend.kline_display import RawDailyDisplay
from src.data.evidence import SourceStatus
from src.data.kline import RawDailyBar
from src.retro.models import RetroRecord


def record(**values):
    return RetroRecord(
        stock_code="300916", created_at=datetime(2026, 10, 7), consensus="Bullish", **values
    )


def history(*points):
    return RawDailyDisplay(
        symbol="300916",
        status=SourceStatus.SUCCESS_DATA,
        fetched_at=datetime.now(UTC),
        bars=[
            RawDailyBar(
                code="300916",
                market="SZSE",
                trade_date=d,
                open=p,
                high=p,
                low=p,
                close=p,
                volume=100,
            )
            for d, p in points
        ],
    )


def test_missing_original_price_has_explicit_baseline_without_mutation():
    original = record()
    before = original.model_dump()
    result = service.build_observation(
        original, history(("2026-10-06", 8), ("2026-10-08", 10), ("2026-10-26", 12))
    )
    assert result.status == "observed" and result.change_pct == 20
    assert result.baseline_date == date(2026, 10, 8) and result.alignment == "same"
    assert "晚于记录日期" in result.message
    assert original.model_dump() == before


@pytest.mark.parametrize(
    ("consensus", "latest", "alignment"),
    [
        ("Bearish", 9, "same"),
        ("看跌", 11, "opposite"),
        ("Bullish", 10, "flat"),
        ("Neutral", 11, "no_direction"),
    ],
)
def test_current_direction_not_final_outcome(consensus, latest, alignment):
    item = record()
    item.consensus = consensus
    result = service.build_observation(item, history(("2026-10-07", 10), ("2026-10-26", latest)))
    assert result.alignment == alignment
    assert item.outcome == "pending"


def test_waits_for_two_closes_and_converts_aware_creation_date():
    item = record()
    item.created_at = datetime(2026, 10, 6, 20, tzinfo=UTC)
    result = service.build_observation(item, history(("2026-10-07", 10)))
    assert result.status == "waiting" and result.change_pct is None
    assert result.recorded_date == date(2026, 10, 7)
    assert service.build_observation(item, history(("2026-10-06", 10))).status == "waiting"


def test_invalid_identity_order_and_zero_are_rejected():
    data = history(("2026-10-07", 10), ("2026-10-08", 11))
    data.symbol = "000001"
    with pytest.raises(ValueError):
        service.build_observation(record(), data)
    with pytest.raises(ValueError):
        service.build_observation(record(), history(("2026-10-08", 11), ("2026-10-07", 10)))
    with pytest.raises(ValueError):
        service.build_observation(record(), history(("2026-10-07", 0), ("2026-10-08", 10)))


@pytest.mark.asyncio
async def test_concurrent_same_stock_uses_one_source_request(monkeypatch):
    import asyncio

    service._cache.clear()
    service._locks.clear()
    reader = AsyncMock(return_value=history(("2026-10-07", 10)))
    monkeypatch.setattr(service, "run_sync", reader)
    await asyncio.gather(service.load_history("300916"), service.load_history("300916"))
    assert reader.await_count == 1
    service._cache.clear()
    service._locks.clear()


def test_route_partial_failure_does_not_hide_other_records(client, monkeypatch):
    from backend.routers import retro

    a, b = record(record_id="a"), record(record_id="b")
    store = AsyncMock()
    store.get.side_effect = [a, b, None]
    monkeypatch.setattr(retro, "_get_store", lambda: store)

    async def load(code):
        raise TimeoutError()

    monkeypatch.setattr(service, "load_history", load)
    result = client.get("/api/retro/observations?record_ids=a,b,missing")
    assert result.status_code == 200
    assert [r["status"] for r in result.json()["data"]] == [
        "unavailable",
        "unavailable",
        "not_found",
    ]
    store.update_outcome.assert_not_called()


@pytest.mark.parametrize("ids", ["a,a", "../x", ",", ",".join(str(i) for i in range(11))])
def test_route_bounds(client, ids):
    assert client.get("/api/retro/observations", params={"record_ids": ids}).status_code == 422


def test_unsupported_market_is_not_transient_retry():
    data = history()
    data.status = SourceStatus.UNSUPPORTED
    result = service.build_observation(record(), data)
    assert result.status == "unavailable" and "暂不支持" in result.message


@pytest.mark.asyncio
async def test_failed_refresh_retains_original_dates_and_single_flights_failures(monkeypatch):
    import asyncio

    service._cache.clear()
    service._locks.clear()
    original = history(("2026-10-07", 10), ("2026-10-26", 11))
    failed = original.model_copy(update={"status": SourceStatus.FAILED, "bars": []})
    reader = AsyncMock(return_value=failed)
    monkeypatch.setattr(service, "run_sync", reader)
    # 用“当前单调时钟 - 301 秒”表示已过期。不能写 0：单调时钟从开机算起，
    # 刚启动不到 5 分钟的机器（如 CI runner）会把时间戳 0 当成未过期。
    service._cache["300916"] = (service.time.monotonic() - 301, original)
    result = await service.observe(record())
    assert result.change_pct == 10 and result.latest_date == date(2026, 10, 26)
    assert result.fetched_at == original.fetched_at and "刷新未成功" in result.message
    service._cache.clear()
    reader.reset_mock()
    await asyncio.gather(service.load_history("300916"), service.load_history("300916"))
    assert reader.await_count == 1
    service._cache.clear()
    service._locks.clear()

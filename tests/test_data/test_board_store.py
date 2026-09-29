"""Failure preservation, durable restart, integrity and independent collection."""
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from src.data.board_runtime import collect_boards_once
from src.data.board_store import BoardSnapshotStore, BoardStoreError
from src.data.providers.eastmoney_boards import (
    BoardQuoteSnapshot,
    BoardSnapshot,
    EastmoneyBoardSnapshots,
)

NOW = datetime(2026, 9, 29, 8, tzinfo=UTC)


def snapshot(at=NOW):
    return BoardSnapshot(kind="industry", fetched_at=at, quotes=(BoardQuoteSnapshot(
        code="BK0001", name="测试板块", change_pct=1, fund_flow=None, as_of=NOW,
    ),))


def test_success_survives_failure_and_store_restart(tmp_path):
    path = tmp_path / "boards.db"
    store = BoardSnapshotStore(path)
    store.record_success(snapshot())
    first = store.load("boards:industry")
    store.record_failure("boards:industry", attempted_at=NOW + timedelta(seconds=1))
    result = BoardSnapshotStore(path).load("boards:industry")
    assert first and result
    assert result.snapshot_id == first.snapshot_id and result.snapshot == first.snapshot
    assert result.consecutive_failures == 1 and result.last_error_code == "upstream_failed"
    store.record_success(snapshot(NOW + timedelta(seconds=2)))
    recovered = store.load("boards:industry")
    assert recovered and recovered.consecutive_failures == 0 and recovered.last_error_code is None


def test_empty_duplicate_and_late_success_cannot_replace_latest(tmp_path):
    store = BoardSnapshotStore(tmp_path / "boards.db")
    original = snapshot()
    store.record_success(original)
    for values in [(), original.quotes * 2]:
        with pytest.raises(BoardStoreError):
            store.record_success(original.model_copy(update={"quotes": values}))
    store.record_success(snapshot(NOW - timedelta(seconds=1)))
    restored = store.load("boards:industry")
    assert restored and restored.snapshot == original


def test_late_success_does_not_clear_newer_failure(tmp_path):
    store = BoardSnapshotStore(tmp_path / "boards.db")
    store.record_success(snapshot())
    store.record_failure("boards:industry", attempted_at=NOW + timedelta(seconds=3))
    store.record_success(snapshot(NOW + timedelta(seconds=1)))
    result = store.load("boards:industry")
    assert result and result.consecutive_failures == 1
    assert result.last_attempt_at == NOW + timedelta(seconds=3)


def test_first_failure_does_not_create_fake_snapshot(tmp_path):
    store = BoardSnapshotStore(tmp_path / "boards.db")
    store.record_failure("boards:concept", attempted_at=NOW)
    assert store.load("boards:concept") is None


def test_corrupt_payload_fails_closed(tmp_path):
    path = tmp_path / "boards.db"
    store = BoardSnapshotStore(path)
    store.record_success(snapshot())
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE board_display_v1 SET payload='{}'")
    with pytest.raises(BoardStoreError, match="checksum"):
        store.load("boards:industry")


def test_provider_records_complete_success_but_never_returns_old_data_on_failure(tmp_path):
    fail = False
    def transport(request):
        if fail:
            return httpx.Response(502)
        return httpx.Response(200, json={"rc": 0, "data": {"total": 1, "diff": [{
            "f12": "BK0001", "f13": 90, "f14": "测试", "f3": 1, "f62": 10,
            "f124": 1790668800,
        }]}})
    clock = [0.0]
    store = BoardSnapshotStore(tmp_path / "boards.db")
    provider = EastmoneyBoardSnapshots(transport=httpx.MockTransport(transport),
                                      clock=lambda: clock[0], store=store)
    assert collect_boards_once(provider) == {"industry": True, "concept": True}
    fail, clock[0] = True, 31
    assert collect_boards_once(provider) == {"industry": False, "concept": False}
    for kind in ("industry", "concept"):
        result = BoardSnapshotStore(store.path).load(f"boards:{kind}")
        assert result and result.consecutive_failures == 1


def test_disk_failure_is_explicit(tmp_path):
    path = tmp_path / "directory"
    path.mkdir()
    with pytest.raises(BoardStoreError, match="persistence failed"):
        BoardSnapshotStore(path).record_success(snapshot())


@pytest.mark.asyncio
async def test_warmup_shutdown_joins_inflight_collection(monkeypatch):
    import asyncio
    from threading import Event

    from src.data.board_runtime import warm_boards
    entered, release = Event(), Event()
    def blocked(provider):
        entered.set()
        assert release.wait(2)
        return {}
    monkeypatch.setattr("src.data.board_runtime.collect_boards_once", blocked)
    task = asyncio.create_task(warm_boards(EastmoneyBoardSnapshots()))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

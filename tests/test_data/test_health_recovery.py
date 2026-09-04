"""Current health is an atomic batch result, independent of historical counters."""
from concurrent.futures import ThreadPoolExecutor

from src.data.collector import HealthObservation, HealthStats


def observation(status: str) -> HealthObservation:
    return HealthObservation.model_validate({
        "endpoint": "market_index:sina", "duration_ms": 1, "status": status,
        "error_code": "index_quote_conflict" if status == "failed" else None,
    })


def test_late_old_batch_preserves_history_without_regressing_current_health() -> None:
    stats = HealthStats()
    old = stats.begin_batch()
    new = stats.begin_batch()
    stats.record_batch(new, [observation("healthy")] * 3)
    stats.record_batch(old, [observation("failed"), observation("healthy"), observation("empty")])
    snap = stats.snapshot()
    ep = snap["market_index:sina"]
    assert ep["total_calls"] == 6
    assert ep["failures"] == 1
    assert ep["empty"] == 1
    assert ep["current_status"] == "healthy"
    assert ep["last_error"] is None
    assert ep["last_error_code"] is None
    assert snap["__summary__"]["healthy_endpoints"] == 1


def test_failure_empty_recovery_and_history_are_separate() -> None:
    stats = HealthStats()
    stats.record_call("quotes", 1, error="secret")
    stats.record_call("quotes", 1, empty=True)
    assert stats.snapshot()["quotes"]["current_status"] == "empty"
    assert stats.snapshot()["__summary__"]["failing_endpoints"] == 0
    stats.record_call("quotes", 1)
    assert stats.snapshot()["quotes"]["current_status"] == "healthy"
    assert stats.snapshot()["__summary__"]["total_failures"] == 1


def test_concurrent_batches_and_snapshots_never_publish_partial_counts() -> None:
    stats = HealthStats()
    def record(_: int) -> None:
        stats.record_batch(stats.begin_batch(), [observation("healthy")] * 3)
        assert stats.snapshot()["market_index:sina"]["total_calls"] % 3 == 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(record, range(100)))
    assert stats.snapshot()["market_index:sina"]["total_calls"] == 300

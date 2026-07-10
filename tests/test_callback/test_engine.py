"""tests for ResultCallbackEngine"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.callback import (
    CallbackConfig,
    CallbackEvent,
    CallbackEventType,
    CallbackPriority,
    CallbackRecord,
    ResultCallbackEngine,
)


async def test_dispatch_runs_matching_callbacks_in_priority_order() -> None:
    calls: list[str] = []
    engine = ResultCallbackEngine()

    async def low(event: CallbackEvent) -> CallbackRecord:
        calls.append(f"low:{event.context['stock_code']}")
        return CallbackRecord(summary="low done")

    async def high(event: CallbackEvent) -> CallbackRecord:
        calls.append(f"high:{event.context['stock_code']}")
        return CallbackRecord(summary="high done")

    engine.register(
        "low",
        low,
        event_types=[CallbackEventType.DEBATE_COMPLETED],
        config=CallbackConfig(
            callback_name="low",
            priority=CallbackPriority.LOW,
        ),
    )
    engine.register(
        "high",
        high,
        event_types=[CallbackEventType.DEBATE_COMPLETED],
        config=CallbackConfig(
            callback_name="high",
            priority=CallbackPriority.HIGH,
        ),
    )

    records = await engine.dispatch(
        CallbackEventType.DEBATE_COMPLETED,
        context={"stock_code": "600519"},
        source="test",
    )

    assert calls == ["high:600519", "low:600519"]
    assert [r.callback_name for r in records] == ["high", "low"]
    assert all(r.success for r in records)
    assert all(r.event_id for r in records)


async def test_dispatch_ignores_unmatched_and_disabled_callbacks() -> None:
    calls: list[str] = []
    engine = ResultCallbackEngine()

    async def callback(event: CallbackEvent) -> CallbackRecord:
        calls.append(event.event_type.value)
        return CallbackRecord(summary="done")

    engine.register(
        "unmatched",
        callback,
        event_types=[CallbackEventType.USER_ACTION_RECORDED],
    )
    engine.register(
        "disabled",
        callback,
        event_types=[CallbackEventType.DEBATE_COMPLETED],
        config=CallbackConfig(
            callback_name="disabled",
            enabled=False,
            event_types=[CallbackEventType.DEBATE_COMPLETED],
        ),
    )

    records = await engine.dispatch(CallbackEventType.DEBATE_COMPLETED)

    assert records == []
    assert calls == []


async def test_callback_failure_is_recorded_and_does_not_block_later_callbacks() -> None:
    calls: list[str] = []
    engine = ResultCallbackEngine()

    async def failing(event: CallbackEvent) -> CallbackRecord:
        calls.append("fail")
        raise RuntimeError("boom")

    async def succeeding(event: CallbackEvent) -> CallbackRecord:
        calls.append("success")
        return CallbackRecord(summary="ok")

    engine.register(
        "failing",
        failing,
        event_types=[CallbackEventType.TRADE_SETTLED],
    )
    engine.register(
        "succeeding",
        succeeding,
        event_types=[CallbackEventType.TRADE_SETTLED],
    )

    records = await engine.dispatch(CallbackEventType.TRADE_SETTLED)

    assert calls == ["fail", "success"]
    assert records[0].success is False
    assert "boom" in records[0].error
    assert records[1].success is True


async def test_callback_auto_disables_after_error_threshold() -> None:
    engine = ResultCallbackEngine()

    async def failing(event: CallbackEvent) -> CallbackRecord:
        raise RuntimeError("bad callback")

    engine.register(
        "fragile",
        failing,
        event_types=[CallbackEventType.BACKTEST_COMPLETED],
        config=CallbackConfig(
            callback_name="fragile",
            event_types=[CallbackEventType.BACKTEST_COMPLETED],
            max_errors_before_disable=2,
        ),
    )

    first = await engine.dispatch(CallbackEventType.BACKTEST_COMPLETED)
    second = await engine.dispatch(CallbackEventType.BACKTEST_COMPLETED)
    third = await engine.dispatch(CallbackEventType.BACKTEST_COMPLETED)

    entry = engine.registry.get("fragile")
    assert first[0].success is False
    assert second[0].success is False
    assert third == []
    assert entry is not None
    assert entry.config.enabled is False
    assert entry.config.error_count == 2


async def test_cooldown_skips_callback_without_incrementing_errors() -> None:
    calls: list[str] = []
    engine = ResultCallbackEngine()

    async def callback(event: CallbackEvent) -> CallbackRecord:
        calls.append("called")
        return CallbackRecord(summary="ok")

    engine.register(
        "cool",
        callback,
        event_types=[CallbackEventType.USER_ACTION_RECORDED],
        config=CallbackConfig(
            callback_name="cool",
            event_types=[CallbackEventType.USER_ACTION_RECORDED],
            cooldown_seconds=60,
            last_fired_at=datetime.now() - timedelta(seconds=10),
        ),
    )

    records = await engine.dispatch(CallbackEventType.USER_ACTION_RECORDED)
    entry = engine.registry.get("cool")

    assert calls == []
    assert records[0].success is True
    assert records[0].summary == "skipped: cooldown"
    assert entry is not None
    assert entry.config.error_count == 0

"""tests for RC-002 M3 TrustTracker callback"""

from __future__ import annotations

from pathlib import Path

from src.callback import CallbackEventType, ResultCallbackEngine
from src.callback.callbacks import create_m3_ext_callback, register_m3_ext_callback
from src.callback.models import CallbackEvent
from src.debate.models import AgentAnalysis
from src.debate.trust import TrustTracker
from src.memory.store import JsonFileStore


def _analysis(
    agent_name: str = "master.buffett",
    direction: str = "Bullish",
    success: bool = True,
) -> AgentAnalysis:
    return AgentAnalysis(
        agent_name=agent_name,
        skill_id=agent_name.replace("master.", ""),
        skill_name="测试大师",
        rating="看涨",
        score=75,
        summary="summary",
        analysis="analysis",
        confidence=0.8,
        direction=direction,
        success=success,
    )


async def test_m3_ext_callback_records_agent_outcomes(tmp_path: Path) -> None:
    store = JsonFileStore(base_path=tmp_path)
    callback = create_m3_ext_callback(memory_store=store)
    event = CallbackEvent(
        event_type=CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
        context={
            "agent_analyses": [
                _analysis("master.buffett", "Bullish"),
                _analysis("master.munger", "Bearish"),
            ],
            "actual_outcome": {
                "actual_direction": "Bullish",
                "actual_price_change_pct": 3.2,
                "evaluation_date": "2026-07-10",
            },
            "session_id": "sess-rc-002",
            "stock_code": "600519",
            "sector": "食品饮料",
            "decision_date": "2026-07-09",
        },
    )

    record = await callback(event)

    assert record.success is True
    assert record.mutations["recorded"] == 2

    tracker = TrustTracker(memory_store=store)
    buffett = await tracker.get_trust_report("master.buffett")
    munger = await tracker.get_trust_report("master.munger")

    assert buffett.metrics.total_samples == 1
    assert buffett.metrics.win_rate == 1.0
    assert buffett.metrics.sector_win_rates["食品饮料"] == 1.0
    assert munger.metrics.total_samples == 1
    assert munger.metrics.win_rate == 0.0
    assert munger.metrics.sector_sample_counts["食品饮料"] == 1


async def test_m3_ext_callback_skips_failed_analyses(tmp_path: Path) -> None:
    store = JsonFileStore(base_path=tmp_path)
    callback = create_m3_ext_callback(memory_store=store)
    event = CallbackEvent(
        event_type=CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
        context={
            "agent_analyses": [
                _analysis("master.buffett", "Bullish", success=True),
                _analysis("master.failed", "Bearish", success=False),
            ],
            "actual_outcome": {
                "actual_direction": "Bullish",
                "actual_price_change_pct": 1.0,
            },
        },
    )

    record = await callback(event)

    assert record.mutations["recorded"] == 1
    tracker = TrustTracker(memory_store=store)
    failed = await tracker.get_trust_report("master.failed")
    assert failed.metrics.total_samples == 0


async def test_m3_ext_callback_missing_actual_direction_is_visible() -> None:
    callback = create_m3_ext_callback(memory_store=None)
    event = CallbackEvent(
        event_type=CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
        context={"agent_analyses": [_analysis()]},
    )

    record = await callback(event)

    assert record.success is False
    assert "actual_direction" in record.error


async def test_register_m3_ext_callback_with_engine(tmp_path: Path) -> None:
    store = JsonFileStore(base_path=tmp_path)
    engine = ResultCallbackEngine()

    register_m3_ext_callback(engine, memory_store=store)
    records = await engine.dispatch(
        CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
        context={
            "agent_analyses": [_analysis()],
            "actual_outcome": {
                "actual_direction": "Bullish",
                "actual_price_change_pct": 2.0,
            },
            "sector": "食品饮料",
        },
    )

    assert records[0].callback_name == "m3_ext"
    assert records[0].mutations["recorded"] == 1

    tracker = TrustTracker(memory_store=store)
    report = await tracker.get_trust_report("master.buffett")
    assert report.metrics.total_samples == 1

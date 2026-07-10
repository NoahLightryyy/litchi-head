"""RC-002: M3 TrustTracker 结果回调"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.callback.models import (
    CallbackConfig,
    CallbackEvent,
    CallbackEventType,
    CallbackPriority,
    CallbackRecord,
)
from src.debate.trust import TrustTracker
from src.memory.store import MemoryStore


def create_m3_ext_callback(memory_store: MemoryStore | None = None):
    """创建 M3-EXT 回调函数。

    事件 context 约定：
      - agent_analyses: list[AgentAnalysis | dict]
      - actual_outcome: dict，含 actual_direction / actual_price_change_pct
      - stock_code/session_id/sector/decision_date/evaluation_date 可在顶层或 actual_outcome 中提供
    """

    async def callback(event: CallbackEvent) -> CallbackRecord:
        analyses = _as_list(event.context.get("agent_analyses"))
        actual = _as_mapping(event.context.get("actual_outcome"))
        actual_direction = _str_field(actual, event.context, "actual_direction")

        if not analyses:
            return CallbackRecord(
                summary="m3_ext skipped: no agent analyses",
                mutations={"recorded": 0},
            )
        if not actual_direction:
            return CallbackRecord(
                success=False,
                summary="m3_ext failed: missing actual_direction",
                error="actual_direction is required",
                mutations={"recorded": 0},
            )

        tracker = TrustTracker(memory_store=memory_store)
        recorded = 0
        for analysis in analyses:
            if not _bool_field(analysis, "success", default=True):
                continue
            agent_name = _str_field(analysis, {}, "agent_name")
            if not agent_name:
                continue

            tracker.record_outcome_from_analysis(
                agent_name=agent_name,
                score=_int_field(analysis, "score"),
                confidence=_float_field(analysis, "confidence"),
                direction=_str_field(analysis, {}, "direction") or "Neutral",
                rating=_str_field(analysis, {}, "rating"),
                skill_id=_str_field(analysis, {}, "skill_id"),
                skill_name=_str_field(analysis, {}, "skill_name"),
                actual_direction=actual_direction,
                actual_price_change_pct=_float_field(actual, "actual_price_change_pct"),
                session_id=_str_field(actual, event.context, "session_id"),
                stock_code=_str_field(actual, event.context, "stock_code"),
                sector=_str_field(actual, event.context, "sector"),
                decision_date=_str_field(actual, event.context, "decision_date"),
                evaluation_date=_str_field(actual, event.context, "evaluation_date"),
            )
            recorded += 1

        await tracker.flush()
        return CallbackRecord(
            summary=f"m3_ext recorded {recorded} trust outcomes",
            mutations={"recorded": recorded},
        )

    return callback


def register_m3_ext_callback(
    engine: Any,
    memory_store: MemoryStore | None = None,
) -> None:
    """把 M3-EXT 注册到 ResultCallbackEngine。"""
    engine.register(
        "m3_ext",
        create_m3_ext_callback(memory_store=memory_store),
        event_types=[CallbackEventType.ACTUAL_OUTCOME_RECEIVED],
        config=CallbackConfig(
            callback_name="m3_ext",
            event_types=[CallbackEventType.ACTUAL_OUTCOME_RECEIVED],
            priority=CallbackPriority.HIGH,
        ),
    )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump()
    return {}


def _get_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _str_field(primary: Any, fallback: dict[str, Any], key: str) -> str:
    value = _get_value(primary, key)
    if value is None:
        value = fallback.get(key)
    return "" if value is None else str(value)


def _int_field(source: Any, key: str) -> int:
    value = _get_value(source, key)
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_field(source: Any, key: str) -> float:
    value = _get_value(source, key)
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bool_field(source: Any, key: str, default: bool) -> bool:
    value = _get_value(source, key)
    return value if isinstance(value, bool) else default


__all__ = ["create_m3_ext_callback", "register_m3_ext_callback"]

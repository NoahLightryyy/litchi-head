"""结果参数回调引擎 —— 中央事件分发器"""

from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Any

from src.callback.models import (
    CallbackConfig,
    CallbackEvent,
    CallbackEventType,
    CallbackFn,
    CallbackRecord,
)
from src.callback.registry import CallbackRegistry
from src.callback.storage import CallbackStorage
from src.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class ResultCallbackEngine:
    """统一接收结果事件，并分发给已注册的回调处理器。

    引擎保证单个回调失败不会阻断其他回调，也不会让业务主流程崩溃。
    """

    def __init__(
        self,
        memory_store: MemoryStore | None = None,
        registry: CallbackRegistry | None = None,
        storage: CallbackStorage | None = None,
    ) -> None:
        self.registry = registry or CallbackRegistry()
        self.storage = storage or CallbackStorage(memory_store=memory_store)

    def register(
        self,
        name: str,
        callback_fn: CallbackFn,
        event_types: list[CallbackEventType] | None = None,
        config: CallbackConfig | None = None,
    ) -> None:
        """注册一个回调处理器。"""
        resolved_config = config or CallbackConfig(callback_name=name)
        if resolved_config.callback_name != name:
            resolved_config = resolved_config.model_copy(update={"callback_name": name})
        if event_types is not None:
            resolved_config = resolved_config.model_copy(update={"event_types": event_types})
        self.registry.register(name, callback_fn, resolved_config)

    async def dispatch(
        self,
        event_type: CallbackEventType | CallbackEvent,
        context: dict[str, Any] | None = None,
        source: str = "",
    ) -> list[CallbackRecord]:
        """分发事件并返回每个回调的执行记录。"""
        event = self._build_event(event_type, context=context, source=source)
        await self._load_persisted_configs()

        records: list[CallbackRecord] = []
        for entry in self.registry.get_for_event(event.event_type):
            if self._is_in_cooldown(entry.config, event.timestamp):
                record = self._cooldown_record(entry.name, event)
            else:
                record = await self._run_callback(entry.name, entry.fn, entry.config, event)
            records.append(record)
            await self.storage.save_record(record)
            await self.storage.save_config(entry.config)

        await self.storage.flush_records()
        return records

    async def _load_persisted_configs(self) -> None:
        for entry in self.registry.list_all():
            persisted = await self.storage.load_config(entry.name)
            if persisted is not None:
                entry.config = persisted

    def _build_event(
        self,
        event_type: CallbackEventType | CallbackEvent,
        context: dict[str, Any] | None,
        source: str,
    ) -> CallbackEvent:
        if isinstance(event_type, CallbackEvent):
            return event_type
        return CallbackEvent(
            event_type=event_type,
            source=source,
            context=context or {},
        )

    def _is_in_cooldown(self, config: CallbackConfig, now: datetime) -> bool:
        if config.cooldown_seconds <= 0 or config.last_fired_at is None:
            return False
        elapsed = (now - config.last_fired_at).total_seconds()
        return elapsed < config.cooldown_seconds

    def _cooldown_record(self, callback_name: str, event: CallbackEvent) -> CallbackRecord:
        return CallbackRecord(
            callback_name=callback_name,
            event_type=event.event_type,
            event_id=event.event_id,
            timestamp=event.timestamp,
            success=True,
            summary="skipped: cooldown",
        )

    async def _run_callback(
        self,
        callback_name: str,
        callback_fn: CallbackFn,
        config: CallbackConfig,
        event: CallbackEvent,
    ) -> CallbackRecord:
        started_at = perf_counter()
        try:
            record = await callback_fn(event)
            record = self._normalize_record(record, callback_name, event, started_at)
            self._apply_success_state(config, record.success)
            return record
        except Exception as e:
            logger.exception("回调执行失败: %s", callback_name)
            duration_ms = (perf_counter() - started_at) * 1000
            self._apply_error_state(config)
            return CallbackRecord(
                callback_name=callback_name,
                event_type=event.event_type,
                event_id=event.event_id,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                success=False,
                summary="callback failed",
                error=str(e),
            )

    def _normalize_record(
        self,
        record: CallbackRecord,
        callback_name: str,
        event: CallbackEvent,
        started_at: float,
    ) -> CallbackRecord:
        duration_ms = record.duration_ms or (perf_counter() - started_at) * 1000
        return record.model_copy(
            update={
                "callback_name": record.callback_name or callback_name,
                "event_type": event.event_type,
                "event_id": record.event_id or event.event_id,
                "duration_ms": duration_ms,
            }
        )

    def _apply_success_state(self, config: CallbackConfig, success: bool) -> None:
        if success:
            config.last_fired_at = datetime.now()
            config.error_count = 0
            return
        self._apply_error_state(config)

    def _apply_error_state(self, config: CallbackConfig) -> None:
        config.error_count += 1
        if config.error_count >= config.max_errors_before_disable:
            config.enabled = False


__all__ = ["ResultCallbackEngine"]

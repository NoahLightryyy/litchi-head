"""回调状态持久化 —— MemoryStore ("callback", *) 命名空间

命名空间布局:
  ("callback", "config")           -- 每个回调的 CallbackConfig（JSON，key=回调名称）
  ("callback", "records")          -- 执行记录流（JSONL，用于审计/调试）
  ("callback", "risk_override")    -- 风险参数覆盖（JSON，key="current"）
  ("callback", "strategy_stats")   -- 策略路由统计（JSON，key="route_table"）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.callback.models import CallbackConfig, CallbackRecord
from src.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class CallbackStorage:
    """回调存储层

    封装 MemoryStore 的 ("callback", *) 命名空间操作。
    MemoryStore 为 None 时静默降级（仅内存运行）。
    """

    _CONFIG_NS = ("callback", "config")
    _RECORDS_NS = ("callback", "records")
    _RISK_OVERRIDE_NS = ("callback", "risk_override")
    _STRATEGY_STATS_NS = ("callback", "strategy_stats")

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self.memory_store = memory_store
        self._pending_records: list[CallbackRecord] = []

    async def save_config(self, config: CallbackConfig) -> None:
        """持久化一个回调的配置"""
        if not self.memory_store:
            return
        try:
            await self.memory_store.put(
                key=config.callback_name,
                value=config.model_dump(),
                namespace=self._CONFIG_NS,
            )
        except Exception as e:
            logger.warning("保存回调配置失败: %s, err=%s", config.callback_name, e)

    async def load_config(self, callback_name: str) -> CallbackConfig | None:
        """加载一个回调的持久化配置"""
        if not self.memory_store:
            return None
        try:
            item = await self.memory_store.get(key=callback_name, namespace=self._CONFIG_NS)
            if item is None:
                return None
            if isinstance(item.value, dict):
                return CallbackConfig(**item.value)
            return None
        except Exception as e:
            logger.warning("加载回调配置失败: %s, err=%s", callback_name, e)
            return None

    async def save_record(self, record: CallbackRecord) -> None:
        """将执行记录加入缓冲区（批量写入）"""
        self._pending_records.append(record)
        if len(self._pending_records) >= 10:
            await self.flush_records()

    async def flush_records(self) -> None:
        """冲刷待处理的执行记录到 MemoryStore"""
        if not self.memory_store or not self._pending_records:
            return
        try:
            timestamp = datetime.now().isoformat()
            await self.memory_store.put(
                key=timestamp,
                value=[r.model_dump() for r in self._pending_records],
                namespace=self._RECORDS_NS,
            )
            self._pending_records.clear()
        except Exception as e:
            logger.warning("冲刷回调记录失败: %s", e)

    async def save_risk_override(self, overrides: dict[str, Any]) -> None:
        """保存风险参数覆盖

        Args:
            overrides: 覆盖值字典，如 {"stop_loss_pct": 0.05, "max_single_position": 0.15}
        """
        if not self.memory_store:
            return
        try:
            await self.memory_store.put(
                key="current",
                value=overrides,
                namespace=self._RISK_OVERRIDE_NS,
            )
        except Exception as e:
            logger.warning("保存风险覆盖失败: %s", e)

    async def load_risk_override(self) -> dict[str, Any]:
        """加载风险参数覆盖

        Returns:
            覆盖值字典（无覆盖时返回空字典）
        """
        if not self.memory_store:
            return {}
        try:
            item = await self.memory_store.get(key="current", namespace=self._RISK_OVERRIDE_NS)
            if item and isinstance(item.value, dict):
                return item.value
            return {}
        except Exception as e:
            logger.warning("加载风险覆盖失败: %s", e)
            return {}

    async def save_strategy_stats(self, stats: dict[str, Any]) -> None:
        """保存策略路由统计

        Args:
            stats: 策略统计字典
        """
        if not self.memory_store:
            return
        try:
            await self.memory_store.put(
                key="route_table",
                value=stats,
                namespace=self._STRATEGY_STATS_NS,
            )
        except Exception as e:
            logger.warning("保存策略统计失败: %s", e)

    async def load_strategy_stats(self) -> dict[str, Any]:
        """加载策略路由统计

        Returns:
            策略统计字典（无记录时返回空字典）
        """
        if not self.memory_store:
            return {}
        try:
            item = await self.memory_store.get(key="route_table", namespace=self._STRATEGY_STATS_NS)
            if item and isinstance(item.value, dict):
                return item.value
            return {}
        except Exception as e:
            logger.warning("加载策略统计失败: %s", e)
            return {}


__all__ = ["CallbackStorage"]

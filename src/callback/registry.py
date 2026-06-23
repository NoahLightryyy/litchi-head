"""回调注册表 —— 管理回调函数的注册、查找和生命周期"""

from __future__ import annotations

import logging

from src.callback.models import CallbackConfig, CallbackEventType, CallbackFn

logger = logging.getLogger(__name__)


class _RegistryEntry:
    """注册表条目（内部，非公开）"""

    __slots__ = ("name", "fn", "config")

    def __init__(
        self,
        name: str,
        fn: CallbackFn,
        config: CallbackConfig,
    ) -> None:
        self.name = name
        self.fn = fn
        self.config = config


class CallbackRegistry:
    """回调注册表

    以回调名称为键，存储回调函数和配置。
    设计为启动时注册，运行时只读。
    """

    def __init__(self) -> None:
        self._entries: dict[str, _RegistryEntry] = {}

    def register(
        self,
        name: str,
        callback_fn: CallbackFn,
        config: CallbackConfig | None = None,
    ) -> None:
        """注册一个回调

        幂等：相同 name 重复注册会覆盖（带警告）。

        Args:
            name: 回调唯一标识（如 "m3_ext", "rp_tune"）
            callback_fn: 回调异步函数
            config: 回调配置（使用默认值如果未提供）
        """
        if name in self._entries:
            logger.warning("回调 '%s' 重复注册，将覆盖", name)
        self._entries[name] = _RegistryEntry(
            name=name,
            fn=callback_fn,
            config=config or CallbackConfig(callback_name=name),
        )

    def unregister(self, name: str) -> bool:
        """注销一个回调

        Args:
            name: 回调标识

        Returns:
            是否成功注销（False 表示不存在）
        """
        if name in self._entries:
            del self._entries[name]
            return True
        return False

    def get(self, name: str) -> _RegistryEntry | None:
        """获取指定回调的注册条目"""
        return self._entries.get(name)

    def list_enabled(self) -> list[_RegistryEntry]:
        """返回所有已启用的回调（按优先级排序）"""
        enabled = [e for e in self._entries.values() if e.config.enabled]
        enabled.sort(key=lambda e: e.config.priority.value)
        return enabled

    def get_for_event(self, event_type: CallbackEventType) -> list[_RegistryEntry]:
        """返回监听特定事件类型的已启用回调"""
        return [
            e
            for e in self.list_enabled()
            if event_type in e.config.event_types
        ]

    @property
    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """清空所有注册（主要用于测试）"""
        self._entries.clear()


__all__ = ["CallbackRegistry"]

"""轻量级数据缓存 —— 基于 TTL 的内存缓存

用途：减少 akshare 请求频率，提供数据过期机制。

TTL 策略由 DataCollector 按数据类型指定：
- 实时行情：30 秒
- K 线（日线）：5 分钟
- 股票列表：1 小时
- 新闻：2 分钟
"""

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """缓存条目，包含值和过期时间"""
    value: Any
    expires_at: float


class DataCache:
    """轻量级内存缓存，基于 TTL 过期

    用法：
        cache = DataCache(default_ttl=60.0)
        cache.set("stocks", stock_list)
        data = cache.get("stocks")  # None 表示未命中或已过期
    """

    def __init__(self, default_ttl: float = 60.0):
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """获取缓存值，未命中或已过期返回 None"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            del self._cache[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期秒数，None 使用 default_ttl
        """
        ttl_value = ttl if ttl is not None else self._default_ttl
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl_value,
        )

    def delete(self, key: str) -> None:
        """删除指定缓存键"""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()

    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查条目是否已过期"""
        return time.time() > entry.expires_at

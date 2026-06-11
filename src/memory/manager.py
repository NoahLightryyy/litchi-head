"""MemoryManager 高层封装

提供面向消费者的语义化接口，隐藏 MemoryStore 的命名空间构造细节。

用法：
    store = JsonFileStore()
    mem = MemoryManager(store=store, user_id="user_001")

    # Agent 记录当前分析
    await mem.remember(agent="buffett", memory_type="working", key="analysis", value={...})

    # 镜子 Agent 获取全部历史
    history = await mem.recall_all_agents(memory_type="episodic")
"""

from __future__ import annotations

from typing import Any

from src.memory.store import MemoryItem, MemoryStore


class MemoryManager:
    """记忆管理器——消费者与 MemoryStore 之间的语义化桥梁

    封装命名空间构造逻辑，让消费者不必手动拼接 namespace tuple。
    """

    def __init__(self, store: MemoryStore, user_id: str = "default"):
        self._store = store
        self._user_id = user_id

    def _ns(
        self, memory_type: str, agent: str
    ) -> tuple[str, str, str]:
        return (memory_type, agent, self._user_id)

    async def remember(
        self,
        agent: str,
        memory_type: str,
        key: str,
        value: Any,
    ) -> MemoryItem:
        """记录一条记忆"""
        return await self._store.put(key, value, namespace=self._ns(memory_type, agent))

    async def recall(
        self,
        agent: str,
        memory_type: str,
        key: str,
    ) -> MemoryItem | None:
        """读取一条记忆"""
        return await self._store.get(key, namespace=self._ns(memory_type, agent))

    async def recall_all_agents(
        self,
        memory_type: str,
        k: int = 100,
    ) -> list[MemoryItem]:
        """跨所有 Agent 搜索同一记忆类型（供镜子 Agent 使用）"""
        return await self._store.search(
            namespace=(memory_type,),
            k=k,
        )

    async def get_profile(self) -> dict:
        """获取用户全局画像"""
        ns = ("semantic", "global", self._user_id)
        item = await self._store.get("profile", namespace=ns)
        if item is None:
            return {}
        return dict(item.value) if isinstance(item.value, dict) else {}

    async def update_profile(self, updates: dict) -> None:
        """更新用户全局画像（合并写入）"""
        ns = ("semantic", "global", self._user_id)
        current = await self.get_profile()
        current.update(updates)
        await self._store.put("profile", current, namespace=ns)

    async def get_session_context(self, agent: str = "master") -> dict | None:
        """获取当前 session 的工作记忆上下文"""
        ns = ("working", agent, self._user_id)
        item = await self._store.get("session_ctx", namespace=ns)
        if item is None:
            return None
        return dict(item.value) if isinstance(item.value, dict) else {}

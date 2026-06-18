"""tests for MemoryManager — 高层封装"""

from pathlib import Path

import pytest

from src.memory.manager import MemoryManager
from src.memory.store import JsonFileStore


class TestMemoryManager:
    @pytest.fixture
    def manager(self, tmp_path: Path) -> MemoryManager:
        store = JsonFileStore(base_path=tmp_path)
        return MemoryManager(store=store, user_id="user_001")

    @pytest.mark.asyncio
    async def test_remember_and_recall(self, manager: MemoryManager):
        """remember 后可通过 recall 读取"""
        await manager.remember(
            agent="buffett",
            memory_type="working",
            key="analysis",
            value={"rating": "看涨"},
        )
        item = await manager.recall(
            agent="buffett",
            memory_type="working",
            key="analysis",
        )
        assert item is not None
        assert item.value["rating"] == "看涨"

    @pytest.mark.asyncio
    async def test_recall_not_found(self, manager: MemoryManager):
        """recall 不存在的记忆返回 None"""
        item = await manager.recall("buffett", "working", "nothing")
        assert item is None

    @pytest.mark.asyncio
    async def test_recall_all_agents(self, manager: MemoryManager):
        """recall_all_agents 跨 Agent 查询"""
        await manager.remember("buffett", "episodic", "q1", {"q": "分析茅台"})
        await manager.remember("munger", "episodic", "q2", {"q": "分析五粮液"})

        all_items = await manager.recall_all_agents(memory_type="episodic")
        assert len(all_items) == 2

    @pytest.mark.asyncio
    async def test_get_and_update_profile(self, manager: MemoryManager):
        """get/update_profile 读写用户画像"""
        initial = await manager.get_profile()
        assert initial == {}

        await manager.update_profile({"risk_tolerance": "稳健", "preferred_stocks": ["茅台"]})
        profile = await manager.get_profile()
        assert profile["risk_tolerance"] == "稳健"
        assert profile["preferred_stocks"] == ["茅台"]

    @pytest.mark.asyncio
    async def test_get_session_context(self, manager: MemoryManager):
        """get_session_context 返回工作记忆"""
        await manager.remember(
            agent="master",
            memory_type="working",
            key="session_ctx",
            value={"focus": "茅台分析"},
        )
        ctx = await manager.get_session_context(agent="master")
        assert ctx is not None
        assert ctx["focus"] == "茅台分析"

    @pytest.mark.asyncio
    async def test_default_user_id(self, tmp_path: Path):
        """不传 user_id 时使用默认值"""
        store = JsonFileStore(base_path=tmp_path)
        m = MemoryManager(store=store)
        await m.remember("test", "working", "k", "v")
        item = await m.recall("test", "working", "k")
        assert item is not None


class TestMemoryManagerStorageFailure:
    """存储失败场景 —— MemoryManager 应优雅降级"""

    @pytest.mark.asyncio
    async def test_remember_readonly_path(self, tmp_path: Path):
        """只读路径的 remember 不应崩溃"""
        readonly_path = tmp_path / "nonexistent" / "deep"
        store = JsonFileStore(base_path=readonly_path)
        manager = MemoryManager(store=store, user_id="test")
        # 应静默处理，不抛异常
        await manager.remember("buffett", "working", "k", {"v": 1})

    @pytest.mark.asyncio
    async def test_recall_nonexistent_store(self, tmp_path: Path):
        """不存在的存储路径 recall 返回 None"""
        store = JsonFileStore(base_path=tmp_path / "no_such_dir")
        manager = MemoryManager(store=store, user_id="test")
        item = await manager.recall("buffett", "working", "k")
        assert item is None

    @pytest.mark.asyncio
    async def test_remember_recall_empty_store(self, tmp_path: Path):
        """空存储路径的 remember/recall 不崩溃"""
        store = JsonFileStore(base_path=tmp_path / "empty_store")
        manager = MemoryManager(store=store, user_id="test")
        # 空存储上 recall 返回 None
        item = await manager.recall("a", "b", "c")
        assert item is None

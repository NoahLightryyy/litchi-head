"""tests for MemoryItem, MemoryStore ABC, and JsonFileStore"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from pathlib import Path

import pytest

from src.memory.store import JsonFileStore, MemoryItem, MemoryStore


class TestMemoryItem:
    def test_minimal(self):
        """最小字段创建"""
        item = MemoryItem(key="k1", value="hello")
        assert item.key == "k1"
        assert item.value == "hello"
        assert item.namespace == ()
        assert isinstance(item.created_at, datetime)
        assert item.score == 0.0

    def test_full_fields(self):
        """完整字段创建"""
        item = MemoryItem(
            key="k1",
            value={"nested": True},
            namespace=("episodic", "buffett", "user_001"),
            score=0.85,
        )
        assert item.key == "k1"
        assert item.value == {"nested": True}
        assert item.namespace == ("episodic", "buffett", "user_001")
        assert item.score == 0.85

    def test_key_required(self):
        """key 是必填字段"""
        with pytest.raises(ValidationError):
            MemoryItem(value="no_key")


class TestMemoryStoreInterface:
    def test_cannot_instantiate_abc(self):
        """MemoryStore 是抽象类，不能直接实例化"""
        with pytest.raises(TypeError):
            MemoryStore()  # type: ignore

    def test_subclass_must_implement_all_methods(self):
        """未实现所有抽象方法的子类不能实例化"""

        class BadStore(MemoryStore):
            async def get(self, key, namespace=()):  # type: ignore[override]
                return None

        with pytest.raises(TypeError):
            BadStore()  # type: ignore


class TestJsonFileStore:
    @pytest.mark.asyncio
    async def test_put_and_get(self, tmp_path: Path):
        """写入后可读取"""
        store = JsonFileStore(base_path=tmp_path)
        item = await store.put("k1", "hello", namespace=("working", "test"))
        assert item.key == "k1"
        assert item.value == "hello"

        retrieved = await store.get("k1", namespace=("working", "test"))
        assert retrieved is not None
        assert retrieved.key == "k1"
        assert retrieved.value == "hello"

    @pytest.mark.asyncio
    async def test_get_not_found(self, tmp_path: Path):
        """不存在的 key 返回 None"""
        store = JsonFileStore(base_path=tmp_path)
        result = await store.get("nonexistent", namespace=("working", "test"))
        assert result is None

    @pytest.mark.asyncio
    async def test_get_wrong_namespace(self, tmp_path: Path):
        """在不同 namespace 中读取不到"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "hello", namespace=("working", "a"))
        result = await store.get("k1", namespace=("working", "b"))
        assert result is None

    @pytest.mark.asyncio
    async def test_put_overwrites(self, tmp_path: Path):
        """相同 key 覆盖写入"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("working", "test"))
        await store.put("k1", "v2", namespace=("working", "test"))
        retrieved = await store.get("k1", namespace=("working", "test"))
        assert retrieved is not None
        assert retrieved.value == "v2"

    @pytest.mark.asyncio
    async def test_put_with_dict_value(self, tmp_path: Path):
        """value 可以是任意 JSON 可序列化对象"""
        store = JsonFileStore(base_path=tmp_path)
        data = {"rating": "看涨", "score": 85, "tags": ["价值", "龙头"]}
        await store.put("analysis", data, namespace=("working", "buffett", "user_001"))
        retrieved = await store.get("analysis", namespace=("working", "buffett", "user_001"))
        assert retrieved is not None
        assert retrieved.value["rating"] == "看涨"
        assert retrieved.value["score"] == 85

    @pytest.mark.asyncio
    async def test_jsonl_append_only(self, tmp_path: Path):
        """情景记忆（.jsonl）多次 put 不覆盖"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("q1", "第一问", namespace=("episodic", "buffett", "u1"))
        await store.put("q2", "第二问", namespace=("episodic", "buffett", "u1"))

        file_path = tmp_path / "episodic" / "buffett" / "u1.jsonl"
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_auto_creates_directory(self, tmp_path: Path):
        """put 自动创建不存在的目录"""
        store = JsonFileStore(base_path=tmp_path)
        deep_ns = ("working", "deep", "nested", "path")
        await store.put("k", "v", namespace=deep_ns)
        retrieved = await store.get("k", namespace=deep_ns)
        assert retrieved is not None
        assert retrieved.value == "v"

"""tests for MemoryItem, MemoryStore ABC, and JsonFileStore"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.memory.store import MemoryItem, MemoryStore


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

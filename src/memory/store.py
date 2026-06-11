"""命名空间记忆存储系统（MemoryStore 接口 + JsonFileStore 实现）"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """存储层返回的记忆条目

    通过 namespace 区分记忆类型和所属 Agent/用户。
    score 字段为 search() 结果的相关性评分（JSON 存储默认为 0.0，向量存储返回相似度）。
    """

    key: str
    value: Any
    namespace: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    score: float = 0.0


class MemoryStoreError(Exception):
    """记忆存储操作异常基类"""


class MemoryStore(ABC):
    """记忆存储的抽象接口

    所有后端实现（JsonFileStore / SqliteStore / ChromaStore）必须实现此接口。
    消费者通过此接口操作记忆，不依赖具体存储实现。
    """

    @abstractmethod
    async def get(self, key: str, namespace: tuple[str, ...] = ()) -> MemoryItem | None:
        """根据 key 和 namespace 读取一条记忆。不存在时返回 None。"""

    @abstractmethod
    async def put(
        self, key: str, value: Any, namespace: tuple[str, ...] = ()
    ) -> MemoryItem:
        """写入/覆盖一条记忆。key 已存在时覆盖（upsert）。"""

    @abstractmethod
    async def search(
        self,
        namespace: tuple[str, ...] = (),
        query: str | None = None,
        k: int = 10,
    ) -> list[MemoryItem]:
        """搜索 namespace 下的记忆条目。

        纯 JSON 存储做前缀匹配 + 全量返回（忽略 query 和 k 做过滤）。
        向量存储实现用 query 做语义检索，k 控制返回条数。
        """

    @abstractmethod
    async def delete(self, key: str, namespace: tuple[str, ...] = ()) -> bool:
        """删除一条记忆。不存在时返回 False，删除成功返回 True。"""

    @abstractmethod
    async def list_namespaces(self) -> list[tuple[str, ...]]:
        """返回所有已存在的 namespace 列表"""

    @abstractmethod
    async def list_keys(self, namespace: tuple[str, ...] = ()) -> list[str]:
        """返回指定 namespace 下的所有 key 列表"""

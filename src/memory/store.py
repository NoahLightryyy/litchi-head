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


_JSONL_TYPES = frozenset({"episodic", "reflective"})


class JsonFileStore(MemoryStore):
    """基于 JSON/JSONL 文件的 MemoryStore 实现（MVP，零外部依赖）

    文件组织：
      data/memory/{type}/{role}/{user_id}.json     —— 单对象（working / semantic）
      data/memory/{type}/{role}/{user_id}.jsonl    —— JSONL（episodic / reflective）

    命名空间到文件路径的映射：
      ("episodic", "buffett", "user_001") → data/memory/episodic/buffett/user_001.jsonl
      ("working", "master", "user_001") → data/memory/working/master/user_001.json
    """

    def __init__(self, base_path: str | Path = "data/memory"):
        self._base_path = Path(base_path)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, path: Path) -> asyncio.Lock:
        str_path = str(path)
        if str_path not in self._locks:
            self._locks[str_path] = asyncio.Lock()
        return self._locks[str_path]

    def _file_path(self, namespace: tuple[str, ...]) -> Path:
        if not namespace:
            raise ValueError("namespace 不能为空")
        ext = ".jsonl" if namespace[0] in _JSONL_TYPES else ".json"
        return self._base_path.joinpath(*namespace).with_suffix(ext)

    async def get(self, key: str, namespace: tuple[str, ...] = ()) -> MemoryItem | None:
        path = self._file_path(namespace)
        if not path.exists():
            return None

        try:
            async with self._lock_for(path):
                data = await asyncio.to_thread(self._read_all, path)
        except (json.JSONDecodeError, OSError) as e:
            raise MemoryStoreError(f"读取记忆文件失败: {path}") from e

        if path.suffix == ".jsonl":
            for record in reversed(data):
                if record.get("key") == key:
                    return MemoryItem(
                        key=key,
                        value=record.get("data"),
                        namespace=namespace,
                        created_at=datetime.fromisoformat(record["timestamp"]),
                        updated_at=datetime.fromisoformat(record["timestamp"]),
                    )
            return None
        else:
            if key not in data:
                return None
            return MemoryItem(
                key=key,
                value=data[key],
                namespace=namespace,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    async def put(
        self, key: str, value: Any, namespace: tuple[str, ...] = ()
    ) -> MemoryItem:
        path = self._file_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now()

        def _write() -> None:
            if path.suffix == ".jsonl":
                record = {"key": key, "timestamp": now.isoformat(), "data": value}
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            else:
                if path.exists():
                    with open(path, encoding="utf-8") as f:
                        existing = json.load(f)
                else:
                    existing = {}
                existing[key] = value
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)

        async with self._lock_for(path):
            await asyncio.to_thread(_write)

        return MemoryItem(
            key=key,
            value=value,
            namespace=namespace,
            created_at=now,
            updated_at=now,
        )

    def _read_all(self, path: Path) -> dict | list[dict]:
        """读取文件全部内容，返回 dict（JSON）或 list[dict]（JSONL）"""
        if path.suffix == ".jsonl":
            records: list[dict] = []
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            return records
        else:
            with open(path, encoding="utf-8") as f:
                return json.load(f)

    # ── Task 4 实现 ──

    async def search(
        self,
        namespace: tuple[str, ...] = (),
        query: str | None = None,
        k: int = 10,
    ) -> list[MemoryItem]:
        return []

    async def delete(self, key: str, namespace: tuple[str, ...] = ()) -> bool:
        return False

    async def list_namespaces(self) -> list[tuple[str, ...]]:
        return []

    async def list_keys(self, namespace: tuple[str, ...] = ()) -> list[str]:
        return []

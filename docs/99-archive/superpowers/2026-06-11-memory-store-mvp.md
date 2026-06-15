# 命名空间记忆存储 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现命名空间记忆存储系统 MVP（MemoryStore 接口 + JsonFileStore 实现 + MemoryManager 高层封装）

**Architecture:** `MemoryStore(ABC)` 定义存取契约，`JsonFileStore` 基于 JSON/JSONL 文件实现，`MemoryManager` 提供面向消费者的 `remember()`/`recall()` 语义化接口。三层命名空间 `("memory_type", "agent_role", "user_id")` 隔离 Agent 视角。

**Tech Stack:** Python 3.12+, Pydantic BaseModel, asyncio, JSON/JSONL, pytest (tmp_path)

---

## File Structure

```
src/memory/
├── __init__.py            # MODIFY — 追加 store/manager 导出
├── knowledge_base.py      # 不动
├── skill_disk.py           # 不动
├── store.py               # CREATE — MemoryStore(ABC) + MemoryItem + JsonFileStore
└── manager.py             # CREATE — MemoryManager 高层封装

tests/
├── test_memory_store.py   # CREATE — JsonFileStore 单元测试
└── test_memory_manager.py # CREATE — MemoryManager 单元测试
```

---

### Task 1: 数据模型定义

**Files:**
- Create: `src/memory/store.py` (第 1 部分 — 模型)

**Step 1.1: 编写测试 — 验证 MemoryItem 模型**

```python
"""tests/test_memory_store.py — MemoryItem Pydantic 模型测试"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.memory.store import MemoryItem


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
```

**Step 1.2: 运行测试验证失败**

Run: `python -m pytest tests/test_memory_store.py::TestMemoryItem -v`
Expected: FAIL — ModuleNotFoundError (store.py 不存在)

**Step 1.3: 创建 MemoryItem 模型**

```python
"""src/memory/store.py — 命名空间记忆存储系统（MemoryStore 接口 + JsonFileStore 实现）"""

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
```

**Step 1.4: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_store.py::TestMemoryItem -v`
Expected: 3 PASSED

**Step 1.5: Commit**

```bash
git add tests/test_memory_store.py src/memory/store.py
git commit -m "feat: MemoryItem Pydantic 模型定义"
```

---

### Task 2: MemoryStore 抽象接口

**Files:**
- Modify: `src/memory/store.py` (追加 MemoryStore ABC)

**Step 2.1: 编写测试 — 验证 MemoryStore 接口**

```python
"""tests/test_memory_store.py — (追加到 TestMemoryItem 之后)"""

from src.memory.store import MemoryStore


class TestMemoryStoreInterface:
    def test_cannot_instantiate_abc(self):
        """MemoryStore 是抽象类，不能直接实例化"""
        with pytest.raises(TypeError):
            MemoryStore()  # type: ignore

    def test_subclass_must_implement_all_methods(self):
        """未实现所有抽象方法的子类不能实例化"""
        class BadStore(MemoryStore):
            async def get(self, key, namespace=()):  # 缺少 put/search 等
                return None

        with pytest.raises(TypeError):
            BadStore()  # type: ignore
```

**Step 2.2: 运行测试验证失败**

Run: `python -m pytest tests/test_memory_store.py::TestMemoryStoreInterface -v`
Expected: 2 FAILED (MemoryStore not defined 或 not abstract)

**Step 2.3: 创建 MemoryStore ABC**

```python
# 追加到 src/memory/store.py 的末尾（在 MemoryItem 之后）

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
```

**Step 2.4: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_store.py::TestMemoryStoreInterface -v`
Expected: 2 PASSED

**Step 2.5: Commit**

```bash
git add src/memory/store.py tests/test_memory_store.py
git commit -m "feat: MemoryStore 抽象接口定义"
```

---

### Task 3: JsonFileStore — put / get 实现

**Files:**
- Modify: `src/memory/store.py` (追加 JsonFileStore 类)

**Step 3.1: 编写测试 — JsonFileStore 基础 CRUD**

```python
"""tests/test_memory_store.py — (追加 TestJsonFileStore 测试类)"""

from pathlib import Path

import pytest

from src.memory.store import JsonFileStore, MemoryItem


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

        # 验证文件行数
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
```

**Step 3.2: 运行测试验证失败**

Run: `python -m pytest tests/test_memory_store.py::TestJsonFileStore -v`
Expected: FAIL — JsonFileStore not defined

**Step 3.3: 实现 JsonFileStore**

```python
# 追加到 src/memory/store.py（MemoryStore 类之后）

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

        async with self._lock_for(path):
            data = await asyncio.to_thread(self._read_all, path)

        if path.suffix == ".jsonl":
            # JSONL — 找最后一条匹配 key 的记录
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
            # 单对象 JSON — 直接查 key
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

        async def _write() -> None:
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

    def _read_all(self, path: Path) -> Any:
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
```

**Step 3.4: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_store.py::TestJsonFileStore -v`
Expected: 7 PASSED

**Step 3.5: Commit**

```bash
git add src/memory/store.py tests/test_memory_store.py
git commit -m "feat: JsonFileStore put/get 实现"
```

---

### Task 4: JsonFileStore — search / delete / list

**Files:**
- Modify: `src/memory/store.py` (追加 search/delete/list_namespaces/list_keys)
- Modify: `tests/test_memory_store.py` (追加测试)

**Step 4.1: 编写测试**

```python
# 追加到 TestJsonFileStore 类中

    @pytest.mark.asyncio
    async def test_search_by_prefix(self, tmp_path: Path):
        """search() 用 namespace 前缀匹配"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("working", "a"))
        await store.put("k2", "v2", namespace=("working", "b"))
        await store.put("k3", "v3", namespace=("episodic", "a"))

        results = await store.search(namespace=("working",))
        assert len(results) == 2
        keys = {r.key for r in results}
        assert keys == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_search_empty_namespace(self, tmp_path: Path):
        """空 namespace 返回所有"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("a",))
        await store.put("k2", "v2", namespace=("b",))
        results = await store.search(namespace=())
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_empty_result(self, tmp_path: Path):
        """搜索不存在的 namespace 返回空列表"""
        store = JsonFileStore(base_path=tmp_path)
        results = await store.search(namespace=("nonexistent",))
        assert results == []

    @pytest.mark.asyncio
    async def test_delete_existing(self, tmp_path: Path):
        """删除存在的 key"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("working", "test"))
        deleted = await store.delete("k1", namespace=("working", "test"))
        assert deleted is True
        result = await store.get("k1", namespace=("working", "test"))
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_path: Path):
        """删除不存在的 key 返回 False"""
        store = JsonFileStore(base_path=tmp_path)
        deleted = await store.delete("nothing", namespace=("working", "test"))
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_namespaces(self, tmp_path: Path):
        """list_namespaces 返回所有已创建的 namespace"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("a", "b"))
        await store.put("k2", "v2", namespace=("a", "c"))
        await store.put("k3", "v3", namespace=("d",))

        namespaces = await store.list_namespaces()
        assert ("a", "b") in namespaces
        assert ("a", "c") in namespaces
        assert ("d",) in namespaces

    @pytest.mark.asyncio
    async def test_list_keys(self, tmp_path: Path):
        """list_keys 返回指定 namespace 下的所有 key"""
        store = JsonFileStore(base_path=tmp_path)
        await store.put("k1", "v1", namespace=("working", "test"))
        await store.put("k2", "v2", namespace=("working", "test"))
        await store.put("not_me", "v3", namespace=("other",))

        keys = await store.list_keys(namespace=("working", "test"))
        assert sorted(keys) == ["k1", "k2"]
```

**Step 4.2: 运行测试验证失败**

Run: `python -m pytest tests/test_memory_store.py::TestJsonFileStore -v`
Expected: 7 FAILED (methods not implemented)

**Step 4.3: 实现 search / delete / list 方法**

```python
# 追加到 JsonFileStore 类的 get/put 方法之后

    async def search(
        self,
        namespace: tuple[str, ...] = (),
        query: str | None = None,
        k: int = 10,
    ) -> list[MemoryItem]:
        results: list[MemoryItem] = []
        search_dir = self._base_path.joinpath(*namespace) if namespace else self._base_path

        if not search_dir.exists():
            return []

        # 遍历文件，匹配 namespace 前缀
        if namespace:
            # 精确 namespace 模式
            path = self._file_path(namespace)
            if path.exists():
                items = await self._search_in_file(path, namespace)
                results.extend(items)
        else:
            # 扫描整个 base_path
            for suffix in (".json", ".jsonl"):
                for fpath in search_dir.rglob(f"*{suffix}"):
                    rel_path = fpath.relative_to(self._base_path)
                    ns = tuple(rel_path.with_suffix("").parts)
                    items = await self._search_in_file(fpath, ns)
                    results.extend(items)

        return results[:k]

    async def _search_in_file(
        self, path: Path, ns: tuple[str, ...]
    ) -> list[MemoryItem]:
        """读取一个文件返回其所有条目"""
        if not path.exists():
            return []
        async with self._lock_for(path):
            data = await asyncio.to_thread(self._read_all, path)

        items: list[MemoryItem] = []
        if path.suffix == ".jsonl":
            for record in data:
                ts = datetime.fromisoformat(record["timestamp"])
                items.append(MemoryItem(
                    key=record["key"],
                    value=record.get("data"),
                    namespace=ns,
                    created_at=ts,
                    updated_at=ts,
                ))
        else:
            for key, val in data.items():
                items.append(MemoryItem(
                    key=key,
                    value=val,
                    namespace=ns,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ))
        return items

    async def delete(self, key: str, namespace: tuple[str, ...] = ()) -> bool:
        path = self._file_path(namespace)
        if not path.exists():
            return False

        async with self._lock_for(path):
            data = await asyncio.to_thread(self._read_all, path)

            if path.suffix == ".jsonl":
                original_count = len(data)
                data = [r for r in data if r.get("key") != key]
                if len(data) == original_count:
                    return False
                # 重写整个文件（去掉被删除的行）
                await asyncio.to_thread(self._write_jsonl, path, data)
            else:
                if key not in data:
                    return False
                del data[key]
                await asyncio.to_thread(self._write_json, path, data)

        return True

    async def list_namespaces(self) -> list[tuple[str, ...]]:
        namespaces: set[tuple[str, ...]] = set()
        if not self._base_path.exists():
            return []
        for suffix in (".json", ".jsonl"):
            for fpath in self._base_path.rglob(f"*{suffix}"):
                rel = fpath.relative_to(self._base_path)
                ns = tuple(rel.with_suffix("").parts)
                namespaces.add(ns)
        return sorted(namespaces)

    async def list_keys(self, namespace: tuple[str, ...] = ()) -> list[str]:
        path = self._file_path(namespace)
        if not path.exists():
            return []

        async with self._lock_for(path):
            data = await asyncio.to_thread(self._read_all, path)

        if path.suffix == ".jsonl":
            return [r["key"] for r in data]
        else:
            return list(data.keys())

    # ── 文件写入辅助 ──

    def _write_json(self, path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _write_jsonl(self, path: Path, data: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

**Step 4.4: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_store.py::TestJsonFileStore -v`
Expected: 14 PASSED

**Step 4.5: 提交**

```bash
git add src/memory/store.py tests/test_memory_store.py
git commit -m "feat: JsonFileStore search/delete/list 实现"
```

---

### Task 5: 错误处理与边界情况

**Files:**
- Modify: `src/memory/store.py` (追加 MemoryStoreError 已定义)
- Modify: `tests/test_memory_store.py` (追加边界测试)

**Step 5.1: 编写边界测试**

```python
# 追加到 TestJsonFileStore 类末尾

    @pytest.mark.asyncio
    async def test_empty_namespace_raises(self, tmp_path: Path):
        """空 namespace 抛出 ValueError"""
        store = JsonFileStore(base_path=tmp_path)
        with pytest.raises(ValueError, match="namespace 不能为空"):
            await store.put("k", "v", namespace=())

    @pytest.mark.asyncio
    async def test_corrupted_json_file(self, tmp_path: Path):
        """损坏的 JSON 文件抛出 MemoryStoreError"""
        store = JsonFileStore(base_path=tmp_path)
        file_path = tmp_path / "working" / "test.json"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("不是一个合法的 JSON", encoding="utf-8")

        with pytest.raises(MemoryStoreError):
            await store.get("k", namespace=("working", "test"))

    @pytest.mark.asyncio
    async def test_file_with_only_newlines(self, tmp_path: Path):
        """空 JSONL 文件不报错"""
        store = JsonFileStore(base_path=tmp_path)
        file_path = tmp_path / "episodic" / "test.jsonl"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("\n\n\n", encoding="utf-8")

        result = await store.get("anything", namespace=("episodic", "test"))
        assert result is None

    @pytest.mark.asyncio
    async def test_put_empty_value(self, tmp_path: Path):
        """value 可以是 None 或空结构"""
        store = JsonFileStore(base_path=tmp_path)
        item = await store.put("null_val", None, namespace=("working", "test"))
        assert item.value is None

        retrieved = await store.get("null_val", namespace=("working", "test"))
        assert retrieved is not None
        assert retrieved.value is None
```

**Step 5.2: 更新 JsonFileStore.get() 增加异常处理**

```python
# 在 JsonFileStore.get() 中，读取时加 try/except
    async def get(self, key: str, namespace: tuple[str, ...] = ()) -> MemoryItem | None:
        path = self._file_path(namespace)
        if not path.exists():
            return None

        try:
            async with self._lock_for(path):
                data = await asyncio.to_thread(self._read_all, path)
        except (json.JSONDecodeError, OSError) as e:
            raise MemoryStoreError(f"读取记忆文件失败: {path}") from e

        # ... 后续逻辑不变
```

把同样的 try/except 加到 `_search_in_file` 和 `delete` 中。

**Step 5.3: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_store.py -v`
Expected: 18 PASSED

**Step 5.4: Commit**

```bash
git add src/memory/store.py tests/test_memory_store.py
git commit -m "feat: JsonFileStore 错误处理与边界情况"
```

---

### Task 6: MemoryManager 高层封装

**Files:**
- Create: `src/memory/manager.py`
- Create: `tests/test_memory_manager.py`

**Step 6.1: 编写测试**

```python
"""tests/test_memory_manager.py — MemoryManager 高层封装测试"""

from pathlib import Path

import pytest

from src.memory.manager import MemoryManager
from src.memory.store import JsonFileStore, MemoryItem


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
```

**Step 6.2: 运行测试验证失败**

Run: `python -m pytest tests/test_memory_manager.py -v`
Expected: 6 FAILED — ModuleNotFoundError

**Step 6.3: 实现 MemoryManager**

```python
"""src/memory/manager.py — MemoryManager 高层封装

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
```

**Step 6.4: 运行测试验证通过**

Run: `python -m pytest tests/test_memory_manager.py -v`
Expected: 6 PASSED

**Step 6.5: Commit**

```bash
git add src/memory/manager.py tests/test_memory_manager.py
git commit -m "feat: MemoryManager 高层封装"
```

---

### Task 7: 更新 `__init__.py` 导出 + 全量测试

**Files:**
- Modify: `src/memory/__init__.py`

**Step 7.1: 更新导出**

```python
"""Memory module — 知识库 + 技能盘 + 记忆存储"""

from src.memory.knowledge_base import KnowledgeBase
from src.memory.manager import MemoryManager
from src.memory.skill_disk import MasterSkill, SkillDisk
from src.memory.store import JsonFileStore, MemoryItem, MemoryStore, MemoryStoreError

__all__ = [
    "KnowledgeBase",
    "MasterSkill",
    "MemoryItem",
    "MemoryManager",
    "MemoryStore",
    "MemoryStoreError",
    "JsonFileStore",
    "SkillDisk",
]
```

**Step 7.2: 全量测试**

Run: `python -m pytest tests/test_memory_store.py tests/test_memory_manager.py -v`
Expected: 24 PASSED (18 store + 6 manager)

Run: `make check` (或 `python -m pytest tests/ -v --tb=short`)
Expected: 302 + N 通过（原 302 + 新 24 ≈ 326 passed）

**Step 7.3: 提交**

```bash
git add src/memory/__init__.py
git commit -m "feat: 更新 memory __init__ 导出 MemoryStore/MemoryManager"
```

---

### Task 8: 全量回归验证

**Step 8.1: 运行 `make check`**

```bash
cd /path/to/project
make check
```

Run: `ruff check src/memory/ tests/test_memory_store.py tests/test_memory_manager.py`
Expected: 0 errors

Run: `pyright src/memory/`
Expected: 0 errors

Run: `python -m pytest tests/ -v --tb=short`
Expected: ~326 passed, 8 skipped

**Step 8.2: 如果 Pyright 报类型错误，修复**

常见问题及修复：
```python
# MemoryItem.value: Any → 不需要 import 额外类型
# JsonFileStore._read_all → 返回类型可以是 dict | list[dict]
# 在 _read_all 上加类型: -> dict | list[dict]  (Python 3.10+)

def _read_all(self, path: Path) -> dict | list[dict]:
    ...
```

**Step 8.3: 最终提交**

```bash
git add -A
git commit -m "chore: 全量回归验证 — memory MVP 24 测试通过"
```

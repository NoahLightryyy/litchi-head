# 命名空间记忆存储系统 — 设计文档

> 版本：v1.0 · 2026-06-11
> 状态：✅ **已实现**（MVP 交付，331 tests）
> 关联：ADR-011（架构决策）| ADR-006（三层记忆）| `src/memory/`

---

## 目录

- [1. 设计目标](#1-设计目标)
- [2. 架构总览](#2-架构总览)
- [3. 核心接口：MemoryStore](#3-核心接口-memorystore)
- [4. 命名空间规范](#4-命名空间规范)
- [5. MVP 实现：JsonFileStore](#5-mvp-实现-jsonfilestore)
- [6. 数据模型](#6-数据模型)
- [7. 消费者使用方式](#7-消费者使用方式)
- [8. 错误处理与边界情况](#8-错误处理与边界情况)
- [9. 测试策略](#9-测试策略)
- [10. 未来扩展路径](#10-未来扩展路径)

---

## 1. 设计目标

### 1.1 核心目标

一套可扩展的记忆存储体系，满足以下约束：

```
📐 接口抽象 → 存储后端可替换（JSON → SQLite → 向量）
🔖 命名空间 → Agent 视角隔离 + 跨 Agent 共享
📦 零依赖  → MVP 仅用 Python 标准库，纯本地逻辑，不依赖 API
🧪 可测试  → 所有核心逻辑可在无网络/无 API Key 环境下验证
📈 渐进式  → 今天能用，明天能升级，不重写
```

### 1.2 非目标

- ❌ **不是 LLM 反思引擎** — 反思逻辑在三层记忆的"反思层"，不在存储层
- ❌ **不是 Agent 运行时记忆管理器** — `remember()` / `recall()` 等高层 API 在消费者侧或专属 Manager 中实现
- ❌ **不是分布式存储** — MVP 单机文件系统，不上网络

---

## 2. 架构总览

```
┌────────────────────────────────────────────────────────────┐
│  消费者层 (Consumer)                                        │
│  MasterAgent / DebateOrchestrator / 镜子 Agent / XiaoZhi   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MemoryManager（可选高层封装）                        │  │
│  │  remember(key, value, namespace) → store.put()       │  │
│  │  recall(query, namespace) → store.search()           │  │
│  │  get_session_context(session_id) → working memory    │  │
│  └──────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────┤
│  存储层 (Store Layer)                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  MemoryStore (Protocol / ABC)                        │  │
│  │  get(key, namespace) → value                         │  │
│  │  put(key, namespace, value) → None                   │  │
│  │  search(namespace, query, k) → list[MemoryItem]      │  │
│  │  delete(key, namespace) → bool                      │  │
│  │  list_keys(namespace) → list[str]                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│           ┌──────────────┼──────────────┐                    │
│           ▼              ▼              ▼                    │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │JsonFileStore│ │SqliteStore │ │ChromaStore │               │
│  │ (MVP)      │ │ (将来)     │ │ (将来)     │               │
│  └────────────┘ └────────────┘ └────────────┘               │
└────────────────────────────────────────────────────────────┘
```

### 2.1 分层职责

| 层 | 职责 | 变化频率 |
|:---|:-----|:--------:|
| **消费者** | 调用 `Store` 做读写，不关心具体存储实现 | 中（随业务变） |
| **MemoryManager** | 可选封装层，提供 `remember()`/`recall()` 语义化接口 | 低（稳定后少变） |
| **MemoryStore 接口** | 定义存取的契约，所有实现必须遵守 | **极低（不可轻易改）** |
| **具体 Store 实现** | 真实施行数据持久化 | 中（随存储技术选型变） |

> 核心设计原则：**接口的稳定性 > 实现的丰富性**。消费者隔离在接口之上，实现随便换。

---

## 3. 核心接口：MemoryStore

### 3.1 接口定义

```python
class MemoryItem(BaseModel):
    """存储层返回的记忆条目"""
    key: str
    value: Any  # JSON-serializable
    namespace: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    score: float = 0.0  # search() 返回时的相关性评分


class MemoryStore(ABC):
    """记忆存储的抽象接口——所有后端实现必须遵循"""

    @abstractmethod
    async def get(
        self, key: str, namespace: tuple[str, ...] = ()
    ) -> MemoryItem | None: ...

    @abstractmethod
    async def put(
        self, key: str, value: Any, namespace: tuple[str, ...] = ()
    ) -> MemoryItem: ...

    @abstractmethod
    async def search(
        self,
        namespace: tuple[str, ...] = (),
        query: str | None = None,
        k: int = 10,
    ) -> list[MemoryItem]: ...

    @abstractmethod
    async def delete(
        self, key: str, namespace: tuple[str, ...] = ()
    ) -> bool: ...

    @abstractmethod
    async def list_namespaces(self) -> list[tuple[str, ...]]: ...

    @abstractmethod
    async def list_keys(
        self, namespace: tuple[str, ...] = ()
    ) -> list[str]: ...
```

### 3.2 设计要点

- **所有方法 async** — 后续 SQLite/网络存储天然异步，MVP 的 JsonFileStore 可用 `asyncio.to_thread()` 包装
- **namespace 是变长 tuple** — `("type", ...)` 支持任意深度的层级
- **query 参数预留为 `str | None`** — 纯 JSON 存储忽略 query 参数做前缀匹配，向量存储做语义检索
- **MemoryItem.score** — search 排名得分，JSON 版本返回 0.0（不做语义排名），向量版本返回相似度

---

## 4. 命名空间规范

### 4.1 三层命名空间约定

```
("memory_type", "agent_role", "user_id")
```

| 层级 | 取值 | 含义 |
|:----|:-----|:-----|
| **memory_type** | `working` / `episodic` / `reflective` / `semantic` | 记忆类型，继承 ADR-006 |
| **agent_role** | `buffett` / `munger` / `lynch` / `graham` / ... 或 `global` | Agent 角色，`global` 表示跨 Agent 共享 |
| **user_id** | 用户标识符（如 `user_001`） | 用户级隔离 |

### 4.2 记忆类型定义

| 类型 | namespace | 存储模式 | 用途 | 生命周期 |
|:----|:----------|:--------:|:-----|:--------|
| **工作记忆** | `("working", role, user)` | 覆盖写入 (upsert) | 当前 Session 的中间上下文 | Session 内，可选持久化 |
| **情景记忆** | `("episodic", role, user)` | Append-only 追加 | 历史决策、查询、交易记录 | 永久保留 |
| **反思记忆** | `("reflective", role, user)` | Append-only 追加 | LLM 驱动的交易后复盘 | 永久保留 |
| **语义画像** | `("semantic", "global", user)` | 覆盖写入 (upsert) | 用户的全局偏好、风险画像、投资风格 | 永久保留 |

### 4.3 跨 Agent 共享机制

- **全局共享**：namespace 的 `agent_role = "global"`，所有 Agent 可读
  - 例如 `("semantic", "global", "user_001")` 存放用户的风险偏好画像
  - 工作记忆也支持全局 namespace：`("working", "global", "user_001")` 跨 Agent 共享上下文
- **跨 Agent 查询**：使用前缀搜索 `search(("episodic",))` 返回所有 Agent 的情景记忆（供镜子 Agent 做综合分析）

---

## 5. MVP 实现：JsonFileStore

### 5.1 文件组织

```
data/memory/
├── working/
│   ├── buffett/
│   │   └── user_001.json        # 单对象 JSON（可覆盖）
│   └── global/
│       └── user_001.json
├── episodic/
│   ├── buffett/
│   │   └── user_001.jsonl       # JSONL 格式（append-only）
│   └── graham/
│       └── user_001.jsonl
├── reflective/
│   └── mirror/
│       └── user_001.jsonl
└── semantic/
    └── global/
        └── user_001.json
```

### 5.2 存储格式

**单对象 JSON（工作记忆 / 语义画像）**：
```json
{
  "current_session": {
    "session_id": "sess_abc123",
    "started_at": "2026-06-11T09:00:00",
    "last_query": "分析贵州茅台"
  },
  "intermediate_results": {
    "step_1": "已获取茅台行情",
    "step_2": "已获取茅台新闻"
  }
}
```

**JSONL（情景记忆 / 反思记忆）**：
```jsonl
{"key": "query_001", "timestamp": "2026-06-11T09:00:00", "data": {"query": "分析贵州茅台", "result": "..."}, "metadata": {"importance": 0.8}}
{"key": "query_002", "timestamp": "2026-06-11T09:05:00", "data": {"query": "比较茅台和五粮液", "result": "..."}, "metadata": {"importance": 0.6}}
```

> JSONL 每行一条记录，追加写入，天然支持 append-only。读取时全量加载或按行流式读取。

### 5.3 实现要点

```python
import asyncio
import json
from pathlib import Path


class JsonFileStore(MemoryStore):
    """基于 JSON/JSONL 文件的 MemoryStore 实现（MVP，零外部依赖）"""

    def __init__(self, base_path: str | Path = "data/memory"):
        self._base_path = Path(base_path)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, path: Path) -> asyncio.Lock:
        str_path = str(path)
        if str_path not in self._locks:
            self._locks[str_path] = asyncio.Lock()
        return self._locks[str_path]

    def _file_path(self, namespace: tuple[str, ...]) -> Path:
        ext = ".jsonl" if namespace[0] in ("episodic", "reflective") else ".json"
        return self._base_path.joinpath(*namespace).with_suffix(ext)

    async def put(self, key: str, value: Any, namespace: tuple[str, ...] = ()) -> MemoryItem:
        path = self._file_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)

        async def _write():
            if path.suffix == ".jsonl":
                record = {"key": key, "timestamp": datetime.now().isoformat(), "data": value}
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

        return MemoryItem(key=key, value=value, namespace=namespace,
                         created_at=datetime.now(), updated_at=datetime.now())
```

### 5.4 线程安全

- 每个文件操作使用 `asyncio.Lock()` 粒度的锁（每个 namespace 一个锁，非全局锁）
- JSONL 的 append 操作是原子性的（单行写入）
- 单对象 JSON 的读写需要完整读取→修改→写入，使用锁保护临界区

---

## 6. 数据模型

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


class MemoryItem(BaseModel):
    """存储层返回的记忆条目"""
    key: str
    value: Any
    namespace: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    score: float = 0.0


class WorkingMemoryData(BaseModel):
    """工作记忆的数据结构（消费者使用时的推荐格式）"""
    session_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    queries: list[dict] = Field(default_factory=list)
    intermediate_results: dict[str, Any] = Field(default_factory=dict)
    current_focus: str | None = None


class EpisodicRecord(BaseModel):
    """情景记忆的单条记录"""
    event_type: str  # "query" | "trade" | "analysis"
    timestamp: datetime = Field(default_factory=datetime.now)
    query: str
    result_summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = 0.5  # 0.0~1.0，为未来的衰减排名预留


class SemanticProfile(BaseModel):
    """用户语义画像（全局共享）"""
    risk_tolerance: str | None = None  # "保守" | "稳健" | "进取"
    preferred_stocks: list[str] = Field(default_factory=list)
    investment_horizon: str | None = None  # "短期" | "中期" | "长期"
    common_mistakes: list[str] = Field(default_factory=list)
    knowledge_level: str | None = None  # "新手" | "中级" | "资深"
```

---

## 7. 消费者使用方式

### 7.1 最简使用（直接操作 Store）

```python
from src.memory.store import JsonFileStore

store = JsonFileStore()

# 保存工作记忆
await store.put("session_context", {"focus": "茅台分析"}, namespace=("working", "buffett", "user_001"))

# 读取工作记忆
ctx = await store.get("session_context", namespace=("working", "buffett", "user_001"))

# 追加情景记忆
await store.put("query_003", {"query": "茅台PE", "result": "28.5"}, namespace=("episodic", "buffett", "user_001"))

# 搜索所有 Agent 对用户001的情景记忆
all_episodes = await store.search(namespace=("episodic",), k=50)
```

### 7.2 通过 MemoryManager（推荐）

```python
from src.memory.manager import MemoryManager

mem = MemoryManager(store=JsonFileStore(), user_id="user_001")

# Agent 记录当前分析
await mem.remember(
    agent="buffett",
    memory_type="working",
    key="current_analysis",
    value={"stock": "000001", "rating": "看涨", "score": 85},
)

# 镜子 Agent 获取用户全部历史
history = await mem.recall_all_agents(memory_type="episodic")

# 获取用户全局画像
profile = await mem.get_profile()
```

---

## 8. 错误处理与边界情况

| 场景 | 行为 |
|:----|:-----|
| **文件不存在** | `get()` 返回 `None`，不抛异常 |
| **namespace 目录不存在** | `put()` 自动创建目录（`mkdir(parents=True)`） |
| **JSON 文件损坏** | 抛 `MemoryStoreError`（含文件路径），上层捕获后重建或跳过 |
| **并发写入同一文件** | `asyncio.Lock()` 按 namespace 粒度保护 |
| **超大文件（>100MB）** | `search()` 读全量时可能 OOM，后续版本需加流式读取优化 |
| **特深 namespace** | 文件系统路径长度限制（Windows 260 字符限制，控制 depth ≤ 4） |
| **key 冲突** | `put()` 覆盖写入（upsert），不报错 |

---

## 9. 测试策略

### 9.1 单元测试（核心接口）

| 测试级 | 覆盖内容 | 数量估计 | 运行环境 |
|:------|:---------|:--------:|:--------|
| 单元 | `MemoryStore` 抽象类验证 | 3-5 | 无依赖 |
| 单元 | `JsonFileStore` 基础 CRUD | 10-15 | 临时目录 |
| 单元 | `JsonFileStore` 边界条件（损坏文件、空文件、超大文件） | 5-8 | 临时目录 |
| 单元 | 命名空间路径映射正确性 | 5 | 无依赖 |
| 单元 | 并发写入安全性 | 3 | asyncio |

### 9.2 使用 `tmp_path`（pytest fixture）

```python
async def test_json_store_put_get(tmp_path: Path):
    store = JsonFileStore(base_path=tmp_path)
    item = await store.put("k1", {"hello": "world"}, namespace=("working", "test"))
    assert item.key == "k1"

    retrieved = await store.get("k1", namespace=("working", "test"))
    assert retrieved is not None
    assert retrieved.value == {"hello": "world"}
```

### 9.3 测试注意事项

- 所有测试使用 `tmp_path`，不写真实 `data/memory/` 目录
- 异步测试需要 `@pytest.mark.asyncio`（当前项目已有 `pytest-asyncio` 依赖）
- 需 mock 文件损坏等异常场景（写入非法 JSON 后测试读）

---

## 10. 未来扩展路径

### Phase 1 — MVP（本阶段实现）
```
存储：JsonFileStore（纯 JSON/JSONL）
功能：CRUD + 命名空间 + 基本搜索（前缀匹配）
测试：20-30 个单元测试
```

### Phase 1+ — SQLite 升级
```
存储：SqliteStore（SQLite 单文件，标准库 sqlite3）
优势：支持 SQL 查询（按时间范围、按 event_type 过滤）
迁移：实现 SqliteStore(MemoryStore) → 切换 store = SqliteStore()
```

### Phase 2 — 向量语义检索
```
存储：ChromaStore（ChromaDB / FAISS）
优势：search(query) 做语义相似度排名，支持遗忘曲线衰减
迁移：实现 ChromaStore(MemoryStore) → 切换 store = ChromaStore()
```

### Phase 2+ — 反思引擎
```
组件：ReflectionEngine（在 MemoryManager 基础上）
功能：定期扫描情景记忆 → LLM 生成反思 → 存入 reflective namespace
前置：需要 API Key + 情景记忆积累到一定量
```

---

## 附录 A：竞品调研摘要

| 来源 | 借鉴点 | 在本设计中的体现 |
|:-----|:-------|:----------------|
| **TradingAgents-CN** | 5-lane 记忆隔离（bull/bear/trader） | 命名空间的 `agent_role` 维度实现同等隔离 |
| **TradingAgents-CN** | ChromaDB 可插拔 | `MemoryStore` 接口 + 多种实现 |
| **LangMem (LangChain)** | `BaseStore` 接口 + namespace template | `MemoryStore(ABC)` + tuple namespace |
| **LangMem** | 存储后端可替换（InMemory → Postgres） | 渐进式升级路径规划 |
| **TradingGPT** | 三层衰减 + 遗忘曲线 | 预留 `importance` 字段 + `score` 字段，衰减算法未来在 search() 中实现 |

---

## 附录 B：与现有模块的关系

| 现有模块 | 关系 | 操作 |
|:---------|:-----|:-----|
| `src/memory/knowledge_base.py` | 互补——KB 存**公开知识**，MemoryStore 存**用户私有记忆** | 不修改 |
| `src/memory/skill_disk.py` | 无关——SkillDisk 存大师人格定义 | 不修改 |
| `src/agents/master_agent.py` | 消费者——MasterAgent 可通过 MemoryStore 读写工作记忆 | 未来接入 |
| `src/agents/xiao_zhi.py` | 潜在消费者——教育小智可记录用户学习历史 | 未来接入 |
| `src/debate/orchestrator.py` | 潜在消费者——辩论过程可写入情景记忆 | 未来接入 |
| `src/utils/config.py` | 配置——存储路径可通过 settings 配置 | 可能需要新增配置项 |

---

> **文档版本**：v1.0 | **创建日期**：2026-06-11 | **关联 ADR**：ADR-006、ADR-011

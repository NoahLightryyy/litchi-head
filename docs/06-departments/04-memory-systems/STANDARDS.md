# 📐 记忆系统部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的记忆模块特定规范。

---

## 代码规范

### 存储抽象层

```python
# ✅ 正确：面向接口编程
class MemoryStore(ABC):
    @abstractmethod
    async def save(self, namespace: str, key: str, data: dict) -> None: ...
    @abstractmethod
    async def load(self, namespace: str, key: str) -> dict | None: ...
    @abstractmethod
    async def search(self, namespace: str, query: str) -> list[dict]: ...

# ✅ 具体实现可替换
class JsonFileStore(MemoryStore): ...  # 当前实现
class SqliteStore(MemoryStore): ...    # Phase 2 可切换

# ❌ 禁止：业务代码直接读写文件
with open("memory.json", "r") as f:  # 禁止
    data = json.load(f)
```

### 命名空间规范

```python
# 命名空间格式：{领域}:{子领域}

SAVE("debate:history", "stock_000001_2026-06-21", {...})   # 辩论历史
SAVE("agent:insight", "buffett_茅台分析", {...})             # Agent 洞见
SAVE("user:preference", "risk_tolerance", {"level": "high"}) # 用户偏好

# 禁止：无命名空间的杂乱存储
SAVE("", "随便一个key", data)  # 禁止
```

### 错误处理

```python
# ✅ 正确：存储失败优雅降级
try:
    await self.store.save(namespace, key, data)
except OSError as e:
    logger.error("[Memory] 存储失败, namespace=%s, key=%s: %s", namespace, key, e)
    # 不抛异常——记忆失败不影响主流程
except Exception as e:
    logger.exception("[Memory] 存储异常: %s", e)
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `store.py` | 320 | **500** | ✅ |
| `knowledge_base.py` | 318 | **500** | ✅ |
| `manager.py` | — | **500** | ✅ |
| `skill_disk.py` | 395 | **500** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ 写入 → 读取一致性（写什么读什么）
- ✅ 命名空间隔离（不同空间数据不干扰）
- ✅ 写入失败（模拟磁盘满/权限不足）
- ✅ 检索空结果（查询不存在的记忆）
- ✅ 知识库语义搜索 top_k 有效性
- ✅ 大量写入性能（1000 条写入 ≤ 2s）

### Mock 策略

```python
# 使用 tests/test_memory/conftest.py 中的 fixture
# kb_with_temp_dir 提供临时目录的 KnowledgeBase

def test_memory_persistence(kb_with_temp_dir):
    """验证写入后重启可读（模拟文件持久化）"""
    kb = kb_with_temp_dir
    await kb.save("test", "key1", {"value": 42})
    # 重新加载
    kb2 = KnowledgeBase(storage_dir=kb.storage_dir)
    result = await kb2.load("test", "key1")
    assert result["value"] == 42
```

### 覆盖率目标

- 存储层：≥90%
- 知识库检索：≥85%
- 记忆管理器：≥85%

---

## 性能标准

| 指标 | 目标 | 测量方法 |
|:-----|:----:|:---------|
| 单条写入 | ≤ 10ms | timeit |
| 单条读取 | ≤ 5ms | timeit |
| 语义检索 top-5 | ≤ 200ms | timeit |
| 批量写入 100 条 | ≤ 500ms | pytest-benchmark |
| 命名空间过滤 | ≤ 50ms | timeit |
| 磁盘占用 | ≤ 100MB（正常使用） | du -sh |

---

## 部门间契约

### 提供给辩论引擎部的 API

```python
# 辩论引擎部（M1 节点）调用记忆接口的约定格式
class MemoryQuery(BaseModel):
    namespace: str          # 查询命名空间
    query: str              # 语义查询字符串
    top_k: int = 5          # 返回结果数
    time_range: tuple | None = None  # 时间范围过滤（可选）

class MemoryResult(BaseModel):
    items: list[dict]       # 检索结果
    total: int              # 匹配总数
    query_time: float       # 查询耗时 ms
```

### 持久化保障

```python
# 写入必须确认落盘
await manager.save("debate", debate_id, data)
# 上面返回即确认已持久化

# 禁止"异步写入、不确认"的模式
asyncio.create_task(manager.save(...))  # 禁止：不确认落盘
```

---

## 审查清单

- [ ] 所有存储操作走抽象接口，不直接读写文件？
- [ ] 写入确认持久化后才返回？
- [ ] 命名空间隔离验证？
- [ ] 存储失败优雅降级（不影响主流程）？
- [ ] 检索性能 ≤ 200ms？
- [ ] 无上限记忆增长（有清理机制）？

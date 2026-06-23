---
department: 记忆系统部
codebase: src/memory/
last_updated: 2026-06-22
---

# 🧠 记忆系统部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| KnowledgeBase 知识库 | ✅ | n-gram TF 向量语义检索 |
| MemoryStore 存储抽象 | ✅ | MemoryStore(ABC) + JsonFileStore 实现 |
| MemoryManager 管理器 | ✅ | 命名空间语义化读写 |
| SkillDisk 插件盘 | ✅ | 7 位投资大师人格定义加载 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 记忆系统测试（test_memory_*） | 29 |
| 知识库 RAG 检索 | 已覆盖 |
| 存储持久化 | 已覆盖 |

### 关键架构决策

- **抽象存储接口**：MemoryStore 抽象基类，可替换实现（当前 JsonFileStore → 未来 SQLiteStore）
- **命名空间隔离**：不同领域数据（辩论历史/Agent 洞见/用户偏好）互不干扰
- **优雅降级**：存储失败不抛异常，日志记录后不影响主流程

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-051 | MemoryManager 无存储失败测试（磁盘满/只读/损坏 JSON） | 🟡 | 30min |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | TD-051 补 MemoryManager 存储失败测试（IOError/损坏 JSON/只读） | 无 |
| 2 🟢 | 定期清理过期记忆机制 | 无 |

### 设计哲学新任务（DP 系列）

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 预估 |
|:--:|:-----|:----:|
| **DP-006 关联** 🥈 | **反思记录存储** — MemoryStore 扩展命名空间 `reflection/` 用于存储 Agent 反思和镜子对比数据，每个 Agent 角色独立命名空间 | ~1h |

### 结果回调核心引擎（RC-001，2026-06-23 新增 — 记忆系统部牵头）

> **定位**：记忆系统部牵头 RC-001（回调核心引擎），因为其核心职责是回调状态持久化 + 事件分发。涉及 MemoryStore ("callback", *) 命名空间扩展。
> 完整方案见 [ROADMAP.md RC 轨道](../../00-overview/ROADMAP.md#rc-结果回调轨道2026-06-23-新增--规划阶段)。

| RC | 事项 | 预估 |
|:--:|:-----|:----:|
| **RC-001** 🥇 | **回调核心引擎** — `src/callback/` 模块：engine（ResultCallbackEngine 中央分发器）+ registry（注册表）+ storage（MemoryStore 持久化）+ models（事件模型）+ callbacks/（预置回调目录） | ~4h |

**架构概览**：

```
src/callback/
  __init__.py              # 公开 API
  engine.py                # ResultCallbackEngine — 中央事件分发器
  registry.py              # 回调注册表（注册/查找/优先级/冷却/自动禁用）
  storage.py               # 回调状态持久化 → ("callback", "config"/"records"/"risk_override")
  models.py                # CallbackEvent / CallbackConfig / CallbackRecord / CallbackEventType
  callbacks/
    __init__.py            # register_default_callbacks()
    m3_ext.py              # RC-002: 按板块信任度校准
    ub_track.py            # RC-003: 用户行为追踪
    rp_tune.py             # RC-004: 风险参数自适应
    calibrate.py           # RC-005: 置信度校准
    strat_route.py         # RC-006: 策略路由
```

**MemoryStore 新命名空间**：

| 命名空间 | 格式 | 用途 |
|:---------|:----:|:------|
| `("callback", "config")` | JSON | 每个回调的 CallbackConfig（key=回调名称）|
| `("callback", "records")` | JSONL | 执行记录流（审计/调试）|
| `("callback", "risk_override")` | JSON | 风险参数覆盖（key="current"）|
| `("callback", "strategy_stats")` | JSON | 策略路由统计（key="route_table"）|

### 用户经验反馈闭环（UI 系列，2026-06-23 新增 — 架构第9层）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 记忆系统部在闭环中负责：RC-001 核心引擎（回调事件分发器 + 注册表 + 存储层）。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-1a** 🥇 | **RC-001 回调核心引擎** — `src/callback/` 模块：engine（ResultCallbackEngine）+ registry + storage + models | 无 | ~4h |

### DP-006 反射存储接口

```python
# MemoryManager 新增
await memory.write(
    namespace="reflection/buffett",      # 每个 Agent 独立命名空间
    key=f"reflect_{date}_{stock_code}",
    data={
        "agent": "warren_buffett",
        "date": "2026-06-22",
        "situation": { ... },            # 当时的市场环境
        "prediction": "买入",
        "outcome": "+3.2%",
        "accuracy": True,
        "lesson": "..."                   # 供镜子展示
    }
)
```

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/memory/store.py` | 320 | MemoryStore(ABC) + JsonFileStore |
| `src/memory/knowledge_base.py` | 318 | n-gram TF 语义检索 |
| `src/memory/manager.py` | — | MemoryManager 语义化读写 |
| `src/memory/skill_disk.py` | 395 | 投资大师人格定义加载 |
| `docs/06-departments/04-memory-systems/ROLE.md` | — | 👤 记忆系统部角色定义 |
| `docs/06-departments/04-memory-systems/STANDARDS.md` | — | 📐 记忆系统部技术规范 |

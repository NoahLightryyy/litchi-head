---
department: 记忆系统部
codebase: src/memory/
last_updated: 2026-07-30 (K 线证据版本记忆职责确认)
---

# 🧠 记忆系统部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| KnowledgeBase 知识库 | ✅ | n-gram TF 向量语义检索 |
| MemoryStore 存储抽象 | 🟡 | 接口完成；JsonFileStore 仅适合 MVP，迁移门禁已建立 |
| MemoryManager 管理器 | ✅ | 命名空间语义化读写 |
| SkillDisk 插件盘 | ✅ | 7 位投资大师人格定义加载 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 记忆系统测试（test_memory_*） | 29 |
| 知识库 RAG 检索 | 已覆盖 |
| 存储持久化 | 已覆盖 |

### 关键架构决策

- **抽象存储接口**：MemoryStore 抽象基类可替换实现；当前 JsonFileStore →
  ADR-012 SQL 事实源（SQLite WAL / PostgreSQL 待门禁决定）
- **命名空间隔离**：不同领域数据（辩论历史/Agent 洞见/用户偏好）互不干扰
- **优雅降级**：存储失败不抛异常，日志记录后不影响主流程
- **ADR-012（方向已批准）**：SQL 保存不可丢事实，Redis 只保存可重建投影，
  Parquet 保存批量行情；当前尚未迁移
- **Batch B/C 恢复证据**：SQLite/PostgreSQL 已恢复同一份已提交代表性 session；
  68,896-byte 真实 LLM 结果已通过 SQLite 重开恢复；最小 LangGraph 图在关闭
  SQLite 连接后按 `thread_id` 续跑且已完成节点未重跑
- **2026-07-28 合成基线**：1,000 条约 4 KB 决策下，JSON Object 写入
  52.9 ops/s，SQLite WAL 约 19,448 ops/s；SQLite 主键查询 p95 约 0.014 ms

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-051 | MemoryManager 无存储失败测试（磁盘满/只读/损坏 JSON） | 🟡 | 30min |
| TD-066 | JSON/JSONL 无生命周期、事务与跨进程安全 | 🟡 | 2-3d |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟡 | 将 AsyncSqlite/Postgres checkpointer 接入正式辩论图并验证副作用幂等 | TD-069 决策 |
| 2 🟡 | TD-051 补 MemoryManager 存储失败测试（IOError/损坏 JSON/只读） | 无 |
| 3 🟡 | TD-066 SQL 迁移与备份恢复门禁 | 正式图恢复证据 |
| 4 🔥 | KR-6 保存辩论所用 RAW/因子/状态版本，历史召回不得跨版本冒充当前事实 | 2C 转换核心已保存双路版本；等待 TD-075/KR-3～4 后只保存经核验统一信封引用 |

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
| **RC-001** ✅ | **回调核心引擎** — `src/callback/` 模块：engine（ResultCallbackEngine 中央分发器）+ registry（注册表）+ storage（MemoryStore 持久化）+ models（事件模型）。预置业务回调目录留给 RC-002+ 分批接入 | 已完成 |

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

**2026-07-10 落地状态**：
- `src/callback/engine.py`：支持 `dispatch()` 中央分发、`register()` 注册、优先级排序、冷却跳过、失败隔离、错误计数、达到阈值自动禁用。
- `src/callback/models.py`：`CallbackEvent` 增加 `event_id`，便于审计串联同一次事件的多条回调记录。
- `tests/test_callback/test_engine.py`：5 个测试覆盖优先级、事件过滤、失败隔离、自动禁用、冷却跳过。
- 后续入口：RC-002/RC-003/RC-004 应只注册业务回调，不再重复实现事件分发机制。

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
| **UI-1a** ✅ | **RC-001 回调核心引擎** — `src/callback/` 模块：engine（ResultCallbackEngine）+ registry + storage + models | 无 | 已完成 |

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

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
记忆系统负责不可变 `DecisionSnapshot`、实验版本和到期结果事件。学习回写只能追加新记录，
不得覆盖原决策、原证据或原 baseline；进程重启和跨进程并发下仍须保持唯一性与可恢复性。

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/memory/store.py` | 320 | MemoryStore(ABC) + JsonFileStore |
| `src/memory/knowledge_base.py` | 318 | n-gram TF 语义检索 |
| `src/memory/manager.py` | — | MemoryManager 语义化读写 |
| `src/memory/skill_disk.py` | 395 | 投资大师人格定义加载 |
| `docs/06-departments/04-memory-systems/ROLE.md` | — | 👤 记忆系统部角色定义 |
| `docs/06-departments/04-memory-systems/STANDARDS.md` | — | 📐 记忆系统部技术规范 |

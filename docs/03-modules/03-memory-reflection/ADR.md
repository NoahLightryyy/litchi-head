# 记忆与反思模块 — 架构决策

## ADR-006: 三层记忆架构

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-03 |
| **状态** | ↩️ 已被 ADR-011 继承细化 |
| **影响范围** | `src/memory/` |

**上下文**：
Agent 需要记忆来保证决策一致性，但 MVP 阶段不应过度工程化。

**决策**：
三层设计 + JSON 文件持久化起步：工作记忆 → 情景记忆 → 反思机制。

---

## ADR-011: 命名空间记忆存储系统

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-11 |
| **状态** | ✅ 已采纳 |
| **影响范围** | `src/memory/`, 所有消费记忆的 Agent |

**上下文**：
ADR-006 在 6 月 3 日定义了"三层记忆"方向，但 8 天来未落地实现。
本 ADR 将 ADR-006 的原则细化为可执行的存储层设计。

**决策**：
采用**命名空间 + 可插拔存储层**架构：

```
MemoryStore 接口 → JsonFileStore（MVP）/ SqliteStore（未来）
namespace = ("memory_type", "agent_role", "user_id")
```

**命名空间设计**：
```
("episodic",  "buffett",  "user_001")  # 情景记忆
("working",   "master",   "user_001")  # 工作记忆
("reflective","mirror",   "user_001")  # 反思
("semantic",  "global",   "user_001")  # 全局画像
```

**与 ADR-006 的继承关系**：
| ADR-006 概念 | ADR-011 映射 |
|:------------|:-------------|
| 工作记忆 | namespace `("working", role, user)` + in-memory |
| 情景记忆 | namespace `("episodic", role, user)` + append-only JSON |
| 反思机制 | namespace `("reflective", role, user)` |
| —（新增） | namespace `("semantic", "global", user)` 用户画像 |

**后果**：
- ✅ 存储层与业务逻辑解耦，升级不影响 Agent 代码
- ✅ 新增记忆类型只需新增 namespace 前缀
- ⚠️ JSON 读写在大规模数据下可能成为瓶颈（几千条级别）

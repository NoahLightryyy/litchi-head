# ADR-008: Agent 数据契约与通信协议规范

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-07 |
| **状态** | ✅ 已采纳 |
| **影响范围** | `src/agents/`, `src/core/`, `src/utils/`, 所有 Agent 实现 |

**上下文**：
现有 `AgentResult.data: dict` 和 `AgentMessage.payload: dict` 是"任意 JSON"类型，导致：
1. ❌ 无法静态校验 — 下游不知 data 里有什么字段
2. ❌ 无法建表 — 每个 Agent 结构不同，无法展开为列
3. ❌ 接口腐化 — 新增 Agent 无契约约束
4. ❌ 序列化陷阱 — `datetime` 不被 `json.dumps` 支持

**决策**：
全栈采用 Pydantic 契约驱动：

1. 每个 Agent 定义自己的 I/O 模型（强制）
2. AgentResult 泛型化 `AgentResult[T]`
3. 编排器 State 使用 Pydantic BaseModel
4. AgentMessage 序列化就绪（`to_db_record()`）
5. SessionRecord 辩论快照

详见 [`src/agents/base.py`](../../src/agents/base.py) 实际落地代码。

**舍弃方案**：
| 方案 | 舍弃理由 |
|------|---------|
| 继续用 `data: dict` | 利息已到上限，Phase 0 不处理 Phase 1 就来不及 |
| Protobuf / Avro | 太重，Pydantic 足够且与 LangChain 生态集成 |
| 数据库先 JSON 再拆 | 后面拆数据成本极高 |

**后果**：
- ✅ 新 Agent 开发者一眼知道要输出什么字段
- ✅ 未来 DB 迁移：Pydantic 模型 → SQLAlchemy 映射自然
- ⚠️ 每个 Agent 多写 ~15 行模型定义
- ✅ 直接修复 TD-002（AgentResult 泛型化）

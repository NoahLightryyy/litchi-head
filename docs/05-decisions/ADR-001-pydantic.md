# ADR-001: Pydantic 作为全栈数据校验层

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-03 |
| **状态** | ✅ 已采纳 |
| **影响范围** | 全项目 |

**上下文**：
多 Agent 系统需要跨模块传递大量结构化数据，需要统一的序列化/校验方案。
同时，LLM 的结构化输出（`with_structured_output`）原生支持 Pydantic 模型。

**决策**：
所有模块间的数据传输统一使用 Pydantic `BaseModel`：
- 通信协议 `AgentMessage` — Pydantic
- Agent 输入/输出 — Pydantic
- 配置管理 — Pydantic Settings

**理由**：
1. 与 LLM `with_structured_output()` 天然对接
2. 零成本序列化/反序列化（`.model_dump()` / `.model_validate()`）
3. JSON Schema 导出能力方便调试和文档生成
4. Python 3.12 标准依赖，无额外引入

**舍弃方案**：
| 方案 | 舍弃理由 |
|------|---------|
| `dataclasses` 纯数据类 | 缺少校验和序列化能力 |
| `msgspec` | 性能更好但生态不如 Pydantic 与 LangChain 集成深 |
| Apache Avro / Protobuf | 太重，不适合 MVP 阶段 |

**后果**：
- ✅ 统一的数据契约层，减少模块间的沟通成本
- ✅ 调试友好（JSON Schema 可直接可视化）
- ⚠️ 性能不如 msgspec（但 MVP 阶段无感知）

# 🏛️ 架构决策记录（ADR）

> 跨模块的架构决策。模块专属的 ADR 在各模块的 `ADR.md` 中。

## 索引

| ID | 决策 | 归属 | 状态 |
|----|------|------|------|
| ADR-001 | Pydantic 全栈数据契约 | 跨模块 | ✅ 已采纳 |
| ADR-004 | Streamlit MVP 前端 | frontend | ✅ 已采纳 |
| ADR-007 | DeepSeek 主力 LLM | utils | ✅ 已采纳 |
| ADR-008 | Agent 数据契约与通信协议 | agents/core | ✅ 已采纳 |
| ADR-010 | Agent 运行时增强（LLMConfig/streaming/辩论上下文） | utils/agents | ✅ 已采纳 |

## 模块专属 ADR

| 模块 | 文件 |
|------|------|
| 01-data-collection | [`03-modules/01-data-collection/ADR.md`](../03-modules/01-data-collection/ADR.md) |
| 02-debate-engine | [`03-modules/02-debate-engine/ADR.md`](../03-modules/02-debate-engine/ADR.md) |
| 03-memory-reflection | [`03-modules/03-memory-reflection/ADR.md`](../03-modules/03-memory-reflection/ADR.md) |
| 04-agent-orchestration | [`03-modules/04-agent-orchestration/ADR.md`](../03-modules/04-agent-orchestration/ADR.md) |

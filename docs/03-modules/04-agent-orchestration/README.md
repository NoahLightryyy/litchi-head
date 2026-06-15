# 🤖 Agent 编排模块

> 多 Agent 的执行流程编排、并行/串行调度、状态管理、上下文传递。

## 当前状态

- ✅ LangGraph StateGraph 基础搭建
- ✅ BaseAgent + MasterAgent 通用实现
- ✅ AgentContext 辩论槽位就绪
- ✅ LangGraph 最小原型验证（20 测试）
- ⬜ 并行写入冲突解决
- ⬜ 条件路由（数据为空时短路）

## 文档

| 文件 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 模块规格（职责边界、代码结构、数据模型） |
| [RESEARCH.md](RESEARCH.md) | 调研分析（战线格局、竞品对比、研究问题） |
| [ADR.md](ADR.md) | 架构决策（ADR-002 LangGraph + ADR-009 MCP 工具扩展） |

## 对应源码

- `src/debate/orchestrator.py` — LangGraph StateGraph 全流程编排
- `src/agents/base.py` — Agent 基类
- `src/agents/master_agent.py` — MasterAgent 通用实现

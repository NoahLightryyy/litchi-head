# 功能模块：Agent 编排

> 多 Agent 的执行流程编排、并行/串行调度、状态管理、上下文传递。

## 模块定义

多 Agent 的执行流程编排、并行/串行调度、状态管理、上下文传递。

**职责边界**：
- ✅ Agent 的有序调度（并行/串行/条件路由）
- ✅ 全局状态的管理与传递
- ✅ 断点续跑 / Checkpoint
- ✅ Agent 注册与动态扩展
- ❌ 不负责单个 Agent 的具体行为逻辑
- ❌ 不负责 Agent 之间辩论的具体内容

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/debate/orchestrator.py` | LangGraph StateGraph 编排全流程 |
| `src/agents/base.py` | Agent 基类（AgentContext + AgentResult + BaseAgent.run_safe） |
| `src/agents/master_agent.py` | MasterAgent 通用实现（注资分析结构化输出） |
| `src/agents/xiao_zhi.py` | 小智 Agent（简单对话 Agent） |

关联决策：[ADR.md](ADR.md) — ADR-002（LangGraph 框架）、ADR-009（MCP 工具扩展）

## 架构（当前状态）

当前编排为 **单线顺序**（D→D→A），简单稳定但尚未利用并行能力：

```
collect_data ──→ master_round ──→ aggregate ──→ END
                    │
              顺序调大师（避开了并行写入冲突）
```

特点：每个 Agent 不共享完整上下文，仅通过 `StateGraph` 传递结构化数据。

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| LangGraph StateGraph 基础搭建 | ✅ 完成 | 8（orchestrator 单元） |
| BaseAgent + MasterAgent 通用实现 | ✅ 完成 | 含 MasterAgent 174 测试 |
| AgentContext 辩论槽位 | ✅ 就绪 | 含 debate 全链路 451 测试 |
| LangGraph 最小原型验证 | ✅ 完成 | 20 原型测试 |
| 并行写入冲突解决 | ⬜ 待解决 | — |
| 条件路由（数据为空时短路） | ⬜ 待解决 | — |

## 下一步

- **并行写入冲突**：研究每个 Agent 写独立 state 字段的方案，替代当前顺序调用
- **条件路由**：当数据为空时自动跳过相关 Agent，不走空分析
- **Agent 注册表**：为 Phase 2 的 Skill/人格市场做准备，实现加 Agent 不改 Graph 定义

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景

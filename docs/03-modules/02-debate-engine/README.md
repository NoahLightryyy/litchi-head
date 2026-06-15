# ⚡ 辩论决策引擎

> 核心模块。多 Agent 辩论 + 评审 + 加权决策的核心流程。

## 当前状态

**Phase 1 MVP 已上线** — 核心链路全通：

| 功能 | 状态 | 测试 |
|:-----|:-----|:----:|
| 四组大师分析 | ✅ D1 | 360 tests |
| 交叉审阅+反驳 | ✅ D1 | 360 tests |
| 独立评审 | ✅ D3 | 383 tests |
| 历史决策注入 | ✅ M1 | 405 tests |
| 强制输出方向 | ✅ D2 | 436 tests |
| VoteSummary 扩展 | ✅ D4 | 451 tests |
| 反思闭环 | 📋 TD-017 已确认 | — |

## 文档

| 文件 | 说明 |
|:-----|:-----|
| [SPEC.md](SPEC.md) | 规格说明书（战线格局 + 架构对照 + 实施轨迹） |
| [ADR.md](ADR.md) | 架构决策（ADR-005 四组辩论架构） |

## 对应源码

- `src/debate/orchestrator.py` — LangGraph StateGraph 编排
- `src/debate/models.py` — 辩论数据模型
- `src/agents/master_agent.py` — 通用 MasterAgent

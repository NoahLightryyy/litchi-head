# 🔧 功能模块

> 每个模块一个文件夹，包含规格（SPEC）、架构（ARCHITECTURE）、决策（ADR）、待办（TODO）。
> 开发一个功能只需看对应模块的文件夹。

## 模块索引

| # | 模块 | 源码 | 目录 |
|:-:|:-----|:-----|:-----|
| 01 | 数据采集 | `src/data/` | [01-data-collection/](01-data-collection/) |
| 02 | 辩论决策引擎 ★ | `src/debate/` | [02-debate-engine/](02-debate-engine/) |
| 03 | 记忆与反思 | `src/memory/` | [03-memory-reflection/](03-memory-reflection/) |
| 04 | Agent 编排 | `src/agents/` | [04-agent-orchestration/](04-agent-orchestration/) |
| 05 | 风控管理 | `src/risk/` | [05-risk-management/](05-risk-management/) |
| 06 | 交易执行 | `src/execution/` | [06-trade-execution/](06-trade-execution/) |
| 07 | 因子研究 | `src/research/` | [07-factor-research/](07-factor-research/) |
| 08 | 回测仿真 | `src/backtest/` | [08-backtest-simulation/](08-backtest-simulation/) |
| 09 | Agent 人格与提示词 | — | [09-agent-persona/](09-agent-persona/) |

## 每个模块的结构

```
02-debate-engine/
├── README.md        ← 总览 + 当前状态 + 测试覆盖率
├── SPEC.md          ← 规格/调研/竞品对照（原调研分析内容）
├── ARCHITECTURE.md  ← 架构方案（可选，复杂模块有）
├── ADR.md           ← 本模块的架构决策
└── TODO.md          ← 待办 + 债务（可选，用模块文件记录）
```

## 依赖关系

```
01-data-collection  ──────────┐
                              ├──→ 02-debate-engine ──→ ...
04-agent-orchestration  ─────┘
                              │
03-memory-reflection  ────────┘
                              │
05/06/07/08/09 (预留模块) ────┘
```

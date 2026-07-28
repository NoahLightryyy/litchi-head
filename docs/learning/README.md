# 🎓 litchi-head 学习资料

> 这里不是文档，是 **技术知识卡片**。
> 每张卡片讲透一个概念，关联到项目里的真实代码。

---

## 为什么有这个文件夹

你说得对——项目结束再总结，东西太大太杂，根本看不进去。

所以改成**边做边写**：每次工作时，写了什么技术相关的东西，就对应写一份学习卡片丢进来。你做完一个功能，就能读到对应的知识讲解。

---

## 怎么用

1. **按顺序读** —— 编号从小到大是建议的学习顺序
2. **边读边打开项目代码** —— 每张卡片都标注了对应文件路径，打开看看
3. **每张卡片末尾有一个「自己试试」** —— 花 5 分钟做一下，比读十遍管用
4. **想写新卡片？** —— 复制 `TEMPLATE.md` 开始，保持格式统一
4. **不用一次读完** —— 每次做新功能前，读相关的 1-2 张卡片就行

---

## 卡片索引

### 基础篇（建议先读）

| # | 卡片 | 项目里的对应 |
|:-:|:-----|:-------------|
| 01 | [Pydantic BaseModel 与模块契约](01-pydantic-basemodel.md) | `src/core/protocol.py` |
| 02 | [LangGraph StateGraph 编排](02-langgraph-stategraph.md) | `src/agents/master_agent.py` |
| 03 | [LLM 统一封装层](03-llm-unified-layer.md) | `src/utils/llm.py` |
| 04 | [FastAPI 桥接层架构](04-fastapi-bridge.md) | `backend/` 目录 |
| 05 | [Provider 抽象模式（数据源）](05-provider-pattern.md) | `src/data/collector.py` |
| 06 | [纯 Python 技术指标计算](06-technical-indicators.md) | `backend/indicators.py` |
| 07 | [React 防抖与轮询模式](07-react-query-patterns.md) | `frontend/lib/hooks/` |

### 进阶篇

| # | 卡片 | 项目里的对应 |
|:-:|:-----|:-------------|
| 08 | [类型注解与 Pyright](08-type-hints-pyright.md) | 全项目 |

| 15 | [Hookify 规则与 Claude Code Hooks](15-hookify-rules.md) | `.claude/hookify.*.local.md` |
| 16 | [系统性代码按察 — Silent Failure 审计方法论](16-code-quality-audit.md) | 全代码库 `except` 块审计 |
| 17 | [测试架构与模块自治](17-testing-architecture.md) | `tests/` 目录 + `TESTING_STRATEGY.md` |
| 18 | [FastAPI 路由测试 — TestClient + MockCollector](18-fastapi-testclient-mockcollector.md) | `tests/test_backend/conftest.py` + 4 路由测试 |

| 19 | [Windows 开发环境调试指南 — Git Bash 5 大兼容坑](19-windows-git-bash-compat.md) | `.claude/skills/resume-session/skill.md` + `docs/01-guides/triage/git-bash-compat.md` |
| 20 | 🆕 [三层测试策略 — pytest marker 实现快慢分离](20-three-tier-test-strategy.md) | `scripts/pre-push` + `pyproject.toml` + `docs/01-guides/ci/` |
| 21 | 🆕 [工程纪律 — 工具不是纪律的替代品](21-engineering-discipline.md) | `scripts/check.py` 创建与反省 |
| 22 | 🆕 [辩论偏斜度计算 — BiasReport](22-debate-bias-report.md) | `src/debate/orchestrator.py` → `compute_bias_report()` |
| 23 | 🆕 [结果回调引擎 — 让结果自动触发系统学习](23-result-callback-engine.md) | `src/callback/engine.py` |
| 24 | 🆕 [按场景校准信任度 — Contextual Trust](24-contextual-trust-calibration.md) | `src/debate/trust.py` + `src/callback/callbacks/m3_ext.py` + `src/debate/orchestrator.py` |
| 25 | 🆕 [财务指标数据模型 — DataSource 协议扩展模式](25-financial-indicator-model.md) | `src/data/models.py` → `FinancialMetrics` + `src/data/providers/akshare.py` |
| 26 | 🆕 [估值比率模型 — ValuationMetrics PE/PB/PS](26-valuation-metrics-model.md) | `src/data/models.py` → `ValuationMetrics` + `src/data/collector.py` |
| 27 | 🆕 [PD 动态指标体系 — 行业感知的关键指标选择](27-pd-dynamic-indicators.md) | `src/data/indicators/registry.py` + `src/data/indicators/selector.py` |
| 28 | 🆕 [结构化多层市场简报 — 让 LLM "看什么股说什么话"](28-structured-market-brief.md) | `src/data/collector.py` + `src/debate/orchestrator.py` |
| 29 | 🆕 [SQL 事实源与 Redis 可重建投影](29-sql-redis-storage-layers.md) | `scripts/storage_baseline.py` + ADR-012 |
| 30 | 🆕 [可恢复 Session 信封](30-durable-session-envelope.md) | `src/debate/session_store.py` + `scripts/debate_recovery_gate.py` |
| 31 | 🆕 [LangGraph 持久检查点：让节点完成后可以断电续跑](31-langgraph-durable-checkpoint.md) | `scripts/langgraph_checkpoint_gate.py` |

> **卡片持续增加中** —— 每次开发新功能，新的学习卡片就会出现在这里。

---

## 阅读建议

| 你的目标 | 建议读哪些 |
|:---------|:-----------|
| 快速上手项目 | 01 → 02 → 03 → 04 → 05 |
| 理解后端设计 | 01 → 03 → 04 → 05 → 08 → **29** → **30** → **31** |
| 理解 Agent 系统 | 02 → 03 → 22 → 24 → **31** |
| 理解前端设计 | 04 → 07 → 28 |
| 理解质量保障 | 15 → 16 → 17 → 文档 `docs/03-modules/12-quality-assurance/` |
| 编写后端测试 | 17 → 18 |
| Windows 开发调试 | **19** → `docs/01-guides/triage/git-bash-compat.md` |
| 测试优化与 CI 流程 | 17 → **20** → `docs/01-guides/ci/` |
| 准备面试 | 全部通读一遍，重点练「自己试试」 |

---
department: 跨部门
last_updated: 2026-07-23
---

# 🔄 跨部门状态总览

> 本文件记录跨部门/全代码库的公共状态。
> 各部门的专有状态见各自 `docs/06-departments/{id}/HANDOVER.md`。

---

## 项目身份

| 字段 | 值 |
|------|-----|
| 项目名称 | litchi-head — 多智能体投资决策平台 |
| 当前阶段 | Phase 1 MVP + Phase R 实盘加固 |
| 技术栈 | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / FastAPI / Next.js 16 |
| 远程仓库 | GitHub (origin) + Gitee (gitee 备份) |
| CI | Ruff + Pyright + Pytest on 3.12/3.13 |

## 全代码库健康

| 指标 | 当前值 |
|:-----|:------:|
| 全量测试 | 943 collected, 全部通过 ✅ |
| Pyright (src/) | 0 errors ✅ |
| Pyright (backend/) | 0 errors ✅ |
| Ruff | All checks passed ✅ |
| 技术债务开放 | 25 条 |
| 紧急指数 | ~4.5/10 |

## 跨部门协作现状

| 协作点 | 状态 | 说明 |
|:-------|:----:|:------|
| 数据契约（data 模型→全部门） | ✅ | 已建立契约测试 |
| API 契约（backend→frontend） | ✅ | 17 端点全量路由测试 |
| Agent 接口（agents→debate） | ✅ | MasterAgent 通用化 |
| 辩论↔风控接口 | ✅ | RiskAssessment 协议 |
| 辩论↔交易接口 | ✅ | TradePlan 协议 |
| 记忆↔辩论接口 | ✅ | MemoryManager 语义化 |
| 回测↔交易接口 | ✅ | TradeRecord 协议 |
| LLM 调用（全部门→infra） | ✅ | 单 Provider 策略（DeepSeek 唯一），接口保留供扩展 |

## 当前未完成事项（跨部门）

| 优先级 | 事项 | 涉及部门 |
|:------:|:-----|:---------|
| 🥇 | **FD-001 基本面数据接入** — ✅ 模型+Provider+辩论注入+分析师增强（数据+辩论完成），⬜ 前端财务 Tab（前端部） | 数据管道部 ✅ + 辩论引擎部 ✅ + 后端 API 部 + 前端部 ⬜ |
| 🥇 | **FD-002 产业链修复** — 真实行业分类替换伪产业链数据 | 后端 API 部 + 前端部 |
| 🥇 | **RC-003 UB-TRACK 用户行为追踪** — InvestmentDecision 模型 + UserBehaviorStore + 操作理由记录 | 后端 API 部 + 前端部 + 数据管道部 |
| 🥈 | **RC-004 RP-TUNE 风险参数自适应** — 回测结果 → 自动调止损/仓位 | 风控管理部 + 回测研究部 |
| 🥈 | **FD-003 供应链图谱（调研评估）** — 年报 PDF 解析前5大客户/供应商可行性 | 数据管道部 |
| 🥈 | **RC-005 CALIBRATE 置信度校准** — Brier score 过高时动态校准 | 辩论引擎部 |
| 🥉 | **RC-006 STRAT-ROUTE 策略路由** — 按市场条件追踪大师胜率并自动降级 | 辩论引擎部 |
| 🥉 | **UI-4a DP-006 镜子 Agent** — BehaviorComparisonReport，决策前历史对比提示，三段式解锁 | AI Agent 架构部 + 辩论引擎部 + 前端部 |
| 🟡 | **TD-041 数据新鲜度标注** — 前端展示数据时效 | 数据管道部 + 前端部 |
| 🟡 | **TD-059 性能基线** — 首次全链路性能测量 | 所有部门 |

> RC 系列 = Result Callback（结果回调引擎），基于 2026-06-23 架构审视。
> RC-001/RC-002 已完成：反思入口收到实际结果后可通过 M3-EXT 写入 TrustTracker。下一步是用户行为、风控参数和复盘看板闭环。
> 完整方案见 [docs/00-overview/ROADMAP.md](../../00-overview/ROADMAP.md) RC 轨道。

> **UI 用户经验反馈闭环** — 架构图第 9 层的完整实施计划，把 RC 公式层 + DP-006 镜子层 + R4 RetroBoard 合为一条完整闭环。
> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。

> FD 系列 = Financial Depth（基本面深度），基于 2026-06-23 机构级基本面分析调研结论。
> 完整调研报告见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

> 各部门的详细债务清单和下一步优先级见各自部门的 `DEBT.md` + `HANDOVER.md`。

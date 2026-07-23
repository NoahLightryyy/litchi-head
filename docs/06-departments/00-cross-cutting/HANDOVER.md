---
department: 跨部门
last_updated: 2026-07-23 (FD 编号对齐)
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
| 全量测试 | 1029 collected, 全部通过 ✅ |
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
| 🥇 | **PD 动态指标体系** — 新增 PD 系列任务：行业→动态选 5-10 指标，产业链位置判断，三维分析（财务+位置+供应链）。详见下方 PD 段落 | 数据管道部 + 辩论引擎部 + 后端 API 部 + 前端部 |
| 🥇 | **FD-001 基本面数据接入** — ✅ 模型+Provider+多源财务+辩论注入+分析师增强（数据+辩论完成），⬜ 前端财务 Tab（前端部） | 数据管道部 ✅ + 辩论引擎部 ✅ + 后端 API 部 + 前端部 ⬜ |
| 🥇 | **FD-002 估值比率模型** — ✅ PE/PB/PS 模型 + DataCollector.get_valuation()（纯计算，无需新 Provider） | 数据管道部 ✅ |
| 🥇 | **FD-003 产业链修复** — 真实行业分类替换伪产业链数据 | 后端 API 部 + 前端部 |
| 🥇 | **RC-003 UB-TRACK 用户行为追踪** — InvestmentDecision 模型 + UserBehaviorStore + 操作理由记录 | 后端 API 部 + 前端部 + 数据管道部 |
| 🥈 | **RC-004 RP-TUNE 风险参数自适应** — 回测结果 → 自动调止损/仓位 | 风控管理部 + 回测研究部 |
| 🥈 | **FD-004 供应链图谱（调研评估）** — 年报 PDF 解析前5大客户/供应商可行性 | 数据管道部 |
| 🥈 | **RC-005 CALIBRATE 置信度校准** — Brier score 过高时动态校准 | 辩论引擎部 |
| 🥉 | **RC-006 STRAT-ROUTE 策略路由** — 按市场条件追踪大师胜率并自动降级 | 辩论引擎部 |
| 🟡 | **TD-041 数据新鲜度标注** — 前端展示数据时效 | 数据管道部 + 前端部 |
| 🟡 | **TD-059 性能基线** — 首次全链路性能测量 | 所有部门 |

### PD 系列 — 产品定位动态指标（2026-07-23 新增）

> **一句话**：不和 Wind 比 6000 个指标。按行业+产业链位置动态选 5-10 个最关键的指标，AI 按行业上下文推理。
> **战略定位**：详见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md) — "散户 AI 决策副驾驶，告诉什么价买、什么价卖"。
>
> **三阶段路线**：
> 1. **基建期** — IndicatorRegistry 注册表 + 产业链位置判断 + 动态采集引擎（数据管道部）
> 2. **推理适配期** — AI 分析师生效行业上下文 + 大师按行业选指标（辩论引擎部）
> 3. **展示期** — 前端产业链位置标签 + 关键指标卡片 + 行业对比（后端 API + 前端）

| PD | 事项 | 牵头部门 | 状态 |
|:--:|:-----|:---------|:----:|
| **PD-001** | IndicatorRegistry 模型 + 注册表 | 🗄️ 数据管道部 | ⬜ |
| **PD-002** | 产业链位置判断（主营构成→上游/中游/下游） | 🗄️ 数据管道部 | ⬜ |
| **PD-003** | 动态采集引擎（按行业只取部分字段） | 🗄️ 数据管道部 | ⬜ |
| **PD-004** | 行业指标覆盖扩展（10+行业） | 🗄️ 数据管道部 | ⬜ |
| **PD-005** | 三维分析上下文注入（collect_data_node） | 🎯 辩论引擎部 | ⬜ |
| **PD-006** | 大师推理适配（大师按行业选关注指标） | 🎯 辩论引擎部 | ⬜ |
| **PD-007** | 指标解释人性化（每个指标一句话解读） | 🎯 辩论引擎部 | ⬜ |
| **PD-008** | 行业定位端点 API | 🌐 后端 API 部 | ⬜ |
| **PD-009** | 动态指标端点 API | 🌐 后端 API 部 | ⬜ |
| **PD-010** | FD-003a 伪产业链修复 | 🌐 后端 API 部 | ⬜ |
| **PD-011** | 产业链位置标签（前端） | 🎨 前端部 | ⬜ |
| **PD-012** | 关键指标卡片（前端） | 🎨 前端部 | ⬜ |
| **PD-013** | 指标解读气泡（前端） | 🎨 前端部 | ⬜ |
| **PD-014** | 行业对比模块（前端） | 🎨 前端部 | ⬜ |

> **PD 系列不取代现有 FD/RC/UI 系列**。PD 是"用什么指标分析方法"，FD 是"从哪里拿数据"，两者互补。

> RC 系列 = Result Callback（结果回调引擎），基于 2026-06-23 架构审视。
> RC-001/RC-002 已完成：反思入口收到实际结果后可通过 M3-EXT 写入 TrustTracker。下一步是用户行为、风控参数和复盘看板闭环。
> 完整方案见 [docs/00-overview/ROADMAP.md](../../00-overview/ROADMAP.md) RC 轨道。

> **UI 用户经验反馈闭环** — 架构图第 9 层的完整实施计划，把 RC 公式层 + DP-006 镜子层 + R4 RetroBoard 合为一条完整闭环。
> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。

> FD 系列 = Financial Depth（基本面深度），基于 2026-06-23 机构级基本面分析调研结论。
> 完整调研报告见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

> PD 系列 = Product Positioning（产品定位动态指标），基于 2026-07-23 产品定位战略定论。
> 完整战略文档见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md)。

> 各部门的详细债务清单和下一步优先级见各自部门的 `DEBT.md` + `HANDOVER.md`。

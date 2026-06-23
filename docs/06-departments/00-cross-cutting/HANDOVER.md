---
department: 跨部门
last_updated: 2026-06-22
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
| 🥇 | **FD-001 基本面数据接入** — 财务指标模型 + Provider 扩展 + 辩论注入 + 前端展示 | 数据管道部 + 辩论引擎部 + 后端 API 部 + 前端部 |
| 🥇 | **FD-002 产业链修复** — 真实行业分类替换伪产业链数据 | 后端 API 部 + 前端部 |
| 🥈 | **FD-003 供应链图谱（调研评估）** — 年报 PDF 解析前5大客户/供应商可行性 | 数据管道部 |
| 🟡 | **TD-041 数据新鲜度标注** — 前端展示数据时效 | 数据管道部 + 前端部 |
| 🟡 | **TD-059 性能基线** — 首次全链路性能测量 | 所有部门 |

> FD 系列 = Financial Depth（基本面深度），基于 2026-06-23 机构级基本面分析调研结论。
> 完整调研报告见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

> 各部门的详细债务清单和下一步优先级见各自部门的 `DEBT.md` + `HANDOVER.md`。

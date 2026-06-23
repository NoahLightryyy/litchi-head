# 🏠 litchi-head 项目概览

> 个人多智能体投资决策助手 — 虚拟小投行设计哲学见 [DESIGN_PHILOSOPHY.md](DESIGN_PHILOSOPHY.md)

## 一句话

**litchi-head** 是一个基于 LangGraph 编排的多 Agent 投资决策平台，让多位"大师"（不同投资风格的 AI Agent）对同一标的进行分析辩论，由独立评审综合裁决输出投资建议。

## 模块鸟瞰

```
┌──────────────────────────────────────────────────────────┐
│                   用户交互层                               │
│         React (Next.js 16) 前端 ← FastAPI 桥接层          │
│  三页路由：宏观总览 → 产业链分析 → 个股决策（4 Tab 面板）    │
├──────────────────────────────────────────────────────────┤
│                   辩论决策层 ★核心                          │
│  大师分析 → 交叉审阅 → 独立评审 → 加权汇总 → 历史注入      │
├───────────────────┬──────────────────┬──────────────────┤
│  记忆与反思 🧠    │  Agent 编排 🤖   │   数据采集 ⛁    │
│  MemoryStore      │  LangGraph       │  akshare / adata │
│  命名空间存储      │  StateGraph      │  Provider 抽象   │
├───────────────────┴──────────────────┴──────────────────┤
│                  预留模块（Phase 2+）                      │
│  风控管理 🛡️ · 交易执行 💹 · 因子研究 🔬 · 回测仿真 🧪    │
├──────────────────────────────────────────────────────────┤
│                   基础设施                                 │
│  DeepSeek LLM · Pydantic 数据契约 · CI/CD (GitHub Actions)│
└──────────────────────────────────────────────────────────┘
```

## 当前阶段

**Phase 1 MVP** — 核心链路全通，前端三页路由 + 完整 Tab 面板已上线。
- data → debate → decision 链路已接驳
- Provider 抽象层（akshare/adata/zzshare 三源，故障自动切换）
- FastAPI 桥接层（17 个 API 端点）
- React 前端（3 页面 + 4 Tab + K 线真渲染 + 搜索 autocomplete）
- 全项目零造假数据 ✅

## 快速入口

| 如果你 | 从这里开始 |
|:-------|:-----------|
| 想理解设计理念 | 🏛️ **`docs/00-overview/DESIGN_PHILOSOPHY.md`** — 虚拟小投行 + 反馈机制 + 差异化 |
| 新开发者 | `docs/01-guides/` 流程规范 + `docs/02-requirements/` 产品需求 |
| 想知道项目怎么组织 | 🏢 **`docs/06-departments/README.md`** — 10 部门体系总览 |
| AI Agent (resume-session) | `docs/01-guides/WORKFLOW.md` + `HANDOVER.md` |
| 修数据模块 | `docs/06-departments/01-data/ROLE.md` |
| 改辩论功能 | `docs/06-departments/02-debate-engine/ROLE.md` |
| 改后端 API | `docs/06-departments/08-backend-api/ROLE.md` |
| 改前端 | `docs/06-departments/09-frontend/ROLE.md` |
| 想了解模块细节 | `docs/03-modules/` 各模块文件夹 |

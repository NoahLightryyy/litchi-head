# 📚 litchi-head 文档路由

> 按「受众 × 生命周期」组织：新人、开发者、AI Agent 各有一条入口。

---

## 🏠 先读这里（所有人都从这里开始）

| 文档 | 说明 |
|:-----|:------|
| [00-overview/OVERVIEW.md](00-overview/OVERVIEW.md) | 项目一句话定位 + 模块鸟瞰 |
| [00-overview/GLOSSARY.md](00-overview/GLOSSARY.md) | 术语表 |
| [00-overview/TECH_STACK.md](00-overview/TECH_STACK.md) | 技术栈 + 选型理由 |

## 🤖 AI Agent 入口（resume-session 加载目标）

| 文档 | 说明 |
|:-----|:------|
| [01-guides/WORKFLOW.md](01-guides/WORKFLOW.md) | AI 自动化工作流程 |
| [01-guides/HANDOVER.md](01-guides/HANDOVER.md) | AI 会话交接文档 |
| [01-guides/ROUTING.md](01-guides/ROUTING.md) | ★ 上下文加载策略（TODO） |
| [01-guides/ENVIRONMENT.md](01-guides/ENVIRONMENT.md) | 环境配置指南 |
| [01-guides/debt/ROUTER.md](01-guides/debt/ROUTER.md) | 技术债务路由索引 |

## 👨‍💻 开发者入口

| 文档 | 说明 |
|:-----|:------|
| [02-requirements/](02-requirements/) | 产品需求 |
| [03-modules/](03-modules/) | **★ 核心：每个功能一个文件夹** |
| [03-modules/02-debate-engine/](03-modules/02-debate-engine/) | 辩论引擎（当前 MVP 核心） |
| [05-decisions/](05-decisions/) | 跨模块架构决策记录（ADR） |

## 📋 变更记录

| 文档 | 说明 |
|:-----|:------|
| [04-changelog/logs/](04-changelog/logs/) | AI 工作日志（按日归档） |

## 🗄️ 归档

| 文档 | 说明 |
|:-----|:------|
| [99-archive/](99-archive/) | 历史调研、旧方案、外部工具文件 |

---

## 目录结构

```
docs/
├── README.md                ← 本文：全文档路由
├── 00-overview/             ← 🏠 项目总览（不随时间膨胀）
├── 01-guides/               ← 📐 流程规范 / AI 路由 / 债务
├── 02-requirements/         ← 📋 产品需求
├── 03-modules/              ← 🔧 ★ 核心：功能模块（一个模块一个文件夹）
├── 04-changelog/            ← 📋 AI 工作日志
├── 05-decisions/            ← 🏛️ 跨模块 ADR
└── 99-archive/              ← 🗄️ 归档
```

**旧目录（内容已迁移，待确认后删除）**：
- `ai-work-logs/` → 已迁移到 `04-changelog/logs/`
- `调研分析/` → 功能模块已迁移到 `03-modules/`
- `技术债务与架构决策/` → ADR 迁移到模块 + `05-decisions/`，债务迁移到 `01-guides/debt/`
- `架构设计/` → 活跃设计搬到了模块文件夹，旧方案归档到 `99-archive/`
- `产品需求/` → 已迁移到 `02-requirements/`
- `流程规范/` → 已迁移到 `01-guides/`
- `项目介绍/` → 已归档到 `99-archive/`
- `superpowers/` → 已归档到 `99-archive/superpowers/`

> **维护规则**：新增文档时，同步更新本文档。旧目录加 `.legacy` 后缀，确认无误后删除。

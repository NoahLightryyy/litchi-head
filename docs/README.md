# 📚 litchi-head 文档路由

> 按「受众 × 生命周期」组织：新人、开发者、AI Agent 各有一条入口。

---

## 目录结构

```
docs/
├── README.md                ← 本文：全文档路由
├── 00-overview/             ← 🏠 项目总览（不变信息）
├── 01-guides/               ← 📐 AI 流程 / 路由 / 债务
├── 02-requirements/         ← 📋 产品需求
├── 03-modules/              ← 🔧 ★ 核心：功能模块（一个模块一个文件夹）
├── 04-changelog/logs/       ← 📋 AI 工作日志（按日分文件夹）
├── 05-decisions/            ← 🏛️ 跨模块 ADR
└── 99-archive/              ← 🗄️ 历史归档
```

---

## 文档速查

| 受众 | 文档 | 说明 |
|:----|:-----|:------|
| 🧑‍💻 **入门** | [00-overview/OVERVIEW.md](00-overview/OVERVIEW.md) | 项目一句话定位 + 模块鸟瞰 |
| | [00-overview/GLOSSARY.md](00-overview/GLOSSARY.md) | 术语表 |
| | [00-overview/TECH_STACK.md](00-overview/TECH_STACK.md) | 技术栈 + 选型理由 |
| | [00-overview/ROADMAP.md](00-overview/ROADMAP.md) | 📋 项目进度看板 |
| 🤖 **AI Agent** | [01-guides/WORKFLOW.md](01-guides/WORKFLOW.md) | AI 自动化工作流程 |
| | [01-guides/HANDOVER.md](01-guides/HANDOVER.md) | AI 会话交接文档 |
| | [01-guides/ROUTING.md](01-guides/ROUTING.md) | ★ 上下文加载策略 |
| | [01-guides/ENVIRONMENT.md](01-guides/ENVIRONMENT.md) | 环境配置指南 |
| | [01-guides/TESTING_STRATEGY.md](01-guides/TESTING_STRATEGY.md) | 🧪 ★ 测试架构策略与组织约定 |
| | [01-guides/debt/ROUTER.md](01-guides/debt/ROUTER.md) | 技术债务路由索引 |
| 👨‍💻 **开发者** | [02-requirements/](02-requirements/) | 产品需求 |
| | [03-modules/](03-modules/) | **★ 核心：每个功能一个文件夹** |
| | [05-decisions/](05-decisions/) | 跨模块架构决策记录（ADR） |

---

## 维护规则

新增文档时，同步更新本文档。

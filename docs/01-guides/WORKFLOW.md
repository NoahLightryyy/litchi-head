# 🤖 AI 自动化工作流（索引）

> **1047 行 → 4 份聚焦文档**。按阶段查阅，不用全读。
> 核心纪律：**进哪个部门戴哪个帽子**、四同步（代码+测试+文档+债务）、发现债务必登记。

---

## 📋 文件导航

| 你在干嘛 | 读这个 | 行数 |
|:---------|:-------|:----:|
| 🚀 **开新会话**、判断部门、加载角色 | [workflow/STARTUP.md](workflow/STARTUP.md) | ~200 |
| 🔨 **日常开发**、代码规范、Agent 编排 | [workflow/DEVELOPMENT.md](workflow/DEVELOPMENT.md) | ~350 |
| ✅ **会话收尾**、写日志、管债务、更新文档 | [workflow/CLOSING.md](workflow/CLOSING.md) | ~200 |
| ⚠️ **审视清单**、阻塞、上下文耗尽 | [workflow/EMERGENCIES.md](workflow/EMERGENCIES.md) | ~120 |

---

## 🧭 决策树

```
开始一个新会话？
  │
  ├─ ✅ 是 → workflow/STARTUP.md
  │     （加载部门角色 → 进入第 5 步）
  │
  └─ 已经在干活了？
        │
        ├─ 🔨 正常开发 → workflow/DEVELOPMENT.md
        │     （功能步骤 → 文档同步 → 代码质量）
        │
        ├─ ⚠️ 遇到问题 → workflow/EMERGENCIES.md
        │     （审视清单 → 阻塞 → 上下文耗尽）
        │
        └─ ✅ 干完了要收尾 → workflow/CLOSING.md
              （日志 → 债务 → 看板 → 提交）
```

---

## ⚡ 核心原则速查

| 原则 | 一句话 |
|:-----|:-------|
| **部门角色加载** | 进哪个代码目录 = 戴哪个部门的帽子。不进不戴 |
| **四同步** | 代码 + 测试 + 文档 + 债务，改一个必须改全部 |
| **优先序** | 安全/数据 → 阻塞 → 核心功能 → 可维护性 → 整洁 |
| **债务必登记** | 发现就写，不写就是欠账不还 |
| **质量红线** | make check（lint + type + test）提交前必须全绿 |

---

## 📎 关联文档

| 文档 | 用途 |
|:-----|:------|
| [HANDOVER.md](HANDOVER.md) | 全局交接仪表盘（项目身份卡 + 各部门状态 + 跨部门优先级） |
| [HANDOVER_TIP.md](HANDOVER_TIP.md) | ⚡ 快速交接卡（扫一眼就够） |
| [debt/ROUTER.md](debt/ROUTER.md) | 技术债务路由索引 |
| [ENVIRONMENT.md](ENVIRONMENT.md) | 双 Key 体系 + 模型快慢分离配置 |
| 🔄 [CI 治理体系](ci/README.md) | CI 标准、处理工作流、本地检查、根因知识库 |

---

> **文档版本**：v2.0 — 按阶段拆分为 4 份聚焦文档
> **创建日期**：2026-06-05
> **最近更新**：2026-06-21 — 拆分为 STARTUP / DEVELOPMENT / CLOSING / EMERGENCIES 四模块

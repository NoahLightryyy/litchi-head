# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的 337 行交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP             测试: 617 ✅
债务: 7 条开放 / 紧急指数 1.4   最新提交: 314c7c9
```

## 🕐 上次做了什么

**docs 目录重组**（2026-06-15）：
9 模块聚合 → `03-modules/0?-*/` · ADR 10 个独立文件 · 债务 7 个小文件
ROUTING.md · SPEC 精简 55% · `.legacy` 清理 · 全路径修复

## 🎯 接下来做什么

| 优先级 | 任务 | 工作量 |
|:------:|:-----|:------:|
| 🟡 P1 | **回测→辩论桥接** — TradePlan→TradeRecord 适配器 | 中 |
| 🟡 P1 | **M3 信任度评分** — Agent 输出 vs 实际结果追踪 | 中 |
| ⬇️ P2 | **C1 简报分区输出** — format_market_brief 按区块分区 | 小 |
| ⬇️ P2 | **前端 MVP** — Streamlit 3 页面 | ~2d |

## 📁 快速索引

| 你要干嘛 | 看哪个文件 |
|:---------|:-----------|
| 了解项目全貌 | `docs/00-overview/` |
| 完整交接（给 AI） | [HANDOVER.md](HANDOVER.md) |
| 全局进度看板 | [ROADMAP.md](../00-overview/ROADMAP.md) |
| 债务路由 | [debt/ROUTER.md](debt/ROUTER.md) |
| 模块规格 | `docs/03-modules/0?-*/SPEC.md` |
| 架构决策 | `docs/05-decisions/` |
| 工作日志 | `docs/04-changelog/logs/` |

---
> 每次会话结束时 AI 自动更新本页。如有出入请提醒。

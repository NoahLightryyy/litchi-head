# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的 337 行交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP             测试: 701 ✅
债务: 7 条开放 / 紧急指数 1.4   最新提交: 6a114ed
```

## 🕐 上次做了什么

**M4 动态权重**（2026-06-16）：
aggregate_node 接入 TrustTracker 信任度因子（0.5-1.5）
VoteSummary.trust_weight_factors · D3/M4 权重叠加 · 10 测试全部通过

## 🎯 接下来做什么

| 优先级 | 任务 | 工作量 |
|:------:|:-----|:------:|
| ✅ ~~M4 动态权重~~ | 已完成 | 小 |
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

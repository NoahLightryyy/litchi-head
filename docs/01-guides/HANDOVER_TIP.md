# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的 337 行交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP             测试: 691 ✅
债务: 7 条开放 / 紧急指数 1.4   最新提交: b7caa37
```

## 🕐 上次做了什么

**M3 信任度评分**（2026-06-16）：
`src/debate/trust.py` — TrustTracker + AgentOutcome/TrustMetrics/TrustReport
方向准确率 · Brier 校准 · 偏差检测 · 趋势检测 · 54 测试全部通过

## 🎯 接下来做什么

| 优先级 | 任务 | 工作量 |
|:------:|:-----|:------:|
| 🟡 P2 | **M4 动态权重** — 用信任度调整 aggregate 权重 | 小-中 |
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

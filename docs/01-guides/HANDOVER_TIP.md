# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的 337 行交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP             测试: ✅（M3+M4 信任度 + 桥接双路径）
债务: 7 条开放 / 紧急指数 1.4   最新提交: e5e720d
本次完成: 本地桥接 + 远程 M3/M4 信任度体系合并完成
```

## 🕐 上次做了什么

## 🕐 上次做了什么

**本次合并**（2026-06-16）：
本地完成：P1 桥接 `src/trader/bridge.py` — TradePlan→TradeRecord 转换
远程完成：回测桥接 `src/backtest/bridge.py` + **M3 信任度评分** `src/debate/trust.py` + **M4 动态权重**

## 🎯 接下来做什么

| 优先级 | 任务 | 工作量 |
|:------:|:-----|:------:|
| ✅ ~~本地 P1 桥接~~ | 已完成 | 中 |
| ✅ ~~远程桥接+M3+M4~~ | 已完成 | 中+小 |
| ⬇️ P2 | **C1 简报分区输出** — format_market_brief 按区块分区 | 小 |
| ⬇️ P2 | **前端 MVP** — Streamlit 3 页面 | ~2d |

## 📁 快速索引

| 你要干嘛 | 看哪个文件 |
|:---------|:-----------|
| 了解项目全貌 | `docs/00-overview/` |
| 桥接函数 | `src/trader/bridge.py` |
| 桥接测试 | `tests/test_trader_bridge.py` |
| 完整交接（给 AI） | [HANDOVER.md](HANDOVER.md) |
| 全局进度看板 | [ROADMAP.md](../00-overview/ROADMAP.md) |
| 债务路由 | [debt/ROUTER.md](debt/ROUTER.md) |
| 模块规格 | `docs/03-modules/0?-*/SPEC.md` |
| 架构决策 | `docs/05-decisions/` |
| 工作日志 | `docs/04-changelog/logs/` |

---
> 每次会话结束时 AI 自动更新本页。如有出入请提醒。

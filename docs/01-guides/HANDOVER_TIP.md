# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP → K 线真渲染 + 零造假数据    Python 测试: 721 ✅
前端: 47 文件 / 7 文档 / React+Next.js + Lightweight Charts
后端桥接: FastAPI 7 文件 / 4 组路由（market/stocks/debate/trust）
数据源: 全项目零造假数据 ⚠️ 板块增强层（TD-020）待实现
```

## 🕐 本次做了什么

**Sprint 6 K 线真渲染 + 数据源造假清除**（2026-06-16）：
- ✅ CandlestickChart 组件（lightweight-charts 封装，暗色主题+成交量直方图）
- ✅ KlineChart 自包含数据获取，周期切换（日/周/月线）真正调用后端
- ⚠️ 发现并清除 5 处造假数据（debate-panel 硬编码 + market.py 板块 + chain-map）
- ✅ 全项目 frontend/ + backend/ 零造假数据
- ✅ pnpm build + tsc --noEmit 零错误

## 🎯 接下来做什么

| 优先级 | 任务 | 工作量 |
|:------:|:-----|:------:|
| 🥇 | **后端完善** — trust.py 接入 TrustTracker + capital-flow 路由 | ~0.5d |
| 🥇 | **TD-020 板块增强层** — heat/chain_map/ai_analysis 真实数据源 | ~1.5h |
| 🥈 | **技术指标/资金流向/信任度 tab 面板** — 3 个占位 tab 实现 | ~1d |

## 📁 快速索引

| 你要干嘛 | 看哪个文件 |
|:---------|:-----------|
| 启动后端 | `cd e:/litchi-head && uvicorn backend.main:app --reload --port 8000` |
| 启动前端 | `cd frontend && pnpm dev` |
| 前端规格 | `docs/03-modules/10-frontend/SPEC.md` |
| 路由设计 | `docs/03-modules/10-frontend/ROUTING.md` |
| API 接口 | `docs/03-modules/10-frontend/API.md` |
| 桥接层文档 | `docs/03-modules/11-fastapi-bridge/README.md` |
| 完整交接（给 AI） | [HANDOVER.md](HANDOVER.md) |
| 全局进度看板 | [ROADMAP.md](../00-overview/ROADMAP.md) |
| 债务路由 | [debt/ROUTER.md](debt/ROUTER.md) |
| 视觉设计 | `docs/02-requirements/FRONTEND_VISION.md` |

---
> 每次会话结束时 AI 自动更新本页。如有出入请提醒。

# 前端模块交接 — AI 上下文恢复

> 用于新 AI 会话快速恢复前端开发上下文。
> 完整设计见 [SPEC.md](SPEC.md) · [COMPONENTS.md](COMPONENTS.md) · [API.md](API.md)

## 🎯 当前状态

```
前端脚手架: React + Next.js 16 + Tailwind v4 + shadcn/ui
文件数:     47（app/ 5 + components/ 17 + lib/ 11 + stores/ 2 + 配置 8）
文档数:     7 篇（前端 5 + FastAPI 桥接 2）
模拟数据:   三页全部有 mock，pnpm dev 即可查看
待编码:     backend/ FastAPI 桥接层 + pnpm install + 依赖安装
```

## 🏗️ 架构要点

```
frontend/               ← React + Next.js（端口 3000）
  └── app/              ← 三页路由
        └── page.tsx    ← Page 1: 宏观总览（大盘+板块排行+AI简报）
        └── sector/[id] ← Page 2: 产业链分析（产业链地图+个股列表）
        └── stock/[code] ← Page 3: 个股决策（K线+AI辩论+信任度）

backend/                ← FastAPI 桥接层（端口 8000）[待编码]
  └── routers/
        └── market.py   ← GET /api/market/indices, /sectors, /sector/{id}
        └── stocks.py   ← GET /api/stocks/{code}/quote, /kline, /news
        └── debate.py   ← POST /api/debate/run, GET /result/{id}
        └── trust.py    ← GET /api/trust/report/{agent}, /leaderboard
```

## 🗺️ 三页漏斗导航

```
宏观总览 (/)  ──点击板块──→  产业链分析 (/sector/{id})
     │                              │
     │                              └──点击个股──→  个股决策 (/stock/{code})
     └──搜索个股──────直接跳转─────→
```

## 📦 关键文件索引

| 文件 | 说明 | 状态 |
|:-----|:-----|:----:|
| `docs/02-requirements/FRONTEND_VISION.md` | 调研+视觉方案 | ✅ |
| `docs/03-modules/10-frontend/SPEC.md` | 完整功能规格 | ✅ |
| `docs/03-modules/10-frontend/ROUTING.md` | 路由+参数约定 | ✅ |
| `docs/03-modules/10-frontend/COMPONENTS.md` | 组件树+UI规范 | ✅ |
| `docs/03-modules/10-frontend/API.md` | REST接口设计 | ✅ |
| `docs/03-modules/11-fastapi-bridge/SPEC.md` | FastAPI路由规格 | ✅ |

## 🎨 暗色主题令牌

| Token | 值 | 用途 |
|:------|:---|:------|
| `--bg-primary` | `#0D1117` | 主背景（极深黑） |
| `--bg-secondary` | `#161B22` | 卡片/面板背景 |
| `--accent-blue` | `#2962FF` | TradingView 蓝 |
| `--accent-green` | `#00C853` | 涨/买入 |
| `--accent-red` | `#FF5252` | 跌/卖出 |

## 🚀 启动验证

```bash
# 1. 先看效果
cd frontend && pnpm install && pnpm dev
# → 打开 http://localhost:3000

# 2. 再看文档
# → docs/03-modules/10-frontend/SPEC.md

# 3. 然后编码后端 API
# → backend/ 目录下的 FastAPI 路由
```

## ⚠️ 决策日志

| 决策 | 选项 | 选择 | 理由 |
|:-----|:-----|:-----|:------|
| 前端框架 | Streamlit / Dash / React | **React** | 用户要求高级感 |
| 定位 | 看盘/决策/综合 | **专业看盘+决策漏斗** | 宏观→板块→产业链→个股 |
| K 线图 | TradingView / Lightweight / ECharts | **Lightweight Charts** | 免费12KB，K线原生优化 |
| Python 后端 | 直连/桥接 | **FastAPI 桥接** | 不改造现有代码 |
| AI 辩论位置 | 嵌入/独立/侧栏 | **嵌入个股页** | 不打断决策流 |

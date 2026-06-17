# litchi-head 前端

> 专业散户「自上而下决策漏斗」投资决策看板。
> React + Next.js 16 + Tailwind v4 + TanStack Query + Zustand。

## 快速启动

```bash
# 1. 安装依赖（已完成，首次需执行）
pnpm install

# 2. 启动开发服务器
pnpm dev
# → http://localhost:3000

# 3. 构建验证
pnpm build
pnpm lint
pnpm type-check   # tsc --noEmit
```

> 前端需要后端 API 才能获取真实数据。启动后端参见 [backend/ README](../backend/README.md)。

## 页面路由

| 路径 | 页面 | 说明 |
|:-----|:-----|:------|
| `/` | 宏观总览 | 三大指数 + 板块排行 + AI 宏观简报 + 搜索 autocomplete |
| `/sector/[id]` | 产业链分析 | 产业链地图 + 个股排行 + AI 分析 |
| `/stock/[code]` | 个股决策 | 行情卡片 + K 线图 + 4 Tab（技术分析/资金流向/AI 辩论/信任度） |

## 目录结构

```
frontend/
├── app/                 # Next.js App Router 页面
│   ├── layout.tsx       # 根布局（Server Component，metadata 导出）
│   ├── app-shell.tsx    # 客户端布局外壳（导航高亮 + 进度条 + 动态标题）
│   ├── providers.tsx    # TanStack Query 全局 provider
│   ├── page.tsx         # 宏观总览
│   ├── sector/[id]/     # 板块详情页（骨架屏 + 错误态重试）
│   └── stock/[code]/    # 个股决策页（4 Tab + 错误态重试）
├── components/          # 可复用 UI 组件（含 loading/empty/error 三态）
│   ├── layout/          # AppShell / Sidebar / Header / Breadcrumb
│   ├── macro/           # MarketIndices / SectorRanking / MacroBrief / HotNews
│   ├── sector/          # SectorHeader / ChainMap / ChainAnalysis / StockList
│   └── stock/           # QuoteCard / KlineChart / CandlestickChart
│                        # DebatePanel / NewsFeed / TrustChart
│                        # CapitalFlowPanel / TechnicalIndicatorsPanel
├── lib/                 # 逻辑层
│   ├── api/             # HTTP 客户端（client.ts）+ API 函数（market/stocks/debate）
│   ├── hooks/           # TanStack Query 封装 hooks（use-market / use-stock / use-debate）
│   ├── types/           # TypeScript 类型定义（market / stock / debate）
│   └── utils.ts         # 工具函数（formatPrice / formatChangePct / changeColor）
└── stores/              # Zustand 状态管理
    └── navigation-store.ts  # 面包屑 + 最近浏览
```

## Tab 面板

| Tab | 组件 | 状态 | 后端 API |
|:----|:-----|:----:|:---------|
| 技术分析 | `TechnicalIndicatorsPanel` | ✅ MA/RSI/MACD/布林带 | `technical-indicators` |
| 资金流向 | `CapitalFlowPanel` | ✅ 主力/机构/散户净流入 | `capital-flow` |
| AI 辩论 | `DebatePanel` | ✅ 触发→轮询→结果展示 | `debate/*` |
| 信任度 | `TrustChart` | ✅ 大师排行榜（胜率/Brier/趋势） | `trust/*` |

## 技术栈

| 层 | 技术 | 用途 |
|:---|:-----|:------|
| 框架 | Next.js 16 | App Router + SSR/SSG |
| 渲染 | React 19 | 组件化 UI |
| 语言 | TypeScript 5 | 类型安全 |
| 样式 | Tailwind CSS 4 | 暗色主题 CSS 变量系统（Bloomberg × TradingView） |
| K 线 | Lightweight Charts 4 | TradingView 开源版（真渲染，零造假数据） |
| 图表 | ECharts 5 | 辅助可视化 |
| 数据 | TanStack Query 5 | API 缓存 + 自动轮询 |
| 状态 | Zustand 5 | 全局状态管理 |

## 数据流

```
组件（components/）
  ↑ useQuery hooks（lib/hooks/）
    ↑ API 函数（lib/api/）
      ↑ HTTP client（client.ts）
        ↑ FastAPI 桥接层（backend/ → port 8000）
          ↑ src/data/collector.py + src/debate/
```

- TanStack Query 自动管理缓存、轮询（30s 行情 / 1min 板块 / 5min 简报 / 2min 技术指标）、重试
- 未连接后端时：loading 骨架屏 → 超时后错误态（含重试按钮）
- 搜索 autocomplete 输入 >= 2 字符触发实时查询
- 侧边栏导航路径高亮（usePathname），页面切换顶部加载进度条动画

## 后端 API 基准

| 前置 | 值 |
|:-----|:----|
| API 地址 | `http://localhost:8000/api`（`NEXT_PUBLIC_API_URL`） |
| 后端服务 | uvicorn backend.main:app --port 8000 |
| API 文档 | `http://localhost:8000/docs` |

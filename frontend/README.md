# litchi-head 前端

> 专业散户「自上而下决策漏斗」投资决策看板。
> React + Next.js 16 + Tailwind v4 + TanStack Query。

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
| `/` | 市场总览 | 三大指数 + 板块排行 + 指数摘要 + 搜索 autocomplete |
| `/sector/[id]` | 产业链分析 | 产业链地图 + 个股排行 + AI 分析 |
| `/stock/[code]` | 个股决策 | 行情卡片 + 统一价格走势（当日/五日/日 K）+ 技术、资金、财务、辩论、信任度 |

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
| 流派分析 | `DebatePanel` / `AgentAnalysisList` | 逐流派摘要、论证、依据、风险与独立失败态；真实运行依赖凭据及证据可用 | `debate/*` |
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

## 投资工作区（FW-070）

- `/industries`：行业/概念目录，搜索、排序、分页和详情入口。
- `/screening`：最多四家公司财务与估值原始指标对照；缺值、报告期、待核验零值明确显示，无综合评级。
- `/watchlist`：本机自选与研究假设，编辑、移除和撤销。
- `/portfolio`：手动股票/基金持仓，金额分布与单项集中度；没有账户自动同步或基金穿透。
- `/retro`：手动实际操作账本 + 历史研究复盘。输入归属标识后录入和分页查询；发生时间必须明确时区，数量/价格未知留空。未确认提交在当前标签页保留，可用原标识恢复重试。归属标识仅为逻辑分区，不是登录认证；本批不计算账户盈亏、费用或影子收益。
- `/data-status`：数据源诊断；调用健康不等于数据新鲜。
- `/settings`：本机记录JSON备份/恢复，恢复前预览确认。

自选和持仓保存在当前站点的浏览器存储，换设备或端口须使用备份迁移。预览3001在构建时设置`NEXT_PUBLIC_API_URL=/api`，通过现有Next代理访问8000。

新浪备用板块入口 `/sector/sina/[code]`：本站行情比较、源生成分股分页和站内个股分析链接；来源网站仅在“查看原始数据”打开。指数摘要为确定性行情汇总，不是AI生成。

价格走势图支持滚轮向下缩小到完整数据后切换当日→五日→日 K；最新窗口向上放大到分钟级后反向切换。按钮可直接选范围，日 K 内保留周线/月线。五日数据使用冻结的 [展示契约](../docs/06-departments/08-backend-api/FIVE-DAY-DISPLAY-CONTRACT.md)，只连接真实分钟点，日期标记区分各交易日。单源和缺失状态保留；此接口不参与交易证据认证。

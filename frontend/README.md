# litchi-head 前端

> 面向普通个人投资者的研究助手：不用写专业问题，先看大白话提醒，再按需展开依据。
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
- `/screening`：先搜索股票/行业/概念，展开板块成分股并逐个加入最多四家公司的对比；显示匹配依据、数据限制与分页。财务与估值保留报告期、缺值和待核验零值，无综合评级。
- `/watchlist`：搜索名称/代码一键关注，自动读取行情和已有买入提醒；备注选填，每页10只，支持移除和撤销。
- `/portfolio`：手动股票/基金持仓，金额分布与单项集中度；没有账户自动同步或基金穿透。
- `/retro`：手动实际操作账本 + 历史研究复盘。输入归属标识后录入和分页查询；发生时间必须明确时区，数量/价格未知留空。未确认提交在当前标签页保留，可用原标识恢复重试。归属标识仅为逻辑分区，不是登录认证；本批不计算账户盈亏、费用或影子收益。
- `/data-status`：数据源诊断；调用健康不等于数据新鲜。
- `/settings`：本机记录JSON备份/恢复，恢复前预览确认。

自选和持仓保存在当前站点的浏览器存储，换设备或端口须使用备份迁移。预览3001在构建时设置`NEXT_PUBLIC_API_URL=/api`，通过现有Next代理访问8000。

独立预览可以在构建时设置`LITCHI_BACKEND_URL=http://127.0.0.1:8027`，控制Next的`/api/*`代理目标；默认仍为`http://localhost:8000`。生产构建后变更代理目标需要重建，不能仅在`next start`时改变量。

## 个股新闻展示（XI-007）

`NewsFeed`按股票代码调用`/api/stocks/{code}/news-display?days=30`。新消费者位于`lib/api/news-display.ts`和`lib/news-display.ts`，严格校验身份、版本、来源、时间和状态；已删除旧`useStockNews`、`fetchNews`和`NewsItem`消费链。后端旧`/news`仅为外部旧客户端保留兼容。

东方财富搜索与巨潮公告分别采集；页面分相关新闻、公司公告、提及该股，支持7/30/90天窗口、已取得内容的关键词过滤及每页10条。原文单独打开，搜索结果不自动进入AI证据。刷新失败保留本页上次成功结果及原检索时间；此为页面缓存，不承诺浏览器重启后恢复。来源故障、局部结果、真正查无匹配分别呈现。

消费者验证：`node --experimental-strip-types --test tests/news-display.test.mts`。冻结契约见[API新闻展示契约](../docs/06-departments/08-backend-api/NEWS-DISPLAY-CONTRACT.md)。

新浪备用板块入口 `/sector/sina/[code]`：本站行情比较、源生成分股分页和站内个股分析链接；来源网站仅在“查看原始数据”打开。指数摘要为确定性行情汇总，不是AI生成。

价格走势图使用＋/－按钮平滑调整视野，到完整数据边界后切换当日→五日→日 K；最新窗口持续放大后反向切换。普通滚轮仅滚动页面，不再缩放图表。时间页签可直接选范围，日 K 内保留周线/月线。五日数据使用冻结的 [展示契约](../docs/06-departments/08-backend-api/FIVE-DAY-DISPLAY-CONTRACT.md)，只连接真实分钟点，日期标记区分各交易日。单源和缺失状态保留；此接口不参与交易证据认证。
首页快讯使用 `NewsTopics` 提供热点词云、报道关注点、时间范围和原文筛选。只统计当前返回的去重标题；缺失/无效发布时间不进入时间窗。规则提取不调用AI、不输出多空判断；Provider 数据质量问题仍须独立修复。
板块页“基本面研究”可从当前页选择最多4家公司，通过版本化fundamental-research合并报表接口并列查看；披露日、公式、原始来源可展开。真实零/负数保留，缺值为—。估值TTM分母可见，缺可靠市值时PE/PB/PS不计算。行业指标接口仅提供定义，完整行业AI报告尚未接入。不将所选公司当作整个行业。
独立联调可在构建时设置`NEXT_PUBLIC_API_URL=/api`及`LITCHI_BACKEND_URL=http://127.0.0.1:8010`，默认后端地址保持8000。
独立预览可在构建时设置 `NEXT_PUBLIC_API_URL=/api` 与
`LITCHI_BACKEND_URL=http://127.0.0.1:8002`，让该前端只代理对应的隔离后端。
未设置LITCHI_BACKEND_URL时默认8000。辩论返回ANALYSIS_NOT_CONFIGURED时需
恢复后端DeepSeek配置后重启，前端重试不会修复服务凭据。

### 辩论修复验收（2026-10-01）

`next.config.ts` 将研究请求代理等待从默认30秒延长到600秒，以匹配当前同步
多轮分析接口。此为同步接口兼容修复，不等于已实现异步作业/断线恢复。
结果展示消费已有 `evidence_limitations` / `review_report` / `analyses.success`；
部分成功不掩盖缺失证据。消费者测试：
`node --experimental-strip-types --test tests/debate-error.test.mts tests/debate-limitations.test.mts`。
独立修复预览3002→8002，主窗口3001的图表开发不在本分支替换范围内。
# 分页板块表格（2026-10-07）

`SectorRanking` 每页10行完整展开，不设内部纵向滚动区域。窄屏保留横向滚动；
翻页滚动页面至表格顶部，搜索输入只重置页码，不移动页面。


首页搜索历史默认折叠，点击标题或用键盘展开，可查看、复用、删除及清空记录；搜索与发现页保持默认展开。
离开个股或切换面板后返回，流派分析从服务器历史恢复同股运行/排队任务并继续读取结果；
运行状态优先于自动显示旧结果，用户主动查看历史仍可用。服务器标记失败时展示已有错误，
不会显示初始触发提示或用旧结论替代。此恢复不重新提交模型请求。

### ETF搜索与独立页面（2026-10-26）

首页和搜索页支持沪深ETF名称、代码和ETF类别搜索。类型为`etf`的结果进入
`/etf/[code]`，独立消费`/api/etfs/{code}`及`/api/etfs/{code}/kline?days=730`。
页面依次展示报价、日/周/月K线、各流派辩论、相关资料，基金身份来源默认折叠。
历史图复用联动指标，ETF价格保留三位小数、成交量为份；周月线按同源不复权日线聚合，
展示包含来源已提供的当日日线；盘中标明未收盘，盘后标明采集阶段（按北京时间采集时点，而非查看时点）。
来源尚未更新时保留实际截止日期；周月线尾部周期可能未完成。任一来源有效即可显示，刷新失败保留旧图及原日期。
ETF复用完整辩论面板，显式传`instrument_type=etf`；缓存、历史和结果按类型及代码隔离，
旧缺类型记录只归股票。打开页面只读取资料与历史，用户点击才启动分析；不套用股票财务。
契约见[ETF展示契约](../docs/06-departments/08-backend-api/ETF-DISPLAY-CONTRACT.md)、
[ETF日线契约](../docs/03-modules/08-backend-api/ETF_KLINE_CONTRACT.md)及
[ETF辩论契约](../docs/03-modules/08-backend-api/ETF_DEBATE_CONTRACT.md)。

## 政策与本金研究样例（2026-10-18）

板块（东方财富及新浪）、股票、ETF详情页统一嵌入 `components/research/research-context.tsx`。
默认自动检索已有相关资料，提供来源、发布日期、匹配原因与可编辑关键词；政策候选和报道分组。
ETF页将其放在K线和辩论之后。相关性不等同于已核验的标的证据，不自动创建付费任务。

已核验证据包与AI深入研究、本金执行核验分别折叠。缺少专属证据包不阻断上方只读资料检索，
但仍不能借用其他标的的claims、持仓或开放本金执行。账户、费率及交易规则缺失时仍返回缺项。

`/policy`、`/capital`保留历史样例入口；`capital-comparison.tsx`的本地假设计算和
`policy-sample.tsx`的历史材料与详情页正式检索/证据/任务接口分开，计算模块及原测试保持不变。

## AI产业结构草图（2026-10-18）

板块缺核验地图时，ChainDraftMap自动调用独立chain-draft接口，绘制通用环节/概念结构与虚线推断关系，显示待核验项、模型和生成时间。后端持久化后再返回，重访复用；仅对暂时错误有限次自动恢复。核验图与草图保持不同契约，详见docs/06-departments/08-backend-api/CHAIN-DRAFT-CONTRACT.md。

2026-10-18恢复逻辑修正：首次缺图自动请求；失败后返回页面或恢复联网重新获取，成功结果保持新鲜且不重复生成。繁忙最多6次自动重试，网络/429最多2次，模型失败/超时最多1次；间隔5至15秒。参数、缓存存储及消费者结构错误不在当前页面自动重试。次数耗尽显示错误与手动重试，不永久锁死失败缓存。

### 辩论结果的数据说明（2026-10-26）

`lib/debate-limitations.ts` 将现有证据限制转为按能力分组的简短说明；
`components/stock/debate-data-notice.tsx` 默认折叠原始诊断，股票与ETF共用。
收盘价和有限新闻样本用中性色；数据冲突、分析失败、缺评审仍直显，未知能力不隐藏。
消费者仅补齐后端已有可选 `error_codes` 字段；不修改历史结果、不重跑AI或调整交易门禁。
相关验证：`tests/debate-limitations.test.mts`、`tests/debate-data-notice.test.mts`、`tests/debate-instrument.test.mts`。

### 产业结构代表企业（2026-10-26）

AI结构图增加按环节分组的企业清单、业务与影响力理由及来源；人形机器人已有6家公司官方资料。
新消费者 `lib/chain-companies.ts` 校验板块、节点、企业与来源；A股身份核对后才给股票入口。
图和公司补充独立缓存，首次自动补充，显式更新才重新生成；失败仍保留原图及旧成功清单。
契约见 `docs/03-modules/08-backend-api/CHAIN_COMPANIES_CONTRACT.md`；测试 `tests/chain-companies.test.mts`。

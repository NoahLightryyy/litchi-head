---
department: 前端部
codebase: frontend/
last_updated: 2026-06-22
---

# 🎨 前端部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 三页路由（首页→板块→个股） | ✅ | Next.js 16 App Router |
| 17 个功能组件 + 4 布局组件 | ✅ | 含 loading/error/empty/data 四态 |
| K 线真渲染（CandlestickChart） | ✅ | Lightweight Charts 成交量直方图 |
| 暗色主题系统 | ✅ | CSS 变量 + Tailwind, Bloomberg × TradingView 配色 |
| 搜索 autocomplete | ✅ | 防抖 300ms + useStockSearch hook |
| 4 Tab 面板（个股页） | ✅ | 辩论/技术指标/资金流向/信任度 |
| 离线检测 | ✅ | `useOnlineStatus()` + 全局离线横幅 |
| Error Boundary | ✅ | `error.tsx` + `not-found.tsx` |
| 全局状态 | ✅ | Zustand 面包屑 + 最近浏览 |

### 测试

| 检查项 | 结果 |
|:-------|:----:|
| `pnpm build` | ✅ 零错误 |
| TypeScript strict | ✅ 零 `any`、零 `@ts-ignore` |
| 前端 mock 数据 | ✅ 零造假 |

### 关键架构决策

- **React Server Component 架构**：页面级 Server Component 包装 Client Component
- **TanStack Query 数据获取**：所有 API 调用通过 hooks 封装，组件不直接 fetch
- **TypeScript 类型手动同步**：从 Pydantic 模型手导（待自动化）

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-033 | capital-flow-panel.tsx `.reverse()` 变异数组违反不可变性 | 🟢 | 5min |

## 已关闭

| ID | 标题 | 修复日期 |
|:---|:-----|:--------|
| TD-025 | 全局 Error Boundary 缺失 | 2026-06-17 |
| TD-026 | 骨架屏永不消失 | 2026-06-17 |
| TD-027 | 无离线检测 | 2026-06-17 |
| TD-028 | 搜索无防抖 | 2026-06-17 |
| TD-029 | 死代码未清理 | 2026-06-17 |
| TD-030 | 资金流向绕过 Provider 层 | 2026-06-17 |
| TD-031 | 辩论轮询永不停止 | 2026-06-17 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🟢 | TD-033 修 `.reverse()` → `.toReversed()` | 无 |
| 2 🟢 | 浏览器端四态全量验证（拔网线/空数据/超时） | 无 |
| 3 🟢 | TypeScript 类型与 Pydantic 模型自动同步 | 后端 API 部 |

### 结果回调（RC 系列，2026-06-23 新增）

> 完整方案见 [ROADMAP.md RC 轨道](../../00-overview/ROADMAP.md#rc-结果回调轨道2026-06-23-新增--规划阶段)。

| RC | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **RC-003** 🥇 | **UB-TRACK 前端用户行为采集** — 用户在个股页执行操作（买入/卖出/关注）时，调用 `POST /api/user/action` 记录操作 + 理由 + 分类；后续展示"你的操作记录"区块 | 后端 API 部 RC-003 API | ~1h |

### 用户经验反馈闭环（UI 系列，2026-06-23 新增 — 架构第9层）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 前端部在闭环中负责：操作按钮 + 理由弹窗 + RetroBoard 前端页面 + 镜子展示。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-1c** 🥇 | **操作按钮+理由弹窗** — 个股决策页新增"买入/卖出/关注/忽略"按钮 + 简短理由输入弹窗（分类选择：技术分析/消息驱动/情绪驱动/基本面） | 后端 API 部 UI-1b | ~2h |
| **UI-3b** 🥈 | **RetroBoard 前端** — 新页面 `/retro` 展示 AI推荐 vs 用户操作 vs 实际盈亏 三列对比表格 + 聚合卡片（AI准确率/你跟AI胜率/最佳Agent） | 后端 API 部 UI-3a | ~3h |
| **UI-4b** 🥉 | **镜子展示** — 决策前弹出对比提示（数据充足时）| 后端 API 部 + 辩论引擎部 | ~2h |
| **UI-4c** 🥉 | **Wrapped 报告** — 周/月行为摘要页面 | UI-3b | ~2h |

### 基本面深度（FD 系列，2026-06-23 新增）

> 完整背景见 [FUNDAMENTAL_RESEARCH.md](../../02-requirements/FUNDAMENTAL_RESEARCH.md)。

| FD | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **FD-003a** 🥇 | **前端金融类型** — 新增 `FinancialMetric` / `IndustryPosition` / `SupplyChainNode` 类型定义到 `lib/types/market.ts` | 后端 API 部 FD-002b/002c | ~30min |
| **FD-003b** 🥇 | **FinancialSummary 组件** — 财务健康概览卡片（ROE/毛利率/负债率/PE四宫格+趋势），覆盖 loading/error/empty/data 四态 | FD-003a | ~3h |
| **FD-003c** 🥇 | **个股页新增财务 Tab** — 在 stock/[code] 4 Tab 基础上增加"财务"Tab 面板 | FD-003b | ~1h |
| **FD-003d** 🥈 | **ChainMap 注入真实数据** — `frontend/components/sector/chain-map.tsx` 从后端真实 API 获取产业链数据替代伪数据 | 后端 API 部 FD-002a | ~2h |
| **FD-003e** 🥈 | **板块页财务聚合** — sector/[id] 页面展示板块级财务汇总（行业平均 ROE/负债率等） | FD-003b + 后根部 FD-002e | ~2h |

### 组件树变更

```
frontend/components/
├── sector/
│   └── chain-map.tsx          ← FD-003d: 注入真实产业链数据
├── stock/
│   ├── debate-panel.tsx
│   ├── technical-indicators-panel.tsx
│   ├── capital-flow-panel.tsx
│   ├── financial-summary.tsx  🆕 ← FD-003b: 财务健康卡片
│   └── fundamentals-panel.tsx 🆕 ← FD-003c: 基本面分析 Tab（含多期对比）

frontend/lib/types/market.ts  ← FD-003a: 新增类型
  ├── FinancialMetric
  ├── IndustryPosition
  └── SupplyChainNode
```

### 终端展示效果

```
个股决策页（stock/[code]）
├── Tab 1: 🤖 AI 辩论      （已有）
├── Tab 2: 📊 技术指标      （已有）
├── Tab 3: 💰 资金流向      （已有）
├── Tab 4: 🏛️ 财务健康 🆕  ← FD-003c
│   ├── 盈利能力卡片（ROE/ROA/毛利率 多期趋势）
│   ├── 估值水平卡片（PE/PB/PS 当前值+历史分位）
│   ├── 成长性卡片（营收增速/利润增速）
│   └── 负债与现金流卡片（负债率/自由现金流）
└── Tab 5: 🎯 信任度        （已有）

板块分析页（sector/[id]）
├── 板块行情卡片              （已有）
├── 产业链图谱                ← FD-003d: 真实数据替代伪数据
├── 板块财务概览 🆕           ← FD-003e: 行业平均指标
└── 成分股列表                （已有）
```

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **DP-003** 🥇 | **偏斜公示展示** — 辩论结果卡片新增偏斜度指标（悲观/乐观偏斜百分比 + 历史趋势） | 辩论引擎部 D4 输出 BiasReport | ~1h |
| **DP-006** 🥈 | **镜子历史对比** — 决策页面新增"历史类似情况"区块，展示上次同市况时各大师的准确率 | 记忆系统部 反射存储接口就绪 | ~2h |

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `frontend/app/page.tsx` | — | 宏观总览页 |
| `frontend/app/sector/[id]/page.tsx` | 134 | 板块分析页 |
| `frontend/app/stock/[code]/page.tsx` | 130 | 个股决策页（4 Tab） |
| `frontend/components/stock/candlestick-chart.tsx` | 138 | K 线图（Lightweight Charts） |
| `frontend/components/stock/debate-panel.tsx` | 191 | 辩论面板 |
| `frontend/components/stock/technical-indicators-panel.tsx` | 302 | 技术指标面板 |
| `frontend/components/stock/capital-flow-panel.tsx` | 134 | 资金流向面板（⚠️ TD-033） |
| `docs/06-departments/09-frontend/ROLE.md` | — | 👤 前端部角色定义 |
| `docs/06-departments/09-frontend/STANDARDS.md` | — | 📐 前端部技术规范 |

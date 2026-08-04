---
department: 前端部
codebase: frontend/
last_updated: 2026-07-30 (K 线口径与 KR-5 展示计划批准)
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
| 4 Tab 面板（个股页） | ✅ | 辩论/技术指标/资金流向/财务分析/信任度 |
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
| 4 🔥 | KR-5 K 线证据展示：四层状态、RAW/复权口径、基准日、冲突和来源不足可见 | KR-3B-1 成功组装已完成；KR-3B-2～5 待完成。前端不得把条款事件展示为可用复权 |

### 盘中决策页目标（2026-07-30 确认）

- 开盘后“AI 辩论”保持可用，不显示“等待日 K 收盘”；
- 历史蜡烛只渲染已确认 `FINAL_DAILY`；今日动态蜡烛单独标记“盘中形成中”；
- 实时价、分时战况和今日动态 OHLC 显示各自采集时间与新鲜度；
- 正式均线/指标与“含盘中估算”版本必须有清晰标签，不能只靠颜色区分；
- 明示原始/前复权/后复权、复权基准日和 `as_of`；订单参考价只显示 RAW/实时坐标；
- 证据不完整时展示缺失层、来源与重试建议，不展示看似完整的旧 AI 结论；
- RAW 冲突、复权冲突和独立上游不足使用不同用户文案；北交所不得单源绿灯；
- 收盘并完成多源确认后，今日动态蜡烛才转为普通历史蜡烛。

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
| **FD-004a** 🥇 | **前端金融类型** — 新增 `FinancialMetrics` / `ValuationMetrics` 类型定义到 `lib/types/stock.ts` | 无 | ✅ 已完成 |
| **FD-004b** 🥇 | **FinancialPanel 组件** — 财务健康概览（估值比率四宫格+盈利能力+增长+财务健康+每股指标+运营效率+历史对比表），覆盖 loading/error/empty/data 四态 | FD-004a | ✅ 已完成 |
| **FD-004c** 🥇 | **个股页新增财务 Tab** — 在 stock/[code] 5 Tab 基础上增加"财务分析"Tab 面板 | FD-004b | ✅ 已完成 |
| **FD-004d** 🥈 | **ChainMap 注入真实数据** — `frontend/components/sector/chain-map.tsx` 从后端真实 API 获取产业链数据替代伪数据 | 后端 API 部 FD-003a | ~2h |
| **FD-004e** 🥈 | **板块页财务聚合** — sector/[id] 页面展示板块级财务汇总（行业平均 ROE/负债率等） | FD-004b + 后根部 FD-003e | ~2h |

### 产品定位新任务（PD 系列，2026-07-23 新增）

> **战略背景**：详见 [PRODUCT-POSITIONING.md](../../99-archive/PRODUCT-POSITIONING.md)。
> 核心方向：前端展示"三维分析"——让散户一眼知道这个公司在产业链什么位置、该看哪几个关键指标。
> 和现有的 5 Tab 互补：三维分析是"价值观/位置"的展示，财务 Tab 是"数据"的展示。

| PD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **PD-011** 🥇 | **产业链位置标签** — 个股页顶部新增"产业链位置"标签条（如"电池制造 · 中游"），点击展开理由（"主营动力电池制造→处于中游加工位置"）| ⬜ **待办** | 后端 PD-008 | ~1h |
| **PD-012** 🥇 | **关键指标卡片** — 个股页新增"当前关键指标"卡片，只显示该行业/位置相关的 5-10 个指标（银行只看净息差/不良率/PB等，不显示毛利率/存货周转率等无关指标）| ✅ **已完成**（融入 FinancialPanel） | 后端 PD-009 | ~2h |
| **PD-013** 🥇 | **指标解读气泡** — 每个关键指标旁带 ? 气泡，点击显示一句话解释（如"净息差=银行赚利差的能力，越高越好"），同时标注"这个指标在行业中的分位" | ⬜ **待办** | PD-012 | ~1h |
| **PD-014** 🥈 | **行业对比模块** — 在个股页展示当前指标与同行业均值的对比（柱状图/雷达图） | ⬜ **待办** | PD-012 | ~2h |

### 组件树变更

```
frontend/components/
├── stock/
│   ├── financial-panel.tsx         ✅ ← FD-004b: 财务指标+估值比率面板
│   ├── industry-position-badge.tsx  🆕 ← PD-011: 产业链位置标签条
│   ├── key-indicators-card.tsx     🆕 ← PD-012: 动态关键指标卡片
│   ├── indicator-tooltip.tsx       🆕 ← PD-013: 指标解读气泡
│   └── industry-comparison.tsx     🆕 ← PD-014: 行业对比模块
```

### 终端展示效果（更新 2026-07-23）

```
个股决策页（stock/[code]）
├── 🏷️ 产业链位置标签条 ← PD-011 🆕
│   "宁德时代 · 电池制造 · 中游 — 主营动力电池制造，处于产业链加工环节"
│
├── 📋 关键指标（按行业筛选）← PD-012 🆕
│   "该行业/位置的关键指标：毛利率(↓)、应收周转(→)、研发费用(↑)、大客户集中度(？)"
│   各指标带解读气泡 ← PD-013 🆕
│   [行业对比雷达图] ← PD-014 🆕
│
├── Tab 1: 🤖 AI 辩论      （已有）
├── Tab 2: 📊 技术指标      （已有）
├── Tab 3: 💰 资金流向      （已有）
├── Tab 4: 🏛️ 财务分析      （✅ FD-004c 已完成）
└── Tab 5: 🎯 信任度        （已有）
```

> 基于 2026-06-22 设计哲学会议。完整背景见 [DESIGN_PHILOSOPHY.md](../../00-overview/DESIGN_PHILOSOPHY.md)。

| DP | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **DP-003** 🥇 | **偏斜公示展示** — 辩论结果卡片新增偏斜度指标（悲观/乐观偏斜百分比 + 历史趋势） | 辩论引擎部 D4 输出 BiasReport | ~1h |
| **DP-006** 🥈 | **镜子历史对比** — 决策页面新增"历史类似情况"区块，展示上次同市况时各大师的准确率 | 记忆系统部 反射存储接口就绪 | ~2h |

---

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
前端必须分开展示“功能完成度”和“证据成熟度”，并显示主 baseline、样本量、时间窗、
成本、置信区间、拒答、失败及限制。没有足够真实样本时不得用绿色状态暗示投资效果通过。

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `frontend/app/page.tsx` | — | 宏观总览页 |
| `frontend/app/sector/[id]/page.tsx` | 134 | 板块分析页 |
| `frontend/app/stock/[code]/page.tsx` | 130 | 个股决策页（5 Tab：技术分析+资金流向+财务分析+AI辩论+信任度） |
| `frontend/components/stock/candlestick-chart.tsx` | 138 | K 线图（Lightweight Charts） |
| `frontend/components/stock/debate-panel.tsx` | 191 | 辩论面板 |
| `frontend/components/stock/technical-indicators-panel.tsx` | 302 | 技术指标面板 |
| `frontend/components/stock/capital-flow-panel.tsx` | 134 | 资金流向面板（⚠️ TD-033） |
| `frontend/components/stock/financial-panel.tsx` | 🆕 | 🏛️ 财务分析面板（财务指标+估值比率+历史对比表） |
| `docs/06-departments/09-frontend/ROLE.md` | — | 👤 前端部角色定义 |
| `docs/06-departments/09-frontend/STANDARDS.md` | — | 📐 前端部技术规范 |

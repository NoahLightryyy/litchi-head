# 💻 代码实现债务

> 代码实现层面的缺陷：错误处理缺失、硬编码、类型不安全等。

---

###### TD-003 MessageRouter 纯内存存储

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:core` `impact:运行时稳定` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼1h |

**描述**：
`MessageRouter._messages` 是内存 dict，进程重启全部丢失。

**利息分析**：
- Phase 0 影响不大（单次会话不跨进程）
- Phase 1 辩论系统上线后，需要持久化辩论记录

**修复方向**：
- 短期：添加 `save_snapshot()` / `load_snapshot()` JSON 持久化
- 长期：SQLite 存储

---

###### TD-006 EvidenceItem 无校验逻辑

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:core` `impact:代码质量` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼30min |

**描述**：
`EvidenceItem` 只是数据容器，无任何校验逻辑。

**修复方向**：
添加 `validate_chain()` 方法，验证来源可追溯。

---

###### TD-007 ensure_dirs() 从未被调用

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:utils` `impact:运行时稳定` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼10min |

**描述**：
`config.py` 中的 `ensure_dirs()` 函数定义了目录创建逻辑但未被调用。

---

###### TD-020 后端板块/产业链数据增强层缺失 ✅ 已关闭

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:backend` `impact:功能完整性` |
| **发现日期** | 2026-06-16 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审视 |
| **状态** | `✅ 已关闭` |
| **实际工时** | ∼2h |

**修复内容**：
`backend/routers/market.py` 完整重写，从 `empty()` 字典改为真实数据：
1. ✅ 板块排行 — `ak.stock_board_industry_name_em()` 直接获取涨跌幅+主力净流入
2. ✅ 成分股列表 — `ak.stock_board_industry_cons_em(symbol)` 获取真实个股行情
3. ✅ heat — 成分股涨跌比计算（≥60%→high, 40-60%→medium, <40%→low）
4. ✅ chain_map — 涨幅分层（龙头层前20%/中坚层中60%/基础层后20%）
5. ✅ ai_analysis — 从成分股数量/涨跌比/平均涨跌幅自动生成格式化分析
6. ✅ ai_rating — 涨跌幅→A(≥5%)/B+(≥2%)/B(≥0)/C(≥-3)/D

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:utils` `impact:可部署性` |
| **发现日期** | 2026-06-05 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼30min |

**描述**：
模型价格硬编码在 `cost_tracker.PRICES` 类属性中。调价需改代码→重新部署。

**修复方向**：
价格表移入 `config/prices.yaml`，运行时加载。

---

###### TD-018 编排层缺少成本优化

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:debate` `impact:运行时成本` |
| **发现日期** | 2026-06-14 |
| **状态** | `📋 已确认` |
| **本金估算** | ∼1d |

**描述**：
当前编排器对所有 ticker 跑完整的 9 层链路，无短路优化。每次约 15 次 LLM 调用，成本是竞品 1.5-2 倍。

**修复方向**：
1. 短路优化：数据为空 → 直接返回
2. 层合并：简单问题跳过分析师层
3. 模型分层：分析师用便宜模型，策略师用推理模型

---

###### TD-021 辩论编排器 21 处 `except Exception: pass` 静默吞掉所有异常

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:debate` `impact:运行时稳定` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼15min |

**修复内容**：
`src/debate/orchestrator.py` 所有 16 处 `except Exception: pass` 改为 `except Exception as e: logger.warning("xxx: %s", e)`。
- 数据采集失败 (行情/K线/新闻) → logger.warning
- Pydantic 解析失败 (PeerReviewRound/IndependentReview/VoteSummary) → logger.warning
- 记忆存储/查询失败 → logger.warning
- 信任度查询失败 → logger.warning
- 最终结果解析失败 → logger.warning

---

###### TD-022 `collect_data_node` 变量未初始化导致必然崩溃

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:debate` `impact:运行时稳定` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | 无需修改（代码中已有初始化） |

**描述**：
审计时发现 `src/debate/orchestrator.py` 行 144-155 中三个连续 try 块如果全部异常，行 158 `for q in quotes` 会触发 `UnboundLocalError`。
**实际检查**：代码行 138-140 已有 `quotes, klines, news = [], [], []`，变量已初始化，TD-022 不构成实际风险。

---

###### TD-023 后端所有 API 返回 HTTP 200，无法区分"正常空"和"系统崩溃"

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:backend` `impact:可观测性` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼10min |

**修复内容**：
1. `backend/routers/trust.py` — 异常时改为 `raise HTTPException(status_code=503)`
2. `backend/routers/debate.py` — `run_debate` 失败时改为 `raise HTTPException(status_code=500)`
3. `backend/routers/stocks.py` 和 `backend/routers/market.py` — 数据源级失败保持空数据返回（这是预期行为），异常路径已有 logger.exception
4. 前端 TanStack Query 自动识别非 2xx 状态码，设置 `isError = true`

**待办**：
- `backend/routers/market.py` 和 `backend/routers/stocks.py` 的路由级别 catch-all 尚未添加

---

###### TD-024 外部数据源调用无超时设置

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:data+backend` `impact:运行时稳定` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼30min |

**修复内容**：
1. 🆕 `backend/async_utils.py` — `run_sync()` 工具函数，用 `asyncio.to_thread()` + `asyncio.wait_for(timeout=15)` 将同步调用转为可超时的异步调用
2. `backend/routers/stocks.py` — 5 处同步调用改为 `await run_sync(...)`
3. `backend/routers/market.py` — 6 处同步调用改为 `await run_sync(...)`

---

###### TD-025 前端无全局 Error Boundary，组件崩溃导致白屏

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:frontend` `impact:用户体验` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼10min |

**修复内容**：
1. 🆕 `frontend/app/error.tsx` — 含"重新加载"按钮的全局 Error Boundary
2. 🆕 `frontend/app/not-found.tsx` — 含"返回首页"链接的 404 页面

---

###### TD-026 前端宏观页骨架屏永不消失

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:frontend` `impact:用户体验` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼15min |

**修复内容**：
1. `frontend/app/page.tsx` — 解构 `isError` 并传给子组件
2. `frontend/components/macro/market-indices.tsx` — loading / error / empty / data 四态分离
3. `frontend/components/macro/sector-ranking.tsx` — loading / error / empty / data 四态分离
4. `frontend/components/macro/macro-brief.tsx` — 增加 error 态 UI

---

###### TD-027 前端无离线/网络断连检测

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:frontend` `impact:用户体验` |
| **发现日期** | 2026-06-17 |
| **修复日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `✅ 已修复` |
| **实际工时** | ∼10min |

**修复内容**：
1. `frontend/app/app-shell.tsx` — 添加 `useOnlineStatus()` hook
2. 使用 `navigator.onLine` + `online`/`offline` 事件监听
3. 离线时顶部显示红色横幅 "⚠ 网络已断开，数据可能无法更新"
4. 在线时自动隐藏

---

###### TD-028 前端搜索无防抖，高频打后端

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:frontend` `impact:性能` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼15min |
| **实盘影响** | 🟡 盘中高频搜索可能触发后端限流 |
| **触发场景** | 用户在搜索框快速输入股票名（如"贵州茅台"） |
| **用户能发现吗** | ❌ 不能 — 多余请求在后台发生，用户无感知但后端被打 |

**描述**：
`frontend/app/page.tsx:38` 搜索 `onChange` 直接 `setSearchQuery`，无 `useDebounce`。输入"贵州茅台"会在 4 次按键间发 2-4 个请求（受 `enabled: query.length >= 2` 限制）。

**修复方向**：
1. 添加 `useDebounce(searchQuery, 300)`，300ms 后才发请求
2. 或使用 `useQuery` 的 `enabled` + 延迟触发组合

---

###### TD-029 前端死代码（150 行布局 + 未用 store + 1MB ECharts 依赖）

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:frontend` `impact:可维护性` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **实盘影响** | 🟢 不影响功能，但影响构建速度和维护 |
| **触发场景** | 新人接手时、重构时发现大量死代码 |

**描述**：
1. ❌ `components/layout/` 下 5 个文件 ~150 行 — 全量死代码，当前 App 用的是内联定义的组件
2. ❌ `stores/navigation-store.ts` — Zustand store 定义但没有任何组件引用
3. ❌ `package.json` 依赖 `echarts` + `echarts-for-react`（~1MB + ~300KB）— 所有图表已用 lightweight-charts 实现

**修复方向**：
1. 删除 `components/layout/` 目录
2. 删除 `stores/navigation-store.ts`
3. 从 `package.json` 移除 `echarts` 和 `echarts-for-react`

---

###### TD-030 资金流向接口绕过数据源抽象层

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:backend` `impact:架构一致` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1h |
| **实盘影响** | 🟡 切换到 adata 模式时，资金流向仍使用 akshare，数据源策略不一致 |
| **触发场景** | 配置为 adata 数据源时，资金流向偷偷走 akshare |
| **用户能发现吗** | ❌ 不能 — 数据看起来正常，但来源和配置不一致 |

**描述**：
`backend/routers/stocks.py:73-97` 的 `_capital_flow_from_akshare` 直接 `import akshare as ak`，完全绕过 `DataCollector` 和 Provider 抽象层。配置为 adata 模式时资金流向仍偷偷用 akshare。

**修复方向**：
将资金流向迁移到 `DataCollector`/Provider 接口，经过缓存和健康监控。

---

###### TD-031 辩论前端轮询永不停止

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:frontend` `impact:性能` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼20min |
| **实盘影响** | 🟡 辩论失败时前端无限轮询，浪费用户流量和系统资源 |
| **触发场景** | 辩论后端返回错误或不返回 vote_summary |
| **用户能发现吗** | ❌ 不能 — 用户在浏览器看不到多余的请求 |

**描述**：
`frontend/lib/hooks/use-debate.ts:33-37` 轮询机制检查 `data?.vote_summary` 来决定是否继续轮询。如果后端返回错误或不返回 vote_summary，轮询永不停止。

**修复方向**：
1. 添加最大轮询次数（如 30 次 ≈ 1 分钟）
2. 添加 `retry` 失败时自动停止

---

###### TD-032 FallbackSource 切换后永不恢复主源

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:data` `impact:性能` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1h |
| **实盘影响** | 🟡 主源短暂恢复后系统仍停留在降级路径，性能降低 |
| **触发场景** | 数据源短暂中断后恢复 |
| **用户能发现吗** | ❌ 不能 — 功能正常但数据可能不是最优源 |

**描述**：
`src/data/providers/fallback.py:144-155` 一旦某个端点标记为 `_using_fallback[endpoint] = True`，永远不自动恢复主源。主源恢复后，系统无限期停留在次优备用源上。

**修复方向**：
1. 备用源连续成功 N 次后自动恢复主源（如 3 次连续成功）
2. 或添加定时探活机制

---

###### TD-033 前端 `capital-flow-panel.tsx` 使用 `.reverse()` 变异数组违反 React 不可变性

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:frontend` `impact:代码质量` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼5min |
| **实盘影响** | 🟢 当前 React 版本未见异常，未来并发模式下可能出问题 |
| **触发场景** | React 18/19 并发模式下 render |

**描述**：
`frontend/components/stock/capital-flow-panel.tsx:80` 直接调用 `.reverse()` 就地修改数组。React 19 并发模式下可能导致渲染不一致。

**修复方向**：
改为 `[...recent].reverse()` 或 `recent.toReversed()`

---

###### TD-034 `zzshare.py` 字段选择死条件逻辑错误

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:data` `impact:代码质量` |
| **发现日期** | 2026-06-17 |
| **发现人** | AI 审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼5min |
| **实盘影响** | 🟢 当前不影响功能（字段名相同），但代码有误导性 |
| **触发场景** | 代码维护者阅读时困惑 |

**描述**：
`src/data/providers/zzshare.py:148-149` `date_key = "trade_date" if "trade_date" in row else "trade_date"` — 条件判断两边值一样，永远返回 `"trade_date"`。

**修复方向**：
修复为正确的字段名选择逻辑，或直接使用 trade_date

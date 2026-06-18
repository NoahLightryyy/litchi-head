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

---

###### TD-053 多处静默异常未记录（已修复 ✅）

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:critical` `module:multiple` `impact:可观测性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察 |
| **修复日期** | 2026-06-18 |
| **状态** | `✅ 已关闭` |
| **实际工时** | ∼2h |

**描述**：
2026-06-18 全面按察审计发现 9 处 CRITICAL 静默吞异常，涉及 7 个文件。详见 CLOSED.md TD-042~TD-049。

---

###### TD-054 backend CORS 地址硬编码

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:backend` `impact:可部署性` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼10min |
| **实盘影响** | 🟢 开发环境正常，换端口/域名部署需要改代码 |
| **触发场景** | 后端部署在不同的端口或域名上 |
| **用户能发现吗** | ✅ 能 — 前端显示 CORS 错误，空白页面 |

**描述**：
`backend/main.py:75-76` 中 `origins = ["http://localhost:3000", "http://127.0.0.1:3000"]` 硬编码。部署到其他端口/域名时需改代码。

**修复方向**：
从环境变量 `BACKEND_CORS_ORIGINS` 读取，逗号分隔，默认值保持当前配置。

---

###### TD-055 LLM 提供商价格硬编码

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:utils` `impact:运行时维护` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼30min |
| **实盘影响** | 🟢 当前价格准确，调价后系统显示错误费用 |
| **触发场景** | 模型提供商调整价格（每年 1-2 次） |
| **用户能发现吗** | ❌ 不能 — 费用记录不准确，但 AI 功能正常 |

**描述**：
`src/utils/cost_tracker.py:12-16` CostTracker.PRICES 以类属性硬编码模型定价。价格变更必须改代码重新部署。

**修复方向**：
移至 `config/prices.yaml`，运行时加载，文件缺失时回退到硬编码默认值。

---

###### TD-059 性能分析从未进行

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:moderate` `module:all` `impact:性能` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼1d |
| **实盘影响** | 🟡 不知道 LLM 调用延迟基线、API 响应时间、内存使用模式。无法定位性能瓶颈，也无法设立性能回归防线 |
| **触发场景** | 用户抱怨"太慢" — 没有基线数据就无法判断是正常还是异常 |
| **用户能发现吗** | ✅ 能 — 页面加载慢/辩论反应卡，但用户不知道是哪个环节慢 |

**描述**：
项目运行至今从未进行过系统性性能分析。盲区包括：

**未测量的维度**：
1. ❌ LLM 调用延迟分布（p50/p95/p99）— AI 功能核心瓶颈
2. ❌ API 端点响应时间（17 个端点 + 数据源）
3. ❌ 辩论全程耗时（9 层链路，~15 次 LLM 调用）
4. ❌ 数据源采集延迟（akshare vs adata vs zzshare 对比）
5. ❌ 内存使用（辩论上下文/缓存/记忆系统）
6. ❌ 前端首次渲染时间（FCP/LCP）
7. ❌ 前端 API 请求瀑布图

**已有工具未利用**：
- `src/utils/cost_tracker.py` 已有费用追踪，但无耗时追踪
- `src/data/collector.py` 已有 health_stats，但只有成功率无延迟分布

**修复方向**：
1. 建立性能基线：用 `cProfile` 或 `py-spy` 录制一次完整辩论流程
2. CostTracker 扩展：加耗时记录
3. DataCollector health_stats 扩展：加延迟统计
4. 前端加 Performance 面板（仅开发环境）
5. 记录基线数据到 `docs/performance/BASELINE.md`

---

###### TD-060 Python 后端死代码从未扫描

| 属性 | 值 |
|------|-----|
| **分类** | `💻 implementation` `severity:minor` `module:all` `impact:代码质量` |
| **发现日期** | 2026-06-18 |
| **发现人** | AI 按察审计 |
| **修复日期** | 2026-06-18 |
| **状态** | `✅ 已扫描，大部分为假阳性` |
| **本金估算** | ∼30min |
| **实际工时** | ∼5min |
| **实盘影响** | 🟢 死代码不影响功能，但增加维护负担、混淆代码阅读、浪费 CI 时间 |
| **触发场景** | 代码审查时被死代码干扰 |

**描述**：
前端 TD-029 已清理死代码，Python 后端从未运行过死代码检测工具。问题包括：
1. ❌ `vulture` 从未安装/运行
2. ❌ `src/utils/` 可能有未使用的辅助函数
3. ❌ DataCollector 中可能存在旧方法（重构 Provider 层后可能有未迁移的代码）
4. ❌ import 语句可能有未使用的导入

**修复方向**：
1. `pip install vulture && vulture src/` 首次扫描
2. 人工确认后删除确认的死代码
3. 可选：加 CI 步骤

# 📋 项目进度看板

> 一站式总览：已完成 ✓ 进行中 ⟳ 待办 ⬜
> **目标**：进来看一眼，就知道项目到哪了、下一步做什么。

---

## 快速统计

```
总 Python 测试数 │ 950 passed（not slow）
技术债务         │ 62 条总记 / 37 条已关闭 / 25 条开放
紧急指数         │ 4.0/10（DP-001 完成 + CI 绿）
当前阶段         │ 🔴 按 8 月底出国倒排 — P0 美股+YahooFinanceSource+FD-001+置信度+复盘看板，~3 周冲刺
前端进度         │ 全部 Tab 面板就绪（技术指标/资金流向/AI 辩论/信任度）+ 暗色主题打磨 + pnpm build ✅
后端桥接         │ market/stocks/debate/trust 四组路由全部完整实现 + TD-020 板块增强 + 技术指标 + 生产配置 ✅
数据源诚信        │ 全项目零造假 ✅ + Provider 抽象层 ✅ + 免费多源架构 ✅ + 生产配置 ✅
```

---

## 🟢 已完成（25 项）

### 核心基建
- ✅ **LLM 调用封装层** — `src/utils/llm.py`（TD-001 🔧 核心实现完成，测试待补）
- ✅ **LLMConfig 参数配置** — `LLMConfig` 数据类，temperature/max_tokens 可按 Agent 覆盖（TD-012 ✅ 已关闭）
- ✅ **通信协议** — `AgentMessage` + `EvidenceItem` + `MessageRouter`（20 tests）
- ✅ **配置加载** — Pydantic Settings（`src/utils/config.py`）
- ✅ **结构化日志** — `src/utils/logger.py`
- ✅ **费用追踪** — `src/utils/cost_tracker.py`（15 tests）
- ✅ **`ensure_dirs()` 目录创建函数已定义**（但未被调用 → TD-007）

### Agent 系统
- ✅ **BaseAgent 基类** + `AgentResult[Generic[T]]` 泛型化（TD-002 ✅ 已关闭）
- ✅ **AgentContext 辩论槽位** — 新增 `peer_outputs`/`current_round`/`target_audience`（TD-014 ✅ 已关闭）
- ✅ **教育小智 Agent** — RAG + LLM 问答（15 tests）
- ✅ **MasterAgent 通用化** — Skill 插件盘 + KB + LLM（24 tests ✅，含真实 DeepSeek API 集成测试）

### 知识 & 记忆
- ✅ **KnowledgeBase RAG** — n-gram TF 向量语义检索（15 tests）
- ✅ **知识库文件** — 30 篇（concepts 8 / indicators 7 / fundamentals 7 / masters 3 / strategies 5）
- ✅ **Master Skill 插件盘** — 7 位投资大师人格定义（30 tests）
- ✅ **知识检索双轨方案** — RAG + GREP 设计已定

### 基建 & 质量
- ✅ **CI 流水线** — GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13，TD-009 ✅ 已关闭）
- ✅ **质量保障体系 Module 12** — Hookify 9 条规则 + Post-tool hooks + 按察审计 8 条 CRITICAL 修复 ✅
- ✅ **Pydantic 字段约束** — StockQuote/KLine Field(ge=) 约束 + OHLC model_validator ✅
- ✅ **边界条件测试** — 数据模型负值验证 + LLM 错误路径 + 存储失败，+14 tests ✅
- ✅ **测试架构策略文档** — `docs/01-guides/TESTING_STRATEGY.md` + 学习卡片 #17 ✅
- ✅ **按察审计流程** — 三路探针全代码库扫描方法论，学习卡片 #16 ✅
- ✅ **Pyright 路径修复** — 移除硬编码 extraPaths（TD-011 ✅ 已关闭）
- ✅ **测试基座** — `conftest.py` + mock 工具 + VCR 录制（TD-004 🔧 核心完成）
- ✅ **全量测试 222 通过**
- ✅ **LangGraph 原型验证** — `tests/test_langgraph_prototype.py`（20 测试，TD-016 ✅ 已关闭）

### 回测引擎
- ✅ **P0 回测引擎基础** — BacktestEngine + PerformanceMetrics + 45 tests
- ✅ **回测→辩论桥接适配器** — TradePlan → TradeRecord + 20 tests

### 全链路验证
- ✅ **P0 端到端链路验证** — E2E 全链路测试（5 tests）+ 成本测算脚本 🆕
- ✅ **trader bug 修复** — `_format_vote_for_trader` 兼容 VoteSummary 对象 🆕

### 设计文档
- ✅ **ADR 体系** — 10 条架构决策记录（001-010）
- ✅ **用户行为镜子 Agent 设计** — `docs/99-archive/USER-BEHAVIOR-MIRROR.md`
- ✅ **前端 MVP 需求** — `docs/02-requirements/MVP_FRONTEND.md`
- ✅ **产品初版要求** — `docs/02-requirements/INITIAL_REQUIREMENTS.md`

### Phase 1 核心模块
- ✅ **数据采集层** `src/data/` — DataCollector + Cache + 5 个 Pydantic 模型（43 测试）
- ✅ **辩论编排器 MVP** `src/debate/` — LangGraph StateGraph 驱动（三节点：collect_data→master_round→aggregate，28 测试）
- ✅ **data → debate 链路可行性验证** — 编排器 MVP 全链路跑通，300 passed
- ✅ **data → debate 接驳** — format_market_brief 市场简报 + 行情过滤 + 结构化下传

### 项目治理
- ✅ **远程仓库迁移** — Gitee → GitHub，保留 Gitee 为备份远程
- ✅ **AI 自动化工作流程** — `docs/01-guides/WORKFLOW.md`
- ✅ **AI 会话交接文档** — 当前文档
- ✅ **技术债务管理系统** — 含分类 / 生命周期 / 仪表盘
- ✅ **工作日志索引** — `docs/04-changelog/logs/README.md`
- ✅ **子 Agent 灵算路由永久化** — Windows 用户 env + .bashrc 对齐，阻塞清零

### Phase 1 新增
- ✅ **命名空间记忆存储 MVP** — MemoryStore(ABC) + JsonFileStore + MemoryManager（29 测试）
- ✅ **D1 第二轮交叉审阅+反驳** — 大师互相看分析后反驳/补充（25 测试）
- ✅ **D3 独立评审 Agent** — IndependentReview + review_report 节点（23 测试）
- ✅ **M1 历史决策注入** — MemoryManager 接入辩论编排器（22 测试）
- ✅ **D2 强制输出方向** — Bullish/Bearish/Neutral + direction_distribution（31 测试）
- ✅ **D4 VoteSummary 结构化扩展** — 6 个评审修正字段（15 测试）

### 前端架构（Phase 1.5 🆕）
- ✅ **需求调研** — 6 大交易平台调研 + 2026 AI+交易趋势
- ✅ **产品定位** — "自上而下决策漏斗"（宏观→板块→产业链→个股）
- ✅ **视觉设计** — FRONTEND_VISION.md（Bloomberg 暗色 × TradingView 配色）
- ✅ **React 脚手架** — Next.js 16 + Tailwind v4 + shadcn/ui（47 文件）
- ✅ **模块文档** — 前端 5 篇 + FastAPI 桥接层 2 篇
- ✅ **FastAPI 桥接层编码** — market/stocks/debate/trust 四组路由（7 文件）
- ✅ **安装依赖 + 构建验证** — pnpm install + pnpm build 通过
- ✅ **前端接入真实 API** — 三页 mock 数据替换为 TanStack Query hooks，
  搜索 autocomplete，QueryClientProvider 全局集成
- ✅ **⚠️ 数据源造假全面清除** — 5 处硬编码删除，全项目零造假数据
- ✅ **Sprint 6: Lightweight Charts K 线真渲染** — CandlestickChart 组件封装 +
  KlineChart 自包含数据获取 + 成交量直方图 + 暗色主题
- ✅ **数据源深度审计** — 7 组代理并行调研 10+ 平台，产出 DATA_SOURCE_AUDIT.md
- ✅ **HealthStats 健康监控** — `/api/health/data-source` 实时监控数据源状态
- ✅ **DataSource Provider 抽象层** — `src/data/providers/` 7 文件，DataSource Protocol + 三源实现
- ✅ **AKShareSource 抽离** — 从 collector.py 移出到独立文件
- ✅ **ADataSource 接入** — adata 5 源融合自动切换（同花顺/东财/新浪/腾讯/百度），免费
- ✅ **ZzshareSource 接入** — Tushare 兼容零 Token 零积分数据源
- ✅ **FallbackSource 故障切换** — 按 endpoint 独立连续失败 N 次自动降级
- ✅ **DataCollector 重构** — 直调 akshare → 委托 DataSource，API 完全向后兼容
- ✅ **数据原则免费化修正** — Phase 2 从 Tushare Pro(500 元/年)改为零成本多源方案

---

## ⬜ 待办

### Phase 0 收尾（优先）

| 优先级 | 事项 | 预估 | 前置 |
|:------:|:-----|:----:|:----:|
| 🥇 | **LangGraph 最小原型验证**（TD-016） | ✅ 已完成 | 20 测试 + 222 全量通过 |
| 🥇 | **TD-013 Streaming 接口** — `astream() → AsyncIterator[str]` | ✅ 已完成 | 228 全量通过 |
| 🥇 | **TD-015 缓存策略解耦** — 不同 LLMConfig 独立缓存 | ✅ 已完成（与 TD-012 同步） | 5 测试验证 |
| 🥈 | **MasterAgent 输出结构化** — 纯文本 → 结构化评级+证据+置信度 | ✅ 已完成 | 228 全量通过 |
| 🥈 | **Phase 0 收尾修复** — config.py deprecation、.env.example | ✅ 已完成 | — |
| 🥈 | **A-4 GREP FormulaIndex** — 公式精确检索 | ~1d | — |
| 🥉 | **4 个空模块补模块文档** — debate/data/backtest/risk | ✅ 已完成 | — |
| 🥉 | **债务清理** — TD-003/005/006/007/008（低优先级，各 10min~1h） | ~3h | — |

### 空架子模块（白色目录，需从零实现）

```
无 — Phase 1 全部 8 模块已上线 ✅
```

### 辩论引擎增强（全部完成 ✅）

| 步骤 | 事项 | 前置 |
|:----:|:-----|:----:|
| 1️⃣ | **辩论编排器 LangGraph StateGraph** | ✅ 已完成（52 测试） |
| 2️⃣ | **D1 交叉审阅+三段式互评** | ✅ 已完成（25 测试，DP-002） |
| 3️⃣ | **D3 独立评审 Agent** | ✅ 已完成（23 测试） |
| 4️⃣ | **M1 历史决策注入** | ✅ 已完成（22 测试） |
| 5️⃣ | **D2 强制输出方向** | ✅ 已完成（31 测试） |
| 6️⃣ | **D4 VoteSummary 结构化扩展** | ✅ 已完成（15 测试） |
| 7️⃣ | **R1 三层风控辩论** | ✅ 已完成（26 测试） |
| 8️⃣ | **data → debate 接驳** | ✅ 已完成 |

### Phase 2+ 当前优先

### Phase R 当前优先（实盘加固）

| 优先级 | 事项 | 依赖 | 预估 |
|:------:|:-----|:----|:----:|
| 🔥 P0 | **TD-028 搜索防抖** — useDebounce(query, 300) | ✅ 已完成 | pnpm build ✅ |
| 🔥 P0 | **TD-029 前端死代码清理** — 布局目录/store/ECharts | ✅ 已完成 | pnpm build ✅ |
| 🔥 P0 | **TD-030 资金流向接入 Provider 层** | ✅ 已完成 | 75 tests ✅ |
| 🔥 P0 | **TD-031 辩论轮询停止条件** | ✅ 已完成 | pnpm build ✅ |
| 🔥 P0 | **TD-032 FallbackSource 恢复主源** | Provider 层就绪 | ~1h |
| 🔥 P0 | **QA 质量保障体系** — Hookify 规则 + Post-tool hooks + except:pass 修复 | 文档就绪 | ~2h |
| 🔴 P1 | **TD-036 backend 测试覆盖** | 全部就绪 | ~2d |
| ✅ P1 | **TD-038 密钥安全管理** | ✅ 已修复 — 迁移至 Windows Credential Manager | ~30min ✅ |
| ✅ P1 | **TD-039 API 速率限制** | ✅ 已修复 — slowapi 三层限流（run 6/min, status/result 30/min） | ~1h ✅ |
| 🟡 P1 | **测试架构提升** — 模块级 conftest 创建 + fixture 迁移 TODO | 全部就绪 | ~2h |
| 🟡 P1 | **契约测试** — tests/contract/ 目录 + data→debate 契约 | 全部就绪 | ~1h |
| 🟡 P2 | **TD-040 LLM Provider fallback** | utils 就绪 | ~1d |
| 🟡 P2 | **TD-041 数据新鲜度标注** | data + frontend | ~2h |
| 🟢 R4 | **📊 交易复盘看板 (Trade Retro Board)** — AI推荐记录 + 用户操作 + 实际盈亏 + 准确率统计 | data + debate + frontend | ~2d |
| 🟢 R4 | **AI推荐置信度量化** — 不确定性明确标注，胡说检测 | debate | ~2d |
| 🟢 R4 | **回测看板** — AI历史建议准确率可视化 | frontend | ~2d |

### Phase R+1 设计哲学落地（2026-06-22 决议）

> 完整蓝图见 [DESIGN_PHILOSOPHY.md](DESIGN_PHILOSOPHY.md)

| DP | 事项 | 牵头 | 预估 |
|:--:|:-----|:----|:----:|
| **DP-001** 🥇 | **模型瘦身** — 只留 DeepSeek，删 OpenAI/Anthropic，保留接口 | 基础设施部 | ✅ 已完成 |
| **DP-002** 🥇 | **D1 同侪审阅** — 从"反驳"改为"赞同+补充+异议"三段式 | 辩论引擎部 | ✅ 已完成 |
| **DP-003** 🥇 | **偏斜公示** — 每次辩论产出偏斜度统计 + 前端展示 | 辩论引擎部 + 前端部 | ✅ 已完成 |
| **DP-004** 🥇 | **TrustTracker 旋钮扩展** — 发言顺序/参与资格/置信度校准 | 辩论引擎部 | ~2h |
| **DP-005** 🥇 | **灵感官 Agent** — 高随机性反共识分析师 | AI Agent 架构部 | ~1h |
| **DP-006** 🥈 | **镜子反思** — 历史对比展示，辅助用户决策 | 辩论引擎部 + 记忆系统部 + 前端部 | ~3h |
| **DP-007** 🥈 | **信息隔离** — StateGraph 只传结构化摘要，裁剪 state | 辩论引擎部 | ~2h |

**关联更新**：
- ✅ **DP-001 完成** — 模型瘦身（只留 DeepSeek），`llm.py`/`config.py`/`credentials.py`/`cost_tracker.py` 清理
- ✅ **DP-002 完成** — D1 三段式互评，`RebuttalAnalysis` 字段重构 + prompt 升级 + 25 测试 + 6 文档
- ✅ **DP-003 完成** — BiasReport 模型 + `compute_bias_report()` + 22 测试 + 前端类型 + 学习卡片
- 🗑️ **TD-001 关闭** — 多 provider 分支精简（由 DP-001 实现）
- 🗑️ **TD-040 关闭** — 单 provider 策略，无需 fallback 链
- ✅ **scripts/check.py 创建** — 跨平台智能 CI 检查，按变更范围选测试，替代 `check.ps1` + 改善 `make check`

---

## 🔴 按 8 月底倒排的优先级（2026-06-23 重排）

> **关键外部截止日期**：8 月底出国前系统需实盘可用，9 月初留学申请提交。
> **核心约束**：爸妈用 A 股，你看 A 股 + 美股。两方互不影响。
> **原则**：8 月底必须能帮你赚生活费。可延后的功能一律延后，到国外安顿好再迭代。

### 美股数据源（新 P0）

| 优先级 | 事项 | 牵头 | 预估 |
|:------:|:-----|:------|:----:|
| 🔥 P0 | **YahooFinanceSource Provider** — 美股数据源接入（K 线+基本面+Provider Protocol 实现） | 数据管道部 | ~半天 |
| 🔥 P0 | **美股前端 Tab** — 市场切换 + 美股行情展示 | 前端部 | ~半天 |

### P0 必须做（命脉 — 约 2 周）

| 优先级 | 事项 | 牵头 | 预估 |
|:------:|:-----|:------|:----:|
| 🔥 P0 | **FD-001 基本面数据接入** — 财务指标模型+Provider 扩展+辩论注入+前端展示 | 数据管道部→辩论引擎部→后端 API 部→前端部 | ~2 天 |
| 🔥 P0 | **R4 置信度量化** — AI 建议附带明确置信度数字，不确定性显式标注 | 辩论引擎部 | ~2 天 |
| 🔥 P0 | **交易复盘看板（极简版）** — TradeRecord 记录 + AI推荐 vs 实际盈亏 | 后端 API 部 + 前端部 | ~2 天 |

### P1 最好做（提升赚钱概率 — 约 1 周）

| 优先级 | 事项 | 牵头 | 预估 |
|:------:|:-----|:------|:----:|
| 🔥 P1 | **DP-004 TrustTracker 旋钮扩展** — 发言顺序/参与资格/置信度校准 | 辩论引擎部 | ~2h |
| 🔥 P1 | **DP-005 灵感官 Agent** — 高随机性反共识分析师 | AI Agent 架构部 | ~1h |
| 🔥 P1 | **DP-007 信息隔离** — StateGraph 只传结构化摘要，裁剪 state | 辩论引擎部 | ~2h |
| 🟡 P1 | **美股新闻/财报事件接入** — 重大事件提醒 | 数据管道部 | ~1 天 |
| 🟡 P1 | **TD-041 数据新鲜度标注** — 采集时间戳+前端展示 | 数据管道部+前端部 | ~2h |
| 🟡 P1 | **TD-036 backend 测试覆盖** | 后端 API 部 | ~2 天 |

### P2 推迟到出国后

| 事项 | 原因 |
|:-----|:------|
| DP-006 镜子反思 | 美观但不致命 |
| UI Phase 2~4 完整反馈闭环（RC-004/005/006 等） | 到国外安顿后再迭代 |
| FD-003/004 供应链图谱 | 有更好，没有也能炒 |
| Phase 3 实盘下单 | 到国外先熟悉当地券商合规 |
| orchestrator.py 拆分 | 重构，不影响功能 |

### 8 月底冲刺路径

```
6/23                                         8/31
  │                                            │
  ├── P0 美股数据源 ─────── 1 天 ──→ ✅         │
  ├── P0 FD-001 基本面 ──── 2 天 ──→ ✅         │
  ├── P0 置信度量化 ─────── 2 天 ──→ ✅         │
  ├── P0 复盘看板(极简) ── 2 天 ──→ ✅         │
  ├── P1 DP-004/005/007 ── 1 天 ──→ ✅         │
  ├── P1 美股事件+新鲜度 ── 1 天 ──→ ✅         │
  ├── P1 TD-036 ────────── 2 天 ──→ (可选穿插)  │
  ├── 留白（适应出国+小仓位试水）─→ 5 周缓冲     │
  └── 9月初 → 简历提交 ──→ "实盘辅助使用中" ✅   │
```

---

### 🔁 UI 用户经验反馈闭环（2026-06-23 新增 — 架构第9层完整计划）

> **这是什么东西**：架构图第 9 层"用户经验反馈闭环"的完整实施计划。AI 推荐 → 用户操作 → 实际盈亏 → 学习 → 改进决策。
> **为什么它跨越 RC/DP/R4**：因为它用到了 RC 的结果回调引擎（公式层）、DP-006 的镜子展示（镜子层）、R4 的交易复盘看板（展示层），三者合在一起才叫"闭环"。
> **完整方案**：[USER_FEEDBACK_LOOP.md](../02-requirements/USER_FEEDBACK_LOOP.md)

**闭环全景**：

```
辩论 → AI推荐记录(已有) → 用户操作采集(RC-003) → 实际盈亏追踪(RC-003扩展)
                            ↓
                    ┌─── 公式层 ───┐
                    │ RC-002 M3-EXT│ 按板块信任度校准
                    │ RC-004 RP-TUNE│ 风险参数自适应
                    │ RC-005 CALIBRATE│ 置信度校准
                    │ RC-006 STRAT  │ 策略路由
                    └──────┬──────┘
                           ↓
                    ┌─── 镜子层 ───┐
                    │ RetroBoard   │ AI vs 用户 vs 盈亏 三列对比
                    │ 镜子 Agent   │ "你上次也这样，后来亏了"
                    └──────┬──────┘
                           ↓
                    ┌─── 学习层 ───┐
                    │ M2反思注入升级│ 用户行为偏差 → prompt
                    │ MemoryStore  │ 用户行为存储
                    └──────────────┘
```

**4 阶段实施**：

| 阶段 | 核心事项 | 牵头部门 | 预估 |
|:----:|:---------|:---------|:----:|
| **1 🥇** | **数据基础** — RC-001 引擎 + RC-003 用户操作采集 + 后端 API + 前端按钮 + RC-002 M3-EXT | 记忆系统部 + 后端 API 部 + 前端部 + 辩论引擎部 | ~11h |
| **2 🥇** | **自动调整** — RC-004 风险参数 + RC-005 置信度校准 + 实际盈亏追踪 + 回测集成 | 风控管理部 + 辩论引擎部 + 数据管道部 + 回测研究部 | ~5h |
| **3 🥈** | **可视化** — RetroBoard 后端/前端 + 镜子 Agent 数据基础 | 后端 API 部 + 前端部 + 数据管道部 | ~7h |
| **4 🥉** | **智能化** — 镜子 Agent DP-006 + M2 升级 + RC-006 策略路由 + Wrapped 报告 | 辩论引擎部 + 前端部 + AI Agent 架构部 | ~9h |

**为什么叫 UI（User Insight）不叫别的**：
- RC = 结果回调引擎（只做"公式调参"这一个维度）
- DP = 辩论哲学改进（镜子反思是展示层）
- FD = 基本面数据纵深
- **UI = 完整的用户经验反馈闭环**，把 RC 公式 + DP 镜子 + R4 看板 三合一

---

### 🔁 RC 结果回调轨道（2026-06-23 新增 — RC 是 UI 的"公式层"子集）

> **背景**：你的审视 — 系统当前只有 M3 `compute_weight_factor()` 一个"结果反馈"维度，且 `TrustTracker.record_outcome()` 从未被实际调用。缺少统一的结果参数回调引擎。
> **核心问题**：任何结果到达（市场结果/用户操作结果）时，大部分策略参数不响应——大师置信度不按板块校准、用户行为不追踪、风控参数不自适应。
> **完整方案**：新增 `src/callback/` 模块（ResultCallbackEngine）统一分发回调事件。

| RC | 事项 | 牵头 | 依赖 | 预估 |
|:--:|:-----|:----|:----|:----:|
| **RC-001** ✅ | **回调核心引擎** — `src/callback/` 模块（engine/registry/storage/models），中央事件分发器，注册/冷却/自动禁用/审计记录 | 记忆系统部 | 无 | 已完成 |
| **RC-002** ✅ | **M3-EXT 按板块信任度校准** — `AgentOutcome.sector` + 按板块胜率 + M3 回调 + `reflect_on_decision()` 实际结果 dispatch 已完成 | 辩论引擎部 | RC-001 | 已完成 |
| **RC-003** 🥇 | **UB-TRACK 用户行为追踪** — InvestmentDecision 模型 + UserBehaviorStore（JSONL）+ 操作理由分类 | 后端 API 部 + 前端部 | RC-001 | ~2h |
| **RC-004** 🥈 | **RP-TUNE 风险参数自适应** — 回测结果 → 自动调止损/仓位覆盖（基于 max_drawdown/win_rate） | 风控管理部 | RC-001 | ~2h |
| **RC-005** 🥈 | **CALIBRATE 置信度校准** — Brier score 过高时注入校准或降低置信度权重 | 辩论引擎部 | RC-002 | ~1h |
| **RC-006** 🥉 | **STRAT-ROUTE 策略路由** — 按市场条件追踪大师胜率，不及格自动降级 | 辩论引擎部 | RC-002 | ~2h |

**依赖关系**：
```
RC-001（核心引擎） → RC-002（M3 信任度修复）+ RC-003（用户行为）
                                    ↓
                     RC-004（风险参数）+ RC-005（置信度校准）+ RC-006（策略路由）
```

**为什么 RC 不是 FD 或 DP**：
- FD = 基本面数据纵深（财报/供应链）
- DP = 辩论流程哲学改进（偏斜公示/镜子反思）
- RC = **结果反馈机制**，闭环系统的"神经反射弧"——让结果自动引发参数调整

---

### 🔬 FD 基本面深度轨道（2026-06-23 新增 — 调研阶段）

> **背景**：你的洞察 — 投行机构 vs 散户的核心差距在财报纵深和供应链分析，而非分析模型。
> **完整调研报告**：见 [FUNDAMENTAL_RESEARCH.md](../02-requirements/FUNDAMENTAL_RESEARCH.md)
> **核心结论**：技术上可行。akshare 三大报表和财务指标接口够支撑 80% 需求，供应链图谱(L5)需额外工作。

| FD | 事项 | 牵头 | 依赖 | 预估 |
|:--:|:-----|:----|:----|:----:|
| **FD-001** 🥇 | **基本面数据接入** — 财务指标模型 + Provider 扩展 + 辩论注入 + 前端展示 | 数据管道部 → 辩论引擎部 → 后端 API 部 → 前端部 | 无（akshare 已有接口） | ~2 天 |
| **FD-002** 🥇 | **产业链修复** — 用真实行业分类替换当前伪产业链数据（涨幅排序造假） | 后端 API 部 + 前端部 | 现有 akshare 行业分类 | ~半天 |
| **FD-003** 🥈 | **供应链图谱调研** — 评估年报 PDF 解析前5大客户/供应商可行性 | 数据管道部 | FD-001 完成 | ~2h |
| **FD-004** 🥉 | **供应链图谱**（条件性）— NLP Pipeline 解析年报 → 可视化图谱 | 数据管道部 + 前端部 | FD-003 调研结论 | ~5-7 天 |

**关键里程碑**：
```
FD-001 ✅ 2 天完成
  ├─ 数据模型 + Provider → 数据层就绪
  ├─ 基本面占位符填充 → 辩论质量提升
  ├─ API 端点 → 后端可用
  └─ 财务 Tab → 用户可见
       ↓
FD-002 ✅ 半天完成（修复伪产业链 = 消除数据诚信债务）
       ↓
FD-003 ❓ 调研决策点（供应链图谱做不做？）
```

**为什么 FD 不是 DP（设计哲学）**：
- DP 系列 = 辩论流程本身的哲学改进（如偏斜公示、镜子反思）
- FD 系列 = **数据纵深**，是纯数据源的扩展，不影响辩论流程设计

### 📊 交易复盘表设计（R4 关键组件）

> **一句话**：每一次 AI 推荐了什么 → 用户做了什么 → 最后怎么样了 → 下次怎么改进。

**为什么需要它**

当前辩论系统输出"买入/卖出/持有"建议后，没有闭环跟踪：
- AI 推荐的股票后涨了还是跌了？没人知道
- 用户听了吗还是没听？没有记录
- AI 的置信度准不准？没有数据
- 哪个 Agent 历史准确率最高？没有统计

**表结构设计**

```
┌──────────┬───────┬────────┬──────┬──────┬──────┬──────────┬──────────┐
│ 日期     │ 代码   │ AI方向  │ 置信度 │ 用户  │ 盈亏  │ 是否正确  │ 偏差分析  │
│          │       │        │       │ 操作  │ (%)   │          │          │
├──────────┼───────┼────────┼───────┼──────┼──────┼──────────┼──────────┤
│ 06-17   │ 000001│ 买入   │ 82%   │ 买入 │ +3.2%│ ✅ 正确  │ AI判断准 │
│ 06-17   │ 600000│ 卖出   │ 65%   │ 持有 │ -1.5%│ ⚠️ 用户逆 │ AI信号偏弱│
│ 06-16   │ 300750│ 买入   │ 91%   │ 买入 │ -2.1%│ ❌ 错误  │ 市场突发利空│
└──────────┴───────┴────────┴───────┴──────┴──────┴──────────┴──────────┘
```

**产出物**

1. **数据模型** — `TradeRecord` Pydantic model（含 AI 推荐+用户操作+实际结果）
2. **后端 API** — `/api/retro/` 查询历史记录 + 汇总统计（准确率/胜率/平均盈亏）
3. **前端看板** — 表格组件 + 过滤器（日期/股票/结果状态）
4. **聚合卡片** — 今日 AI 准确率 / 7 日准确率 / 最佳 Agent / 最差 Agent
5. **自动记录** — 辩论触发时自动创建 TradeRecord，后端定时采集实际行情填充盈亏

**关联债务**
- TD-017 M2 反思闭环 — 交易复盘是反思闭环的输入数据
- TD-041 数据新鲜度标注 — 复盘需要标注"推荐时的数据新鲜度"以判断是否因数据延迟导致偏差

---

## 📊 模块完成度气温图

```
src/（Python 后端 — 全部就绪）
├── utils/        ████████████████████ 100%  ✅
├── core/         ████████████████████ 80%   ← TD-003/006
├── agents/       ████████████████████ 85%
├── memory/       ████████████████████ 100%  ✅
├── debate/       ████████████████████ 100%  ✅（222 测试）
├── data/         ████████████████████ 100%  ✅（43 测试）
├── trader/       ████████████████████ 100%  ✅
├── risk/         ██████████████████░░ 65%
└── backtest/     ██████████████████░░ 80%

frontend/（React + Next.js — 全部 Tab 就绪 ✅）
├── app/          ██████████████████░░ 85%   ✅ 四态分离 + 全局进度条 + 动态标题
├── components/   ████████████████████ 90%   ✅ 17 组件 + 全部 Tab 面板 + 暗色主题打磨
├── lib/          ████████████████████ 85%   ✅ 类型 + API + Hooks + QueryClientProvider
├── stores/       ██████░░░░░░░░░░░░░░ 30%   ✅ 基础状态管理
└── 配置           ████████████████████ 100%  ✅ pnpm build + tsc 零错误

backend/（FastAPI 桥接层 — 全部路由完整实现 ✅）
└── routers/      ████████████████████ 85%   ✅ market/stocks/debate/trust + TD-020 + 技术指标 + 生产配置

qa/（质量保障体系 — Hookify 规则 + Post-tool hooks）
├── SPEC          ██████░░░░░░░░░░░░░░ 15%   ⟳ 文档就绪，规则待实施
└── HOOKS         ██████░░░░░░░░░░░░░░ 15%   ⟳ 文档就绪
```

---

## 🔗 关联信息源

| 信息来源 | 位置 | 用途 |
|---------|------|------|
| 技术债务详情 | `docs/01-guides/debt/ROUTER.md` | 按部门路由的债务仪表盘 |
| 架构决策 | `docs/05-decisions/README.md` | 10 条 ADR 全文 |
| 🏢 部门体系 | `docs/06-departments/README.md` | 10 部门架构 + 数据流图 + 协作规程 |
| 工作日志 | `docs/04-changelog/logs/README.md` | 按日期回溯每会话工作内容 |
| 会话交接 | `docs/01-guides/HANDOVER.md` | 全局仪表盘 + 跨部门状态 |
| 镜子 Agent | `docs/99-archive/USER-BEHAVIOR-MIRROR.md` | 完整设计（9 章） |
| 前端视觉设计 | `docs/02-requirements/FRONTEND_VISION.md` | 调研 + 视觉方案 + 布局原型 |
| 前端规格文档 | `docs/03-modules/10-frontend/` | README+SPEC+ROUTING+COMPONENTS+API |
| FastAPI 桥接 | `docs/03-modules/11-fastapi-bridge/` | 桥接层 README+SPEC |
| 质量保障体系 | `docs/03-modules/12-quality-assurance/` | QA 系统 SPEC+HOOKS |
| 初版要求 | `docs/02-requirements/INITIAL_REQUIREMENTS.md` | 原始需求文档 |

---

## 📝 更新记录

| 日期 | 操作 |
|------|------|
| 2026-06-07 | 创建 — 聚合 AI 会话交接文档 §5 + 技术债务日志 + 路线图 memory 为一站式看板 |
| 2026-06-07 | TD-012 关闭 — LLMConfig 数据类 + 接口修改 + 17 测试，202 全量通过，紧急指数 1.2→0.9 |
| 2026-06-08 | TD-016 关闭 — LangGraph 原型验证通过，20 测试 + 222 全量通过，紧急指数 1.2→0.9 |
| 2026-06-08 | Phase 0 核心收尾 — TD-013/015/010 关闭 + MasterAgent 结构化输出，228 全量通过，紧急指数 0.9→0.7 |
| 2026-06-08 | Phase 1 数据采集层上线 — DataCollector + Cache + Models，43 测试，272 total |
| 2026-06-08 | 辩论编排器 MVP 上线 — LangGraph StateGraph + 28 测试，300 total |
| 2026-06-08 | 子 Agent 灵算路由永久化 — Windows User env + .bashrc 对齐，阻塞清零 |
| 2026-06-09 | data → debate 接驳实现 — format_market_brief + 行情过滤 + 结构化下传 |
| 2026-06-11 | 命名空间记忆存储架构设计 — ADR-011 + 设计文档 + 实现计划 + 流程规范 §1.3 竞品调研原则 |
| 2026-06-11 | 命名空间记忆存储 MVP 实现 — MemoryStore + JsonFileStore + MemoryManager，29 测试，331 passed |
| 2026-06-12 | 辩论深度进化全部完成 — D1+D2+D3+D4+M1 五模块上线，491 passed |
| 2026-06-14 | **P0 回测引擎基础上线** — BacktestEngine + 45 tests，空模块清零 🎉 |
| 2026-06-16 | **前端 MVP 架构设计完成** — 6 平台调研 + 产品定位 + React 脚手架 47 文件 + 模块文档 7 篇 |
| 2026-06-16 | **FastAPI 桥接层 + 前端构建验证** — 7 文件编码、pnpm build 通过 |
| 2026-06-16 | **前端接入真实 API** — 三页 mock→hooks 组件化，搜索 autocomplete |
| 2026-06-16 | **Sprint 6 K 线真渲染 + 数据源造假清除** — CandlestickChart + zero mock |
| 2026-06-16 | **数据源深度审计 + 健康监控** — DATA_SOURCE_AUDIT.md + `/api/health/data-source` |
| 2026-06-16 | **Provider 抽象层 + 免费多源架构** — DataSource Protocol + adata/zzshare/fallback 三源 + 数据原则免费化 |
| 2026-06-16 | **Batch 7 四项全完成** — 技术指标 Tab + TD-020 板块增强 + 生产配置 + 暗色主题打磨 |
| 2026-06-17 | **Phase R 实盘审计升级** — 项目标准升为"实盘产品级"，21 条 P0/P1 债务登记 + 7 条修复，742 tests，紧急指数 7.9/10 🛡️ |
| 2026-06-21 | **🏢 10 部门体系上线 + WORKFLOW 拆分** — 代码目录映射为 10 个部门（43 文件），债务按部门拆分，WORKFLOW 1047→50 行索引 + 4 份按阶段分流，HANDOVER 全面同步，全部架构引用清理 ✅ |
| 2026-06-23 | **DP-001 模型瘦身 + scripts/check.py 智能 CI 检查 + 全流程闭环** — 只留 DeepSeek，24 处文档统一指向 check.py，check.ps1 退役 |
| 2026-06-23 (2) | **DP-002 D1 三段式互评** — rebuttal→赞同+补充+异议，模型+prompt+测试+文档五同步 |
| 2026-06-23 (3) | **DP-003 偏斜公示** — BiasReport + compute_bias_report + 22 测试 + 前端类型 + 学习卡片
| 2026-06-23 (4) | **8月底倒排重优先级** — P0美股数据源+FD-001+置信度量化+复盘看板，P2出国后迭代，DESIGN_PHILOSOPHY追加「上下文通胀」节，ROADMAP/HANDOVER/记忆系统全面同步 |

> **如何更新**：每次会话结束时，把"已完成"和"变更状态"同步到此文件。
> 保持 `🟢 → 🔵 → ⬜` 三段式清晰可见。

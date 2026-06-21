# 📋 项目进度看板

> 一站式总览：已完成 ✓ 进行中 ⟳ 待办 ⬜
> **目标**：进来看一眼，就知道项目到哪了、下一步做什么。

---

## 快速统计

```
总 Python 测试数 │ 945 collected
技术债务         │ 61 条总记 / 35 条已关闭 / 26 条开放
紧急指数         │ 4.5/10（测试架构 + 债务按部门拆分完成）
当前阶段         │ Phase R 实盘加固 — 10 部门体系 + 文档同步
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
| 2️⃣ | **D1 交叉审阅+反驳** | ✅ 已完成（25 测试） |
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
| 🟡 P1 | **TD-039 API 速率限制** | backend 就绪 | ~1h |
| 🟡 P1 | **测试架构提升** — 模块级 conftest 创建 + fixture 迁移 TODO | 全部就绪 | ~2h |
| 🟡 P1 | **契约测试** — tests/contract/ 目录 + data→debate 契约 | 全部就绪 | ~1h |
| 🟡 P2 | **TD-040 LLM Provider fallback** | utils 就绪 | ~1d |
| 🟡 P2 | **TD-041 数据新鲜度标注** | data + frontend | ~2h |
| 🟢 R4 | **📊 交易复盘看板 (Trade Retro Board)** — AI推荐记录 + 用户操作 + 实际盈亏 + 准确率统计 | data + debate + frontend | ~2d |
| 🟢 R4 | **AI推荐置信度量化** — 不确定性明确标注，胡说检测 | debate | ~2d |
| 🟢 R4 | **回测看板** — AI历史建议准确率可视化 | frontend | ~2d |

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

> **如何更新**：每次会话结束时，把"已完成"和"变更状态"同步到此文件。
> 保持 `🟢 → 🔵 → ⬜` 三段式清晰可见。

# 🔄 AI 会话交接文档

> **用途**：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
> 
> **人类速查**：看 [HANDOVER_TIP.md](HANDOVER_TIP.md)（一页纸，扫一眼就够）。
> 
> **上下文耗尽自动交接**：当 AI 检测到上下文接近上限时（~20K tokens 剩余），
> 自动执行交接流程（更新日志+债务+看板+提交），不推进新工作。
> 详细流程见 CLAUDE.md「上下文耗尽自动交接」节。
> 
> **新 AI 启动流程（推荐用 Skill）：**
> 
> ```
> 执行 /resume-session Skill     ← 项目级 Skill，自动执行以下三层加载
>   ├── 记忆层自动注入           ← project-identity + architecture-decisions + current-state
>   ├── 交接文档 §2 + §5         ← 当前状态 + 下一步（约 3K token）
>   └── 最新工作日志             ← 前一次会话具体内容
> 
> 按需加载（用到才读）← 债务日志 / 设计文档 / 历史日志
> ```
> 
> 注意：不再逐个完整读取债务日志、自动化工作流程文档、CLAUDE.md（其核心内容已由 memory 层覆盖）。

---

## 1. 项目身份卡

| 字段 | 值 |
|------|-----|
| **项目名称** | litchi-head — 多智能体投资决策平台 |
| **当前阶段** | Phase 1 MVP 期（data/ + debate/ + memory/ 已上线，backtest/risk 待启动） |
| **技术栈** | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / akshare / FAISS |
| **代码位置** | `e:\litchi-head` |
| **远程仓库** | GitHub (`origin`)，Gitee (`gitee`) 作为备份 |
| **默认分支** | `main` |
| **CI** | GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13） |
| **最新提交** | `36c6671` — docs: 全量文档同步 + §3.1.1 文档同步审计清单 |

---

## 2. 当前会话状态（2026-06-16 — Sprint 6 K 线真渲染 + 数据源造假全面清除 ✅）

> **本次完成**：Batch 3 — Sprint 6 Lightweight Charts K 线真渲染（CandlestickChart + KlineChart 自包含数据获取 + 成交量直方图）。
> **⚠️ 数据源诚信审计**：发现并清除 5 处造假数据（debate-panel 硬编码大师分析 + market.py 板块硬编码 + chain-map 硬编码代码映射）。
> 全项目 frontend/ + backend/ **零造假数据** ✅。
> 前期完成：Batch 1 FastAPI 桥接层编码 + Batch 2 前端接入真实 API + 前端 MVP 架构设计（47 文件）。

### 完成内容

| 事项 | 状态 |
|:-----|:----:|
| 6 大交易平台调研（TV/Bloomberg/Robinhood/东方财富/同花顺/雪球） | ✅ |
| 2025-2026 AI+交易趋势调研（eToro Tori/Quant/同花顺问财） | ✅ |
| FRONTEND_VISION.md 视觉设计方案（Bloomberg暗色×TradingView配色） | ✅ |
| 前端模块文档 5 篇（README/SPEC/ROUTING/COMPONENTS/API） | ✅ |
| FastAPI 桥接层文档 2 篇（README/SPEC） | ✅ |
| 三页路由搭建（`/` → `/sector/[id]` → `/stock/[code]`） | ✅ |
| 暗色主题系统（CSS 变量 + Tailwind config + globals.css） | ✅ |
| 17 个功能组件 + 4 个布局组件（含 loading/empty/error 三态） | ✅ |
| TypeScript 类型 5 文件（覆盖 Pydantic 模型对应类型） | ✅ |
| API 层 5 文件 + 4 个 React Hooks | ✅ |
| Zustand 全局状态（面包屑 + 最近浏览） | ✅ |
| **总计 47 个前端文件 + 7 个文档 ** | ✅ |
| Python 后端 721 测试通过（不变） | ✅ |
| FastAPI 桥接层编码 — `backend/` 项目骨架 | ✅ |
| market.py 路由（指数/板块/板块详情/brief 4 endpoints） | ✅ |
| stocks.py 路由（搜索/个股/K 线/新闻/资金流向 5 endpoints） | ✅ |
| debate.py + trust.py 路由（辩论触发/状态/结果/信任度） | ✅ |
| 前端依赖安装 — `pnpm install` 通过 119 包 | ✅ |
| 前端构建验证 — `pnpm build` 三页路由全部通过 | ✅ |
| Pyright 类型检查 — backend/ 零错误 | ✅ |
| **Batch 2: 三页 mock → 真实 API 接入** | ✅ |
| **app/page.tsx 组件化** — hooks + MarketIndices/SectorRanking/MacroBrief + 搜索 autocomplete | ✅ |
| **sector/[id]/page.tsx 组件化** — hooks + SectorHeader/ChainMap/ChainAnalysis/StockList + 骨架屏 | ✅ |
| **stock/[code]/page.tsx 组件化** — hooks + QuoteCard/KlineChart/DebatePanel/NewsFeed + tab 面板 | ✅ |
| **QueryClientProvider** — TanStack Query 全局 providers.tsx | ✅ |
| **Batch 3: Sprint 6 K 线真渲染** — CandlestickChart + KlineChart 自包含 + 成交量直方图 | ✅ |
| **⚠️ 数据源造假清除** — debate-panel/market.py/chain-map 5 处硬编码全部删除 | ✅ |
| **全量数据源诚信审计** — frontend + backend 零造假数据 | ✅ |

### 重要：项目目录新结构

```
docs/
├── README.md                 ← 全文档路由表
├── 00-overview/              ← 🏠 总览（4 文件：OVERVIEW + GLOSSARY + TECH_STACK + ROADMAP）
├── 01-guides/                ← 📐 流程规范 + AI 路由
│   └── debt/                 ← 债务按类型拆分（7 文件）
├── 02-requirements/          ← 📋 产品需求
├── 03-modules/               ← 🔧 ★ 核心：11 个模块，各一个文件夹
│   ├── 01-data-collection/   ← README + SPEC + RESEARCH + ADR
│   ├── 02-debate-engine/     ← README + SPEC + RESEARCH + ADR
│   ├── ...（同格式，至 09-）
│   ├── 10-frontend/          ← 🆕 React + Next.js 前端（5 文档：README/SPEC/ROUTING/COMPONENTS/API）
│   └── 11-fastapi-bridge/    ← 🆕 FastAPI 桥接层（2 文档：README/SPEC）
├── 04-changelog/logs/        ← 📋 AI 工作日志（按日分文件夹）
├── 05-decisions/             ← 🏛️ 跨模块 ADR（6 文件）
└── 99-archive/               ← 🗄️ 归档（11 文件）
```

**核心思想**：一个功能 = 一个文件夹。开发辩论功能只看 `03-modules/02-debate-engine/`（SPEC 管规格，RESEARCH 管调研背景）。

### 关键变化

| 之前的问题 | 现在 |
|:-----------|:-----|
| 跨 4 个目录开发一个功能 | ✅ 一个模块文件夹解决所有 |
| 1143 行的债务日志线性膨胀 | ✅ 按类型拆为 7 个小文件 |
| 863 行的 ADR 一个大文件 | ✅ 拆为 10 个独立 ADR 文件 |
| 日志 4 级嵌套（39 文件遍历累） | ✅ 按日分文件夹，按日归档 |
| 中英混用目录名 | ✅ 全英文路径 |
| 旧/新内容混在一起 | ✅ 旧内容移入 `.legacy` 目录后清理 |
| SPEC 混杂调研笔记 → 1415 行 | ✅ SPE C精简为 641 行，调研拆入 RESEARCH.md |

### 尚未完成的

1. ~~**`01-guides/ROUTING.md`** — 上下文加载策略文件~~ ✅ 已完成（2026-06-15）
2. ~~**SPEC.md 内容精简** — 9 个模块 SPEC 精简为 641 行（原 1415 行，降 55%）~~ ✅
3. ~~**`.legacy` 目录删除** — 确认新结构没问题后可清理~~ ✅ 已清理（2026-06-15）
4. ~~**旧路径引用修复** — WORKFLOW/HANDOVER_TIP/看板/模块 RESEARCH 全量更新~~ ✅
5. ~~**回测→辩论桥接** — TradePlan → TradeRecord 适配器~~ ✅ 已完成（2026-06-16）
6. ~~**M3 信任度评分** — Agent 输出 vs 实际结果追踪~~ ✅ 已完成（2026-06-16）
7. ~~**前端 MVP 开发** — React + Next.js 脚手架已搭建~~ ✅ 依赖安装+构建验证通过
8. ~~**FastAPI 桥接层实现** — 接口设计已定，需要编写 Python API 路由~~ ✅ 已编码（7 文件）
9. 🆕 ~~**前端连接后端 API** — 替换模拟数据为真实 FastAPI 接口调用~~ ✅
10. 🆕 ~~**后端 trust.py 和 stocks/capital-flow** — 占位路由需要完整实现~~ ⬜ 待继续
11. 🆕 ~~**Lightweight Charts K 线集成** — 替换模拟 K 线为真渲染~~ ✅
12. 🆕 **后端数据增强** — 移除造假后 heat/chain_map/ai_analysis 需要接入真实数据源（TD-020）
13. 🆕 **技术指标/资金流向/信任度 tab 面板** — 3 个占位 tab 等待实现

### 当前 Git 状态

```
最新提交: 36c6671 — docs: 全量文档同步 + §3.1.1 文档同步审计清单
工作区: 有 frontend/ + docs/ 新文件未提交
```

### 测试覆盖

| 测试文件 | 测试数 |
|---------|:------:|
| `tests/test_debate_*.py` | 199（含 54 M3 + 10 M4） |
| `tests/test_risk_*.py` | 26 |
| `tests/test_trader_*.py` | 20 |
| `tests/test_backtest_*.py` | 65（含 20 桥接） |
| `tests/test_e2e_full_pipeline.py` | 5 |
| `tests/test_memory_*.py` | 29 |
| `tests/test_agents_*.py` | 58+4 skip |
| `tests/test_trader_bridge.py` | 14 |
| `tests/test_debate_trust.py` | 54+10 |
| 其他 | 78 |
| **Python 全量** | **721 passed** |
| `frontend/` | 🆕 React 前端，暂无测试（待 Phase 2） |
| `backend/` | 🆕 FastAPI 桥接层，暂无专用测试（Pyright 零错误） |

---

## 3. 代码结构现状

### 3.1 模块完成度

```
已就绪模块（✅）：
  src/utils/       — llm / config / cost_tracker / logger / complexity_router（100%）
  src/core/        — protocol（AgentMessage + MessageRouter）
  src/agents/      — base / xiao_zhi / master_agent（全部通用化）
  src/data/        — models / cache / collector（Phase 1 ✅）
  src/debate/      — models / orchestrator / analysts（D1+D2+D3+D4+M1+R1 全部完成 ✅）
  src/risk/        — models / profiles / orchestrator（R1 三层风控辩论 ✅）
  src/trader/      — models / profiles / orchestrator（T1 交易员层 ✅）
  src/backtest/    — models / engine / metrics（P0 回测引擎基础 ✅）
  src/memory/      — knowledge_base / skill_disk / store / manager（MVP ✅）

🆕 新建模块（已编码）：
  frontend/        — React + Next.js 16 + Tailwind v4 + shadcn/ui（47 文件，pnpm build 通过 ✅）
  backend/         — FastAPI 桥接层（7 文件，market/stocks/debate/trust 四组路由 ✅）

空架子模块（⬜）：（无）
```

### 3.2 技术债务一览

```
紧急指数：1.4/10（↑ 0.5，因新增 S1 债务 TD-017 反思闭环缺失）

✅ 已关闭（9 条）：
  TD-002 / TD-009 / TD-010 / TD-011 / TD-012 / TD-013 / TD-014 / TD-015 / TD-016

🔧 修复中（2 条）：
  TD-001  LLM 封装层（惰性导入优化完成，模型路由待补）
  TD-004  测试基座（537 tests，backtest 待补）

📋 已确认（10 条）：
  S1 🟠 TD-017 反思闭环缺失（竞品最大结构性差距，M2 优先修复）
  S2 🟡 TD-003 MessageRouter 内存存储 / TD-005 双配置源
  S2 🟡 TD-018 编排层成本优化（15次调用，竞品1.5-2倍）
  S2 🟡 TD-019 单LLM提供商依赖（竞品7-13种）
  S3 🟢 TD-006 EvidenceItem 无校验 / TD-007 ensure_dirs / TD-008 价格硬编码

开放债务：12 条（TD-017/018/019 🆕）
```

---

## 4. 关键设计决策

### 4.1 产品定位：手榴弹

```
机构有原子弹（10 个 CFA + Bloomberg + 自研量化系统）
散户只有手榴弹——但手榴弹拉开环扔出去就能炸

产品使命：散户问一句话 → 15 秒拿到结构化的多维决策信息
         10 秒内能看懂、能决策、能行动
```

### 4.2 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` / `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误
4. **四同步原则** — 代码 + 测试 + 文档 + 债务日志同步更新
5. **Agent 输出结构化** — 含评分/证据/置信度，非纯文本
6. **LLMService 调用走 `LLMConfig`** — 不硬编码 temperature/max_tokens

### 4.3 AgentResult 泛型化后的用法

```python
# 向后兼容（已有代码不变）
result = AgentResult(data={"key": "val"})

# 新写法（类型化输出，Pyright 可静态校验）
class NewsOutput(BaseModel):
    summary: str
    sentiment: str

result = AgentResult[NewsOutput](data=NewsOutput(...))
result.data.summary  # Pyright 可校验 ✅
```

### 4.4 data 模块使用示例

```python
from src.data import DataCollector

collector = DataCollector()

# 全部 A 股（缓存 1h）
stocks = collector.get_all_stocks()

# 实时行情（缓存 30s）
quotes = collector.get_realtime_quotes()

# 个股 K 线（缓存 5min）
klines = collector.get_klines("000001", period="daily")
```

---

## 5. 下一步优先级（2026-06-16 更新 — Sprint 6 K 线真渲染 + 数据源造假清除 ✅）

> **本次完成**：
> - Sprint 6: Lightweight Charts K 线真渲染（CandlestickChart 组件 + KlineChart 自包含 + 成交量直方图）
> - ⚠️ 数据源造假全面清除：5 处硬编码删除，frontend + backend 零造假数据 ✅
>
> 建议下一步：**后端占位路由完善 + 板块数据增强层**。

### 🥇 下一步

| 优先级 | 说明 | 涉及范围 | 工作量 |
|:------:|:-----|:--------:|:-----:|
| 🥇 **后端完善** | trust.py 信任度路由 / capital-flow 资金流向路由完整实现 | `backend/` | ~0.5d |
| 🥇 **TD-020** | 板块数据增强层 — heat/chain_map/ai_analysis 接入真实数据源 | `backend/routers/market.py` | ~0.5d |
| 🥈 **Tab 面板** | 技术指标/资金流向/信任度 3 个占位 tab 实现 | `frontend/` | ~1d |
| 🟢 后续 | **暗色主题打磨** — 加载态、骨架屏、错误态等体验优化 | 全局 | ~0.5d |

### 关键架构决策（新会话必读）

1. **前端用 React + Next.js 16，不用 Streamlit** — 用户要求高级感，Streamlit 无法达到
2. **Python 后端不动，前面加 FastAPI 桥接层** — 现有 akshare/LangGraph 全部保留
3. **三页路由**：`/`（宏观总览）→ `/sector/[id]`（产业链分析）→ `/stock/[code]`（个股决策）
4. **数据源不造假** — akshare 提供什么就返回什么，空就是空，未实现就是不实现 ✅
5. **详细文档在** `docs/03-modules/10-frontend/`（5 篇） + `docs/03-modules/11-fastapi-bridge/`（2 篇）

### 下个会话推荐启动顺序

```
1. /resume-session 恢复上下文
2. cd e:/litchi-head && uvicorn backend.main:app --reload --port 8000   ← 从项目根启动 FastAPI
3. cd frontend && pnpm dev                               ← 启动前端看效果
4. 后端 trust.py + capital-flow 路由完善                   ← 后端占位补全
5. 板块数据增强层（TD-020）                                ← 接入真实数据源
6. Tab 面板实现（技术指标/资金流向/信任度）                  ← 页面功能补全
```

> **最后更新**：2026-06-16（Sprint 6 K 线真渲染 + 数据源造假清除 — CandlestickChart + 诚信审计 ✅） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

---

## 6. 工作流优化建议

> 2026-06-08 第 4 次会话复盘产出。

### 6.1 已知效率问题与修复

| 问题 | 影响 | 修复方案 | 状态 |
|:----|:----:|:---------|:----:|
| **质量修复循环过多** | 每次写代码后 3-6 轮 Ruff/Pyright 修复 | 配置 PostWrite hook 自动 `ruff check --fix` | ✅ 已配置 |
| **pandas 类型反复** | `row["code"]` 被推断为 Series，Pyright 报错 | 必须 `str(row["col"])` 显式转换 | ✅ 已记录 |
| **Agent API 不兼容 DeepSeek** | planner/Explore 代理因 reasoning_effort 失败 | 降级到 Plan Mode 并记入 memory | ✅ 已记录 |
| **reasoning_effort 已接入** | `LLMConfig.reasoning_effort` 此前未接线 | `_build_llm()` 已接入，仅对 `deepseek-reasoner` 生效 | ✅ TD-014 |
| **复杂度感知路由** | 简单问题也用推理模型导致慢 | `src/utils/complexity_router.py` 自动路由到 chat/reasoner | ✅ TD-014 |
| **集成测试 skip 检测反复** | 代理环境特殊 | 使用 HTTP urlopen 检测，按数据源独立标记 | ✅ 已解决 |
| **Windows torch access violation** | transformers 链导入 torch 导致 crash | `__init__.py` 惰性导入 DebateOrchestrator + reflection.py llm_service | ✅ 已解 |

### 6.2 已知 pandas 类型模式（必须遵守）

akshare 返回 `pd.DataFrame`，`df.iterrows()` 的 `row["col"]` 被 Pyright 推断为 `Series | ndarray | Any`。

**必须写**：
```python
# ❌ 错误：Pyright 报 type mismatch
StockInfo(code=row["code"], name=row["name"])

# ✅ 正确：显式转换
StockInfo(code=str(row["code"]), name=str(row["name"]))
StockQuote(price=float(row["最新价"]), volume=int(row["成交量"]))
```

### 6.3 会话草稿模式（推荐工作习惯）

用一个 scratchpad 文件或内存列表，每完成一个 todo item 追加一行，最终日志直接以此为基础编写。

```markdown
# 每次完成一个 todo，追加一行：
- [x] 步骤 ①: models.py + 17 测试
- [x] 步骤 ②: cache.py + 11 测试
...
# 会话结束 = 日志骨架已就绪
```

---

## 7. 常见问答

**Q：AgentResult 改成 BaseModel 后，现有测试需要改吗？**
A：不需要。`data: dict | T = Field(default_factory=dict)` 设计确保所有现有代码向后兼容。

**Q：为什么 AgentContext 还是 dataclass？**
A：模块内部传递数据，不跨模块序列化。如有跨模块序列化需求再改。

**Q：集成测试为什么跳过？**
A：代理环境屏蔽了东方财富 API（push2.eastmoney.com），`urllib.request.urlopen(..., timeout=3)` 检测失败时自动跳过。CI 环境会正常跑通。

---

## 8. 文件索引

### 核心代码

| 文件 | 说明 |
|------|------|
| `src/agents/base.py` | Agent 基类 + AgentContext + AgentResult[Generic[T]] |
| `src/agents/xiao_zhi.py` | 教育小智 Agent（RAG + LLM 问答） |
| `src/agents/master_agent.py` | MasterAgent 通用化（Skill 插件盘 + KB + LLM + 结构化输出） |
| `src/memory/skill_disk.py` | Master Skill 插件盘（7 位投资大师人格定义） |
| `src/memory/knowledge_base.py` | 知识库 RAG（n-gram TF 向量语义检索） |
| `src/memory/store.py` | MemoryStore(ABC) + JsonFileStore |
| `src/memory/manager.py` | MemoryManager 语义化接口 |
| `src/core/protocol.py` | 通信协议（AgentMessage / EvidenceItem / MessageRouter） |
| `src/utils/llm.py` | LLM 调用封装（DeepSeek/OpenAI 统一接口 + Streaming + LLMConfig） |
| `src/utils/config.py` | 配置加载（Pydantic Settings） |
| `src/utils/cost_tracker.py` | 费用追踪 + 持久化 |
| `src/utils/logger.py` | 结构化日志 |
| `src/data/models.py` | 7 个 Pydantic 数据契约（含 MarketBrief/BriefSection） |
| `src/data/cache.py` | DataCache 内存 TTL 缓存 |
| `src/data/collector.py` | DataCollector 封装 akshare 6 类数据 |
| `src/debate/models.py` | 辩论数据模型（含 D1-D4+M1-M4+R1+T1 扩展） |
| `src/debate/orchestrator.py` | LangGraph 辩论编排器（9层链路 + TrustTracker） |
| `src/debate/reflection.py` | M2 反思闭环（Record→Compare→Reflect→Inject） |
| `src/backtest/models.py` 🆕 | 回测数据模型（BacktestConfig/TradeRecord/BacktestReport） |
| `src/backtest/engine.py` 🆕 | BacktestEngine 回测模拟引擎 |
| `src/backtest/metrics.py` 🆕 | 绩效指标计算（夏普/回撤/胜率/盈亏比/CAGR） |

### 辩论模块测试

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_debate_orchestrator.py` | 52→17（重构精简） | 辩论编排器 MVP |
| `tests/test_debate_d1_cross_review.py` | 25 | D1 交叉审阅+反驳 |
| `tests/test_debate_d2_direction_constraint.py` | 31 | D2 强制输出方向 |
| `tests/test_debate_d3_independent_review.py` | 23 | D3 独立评审 |
| `tests/test_debate_m1_history_injection.py` | 22 | M1 历史决策注入 |
| `tests/test_debate_d4_vote_summary_extension.py` | 15 | D4 VoteSummary 扩展 |
| `tests/test_debate_trust.py` 🆕 | 54 | M3 信任度评分 |
| `tests/test_debate_m4_dynamic_weight.py` 🆕 | 10 | M4 动态权重 |

### 数据模块测试

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_data_models.py` | 22 | Pydantic 模型验证 |
| `tests/test_data_cache.py` | 12 | DataCache TTL |
| `tests/test_data_collector.py` | 26 | DataCollector + C1 简报分区 |

### 关键调研文档

| 文档 | 说明 |
|------|------|
| `docs/00-overview/OVERVIEW.md` | 项目概览（新读者起点） |
| `docs/03-modules/` | 全部功能模块规格 |
| `docs/03-modules/02-debate-engine/SPEC.md` | 辩论引擎规格（含 TradingAgents 源码分析） |
| `docs/01-guides/debt/ROUTER.md` | 技术债务路由索引 |
| `docs/05-decisions/README.md` | 跨模块 ADR 索引 |

---

> **最后更新**：2026-06-15（docs 重组全部完成 — 后续更新看 §2 行末） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

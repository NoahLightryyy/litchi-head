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
| **最新提交** | `e848d45` — fix: TD-036 backend 全路由测试覆盖（77 测试） |

---

## 2. 当前会话状态（2026-06-18 — TD-058 剩余 4 模块 conftest ✅）

> **本次完成**：TD-058 剩余 4 模块 conftest — agents/data/memory/utils 全部完成。
> 创建 conftest 4 个，迁移 11 个扁平测试文件到模块目录，Fixture 去重。
> **全量 941 tests collected, 全部通过** ✅
> **前期完成**：TD-036 backend 全路由测试覆盖（77 测试，17 端点）。
> TD-032 FallbackSource 恢复主源 + TD-058 debate conftest 示范 + TD-059 契约测试。
> 全代码库测试架构系统审查 + 测试策略文档 + 学习卡片。
> QA 质量保障体系 Module 12 + Phase R P0 修复（TD-028~031）+ Batch 6 + Batch Loop 等。
> **Batch 5~1** 同上。

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
| **Batch 4: 数据源深度审计** — 覆盖 10+ 平台，产出 DATA_SOURCE_AUDIT.md | ✅ |
| **HealthStats 监控** — 每个 endpoint 记录成功率/延迟/错误 | ✅ |
| **`/api/health/data-source`** — 实时数据源健康暴露端点 | ✅ |
| **Batch 5: DataSource Provider 抽象层** — `src/data/providers/` 全新模块（7 文件） | ✅ |
| **AKShareSource 抽离** — 从 `collector.py` 移出到 `providers/akshare.py` | ✅ |
| **ADataSource** — adata 5 源融合（同花顺/东财/新浪/腾讯/百度）自动切换，免费 | ✅ |
| **ZzshareSource** — Tushare 兼容零 Token 零积分数据源 | ✅ |
| **FallbackSource** — 按 endpoint 独立故障自动切换（连续 N 次失败降级） | ✅ |
| **DataCollector 重构** — 直调 akshare → 委托 DataSource，API 完全向后兼容 | ✅ |
| **数据原则修正** — DATA_SOURCE_AUDIT.md Phase2 从 Tushare Pro(500元/年)改为零成本方案 | ✅ |
| **Provider 层测试** — 19 个单元测试（协议验证 + FallbackSource 全覆盖） | ✅ |
| **全量 719+19 = 738 passed, Pyright 零错误** | ✅ |
| **Batch 6: 后端路由完善 + Tab 面板实现** | ✅ |
| **capital-flow 资金流向路由** — _detect_market + CapitalFlowItem + akshare fund_flow 接入 | ✅ |
| **trust.py 信任度路由** — TrustTracker 接入 + report/leaderboard 2 endpoints | ✅ |
| **CapitalFlowPanel 组件** — 汇总卡片 + 明细列表 | ✅ |
| **TrustChart 接入 stock 页 trust tab** | ✅ |
| **Batch Loop 四方向全完成** | ✅ |
| **技术指标 Tab** — backend/indicators.py 纯 Python MA/RSI/MACD/布林带 + TechnicalIndicatorsPanel | ✅ |
| **TD-020 板块数据增强** — market.py 重写：heat/chain_map/ai_analysis/ai_rating 全部真实数据 | ✅ |
| **数据源生产配置** — backend/config.py + DataCollector.default_source + adata 2.9.5 | ✅ |
| **暗色主题打磨** — 导航高亮/全局进度条/动态标题/错误态重试/Server Component 架构 | ✅ |
| **Phase R 实盘审计** — 项目标准升级 → 实盘产品级 | ✅ |
| **Phase R 致命缺陷修复** — 21 处 except:pass→logger / HTTP 状态码修正 / async_utils 超时 / Error Boundary / 骨架屏四态 / 离线横幅 | ✅ |
| **学习卡片系统** — docs/learning/ 7 张卡片（01-Pydantic ~ 07-类型注解） | ✅ |
| **全量 742 tests passed, Pyright 零错误** | ✅ |
| **TD-028 搜索防抖** — `useDebounce(query, 300)` + useStockSearch 接入 | ✅ |
| **TD-029 死代码清理** — 删 layout(5文件)/stores(2文件)/hot-news + echarts/zustand 依赖 | ✅ |
| **TD-030 资金流向 Provider 层贯通** — CapitalFlowItem→Protocol→三源→Fallback→DataCollector→路由 | ✅ |
| **TD-031 辩论轮询兜底** — useRef 计数 + 最大 60 次（~120s）自动停 | ✅ |
| **Module 12: QA 质量保障体系上线** — 7 条 Hookify 规则 + Post-tool hooks + except:pass 修复 | ✅ |

| **按察审计 Code Quality Sweep — 8 处 CRITICAL 静默异常修复** | ✅ |
| **Phase 1: 修复静默吞异常** — orchestrator(5处) + risk(2处) + reflection(2处) + trust(3处) + engine(1处) + collector(7处) + conftest(1处) | ✅ |
| **Phase 2: 债务登记** — CLOSED.md +8条(TD-042~049) / TESTING.md +3条(TD-050~052) / IMPLEMENTATION.md +2条(TD-054~055) | ✅ |
| **Phase 3: 边界条件测试** — 数据模型Field约束+Pydantic验证器 + XiaoZhi LLM错误处理后+3测试 + MemoryManager存储失败测试+3 | ✅ |
| **Pydantic 字段约束** — StockQuote/KLine Field(ge=0.0) + KLine model_validator(OHLC合理性) | ✅ |
| **XiaoZhiAgent LLM 错误防护** — try/except 封装 LLM 调用，超时/网络错误优雅降级 | ✅ |
| **Phase 4: Hookify 规则 R008/R009** — logger-exception-blocker + type-ignore-comment | ✅ |
| **全量 756 tests passed**（+14 边界测试），Pyright 零错误 | ✅ |

| **测试架构审查 — 文档化 + 债务登记** | ✅ |
| **测试策略文档** — `docs/01-guides/TESTING_STRATEGY.md` 测试金字塔/模块自治/契约测试约定 | ✅ |
| **学习卡片 #17** — 测试架构与模块自治 | ✅ |
| **债务 TD-058~060** — 模块级 conftest 缺失/无契约测试/无测试文档 | ✅ |
| **当前全量 868 tests collected**（含 +4 契约测试），Pyright src/ 2 errors，backend/ 0 errors | ✅ |
| | | |
| **第三轮：Phase R 三项债务修复** | ✅ |
| **TD-032 FallbackSource 恢复主源** — 备用模式每次先尝试主源，成功自动切回 | ✅ |
| **TD-058 模块级 conftest（debate 示范）** — 迁移 10 文件到 tests/test_debate/ + conftest.py fixture 去重 | ✅ |
| **TD-059 契约测试 data→debate** — tests/contract/ + StockQuote/KLine/NewsItem JSON roundtrip + format_market_brief | ✅ |
| | | |
| **第四轮：TD-036 backend 全路由测试覆盖** | ✅ |
| **tests/test_backend/conftest.py** — TestClient + MockCollector + DataFrame 工厂 | ✅ |
| **test_market.py** — 6 端点 + 5 辅助函数（52 测试） | ✅ |
| **test_stocks.py** — 6 端点（15 测试） | ✅ |
| **test_debate.py** — 3 端点（9 测试） | ✅ |
| **test_trust.py** — 2 端点 + 映射逻辑（11 测试） | ✅ |
| **全量 941 tests passed**（+77 backend 测试），Pyright 零错误 | ✅ |
| | | |
| **第五轮：TD-058 剩余 4 模块 conftest 🆕** | ✅ |
| **tests/test_agents/conftest.py** — ctx/buffet_lite/munger_lite/make_analysis | ✅ |
| **tests/test_data/conftest.py** — MockDataSource + MockFailingDataSource + collector 系列 fixture | ✅ |
| **tests/test_memory/conftest.py** — kb_with_temp_dir + 知识文件 fixture | ✅ |
| **tests/test_utils/conftest.py** — 模式占位 | ✅ |
| **Fixture 去重 + 11 文件迁移，全量 941 tests 零回归** | ✅ |
| | | |
| **第五轮：TD-058 剩余 4 模块 conftest 🆕** | ✅ |
| **tests/test_agents/conftest.py** — 提取 ctx/buffet_lite/munger_lite/make_analysis fixture | ✅ |
| **tests/test_data/conftest.py** — 共享 MockDataSource + collector 系列 fixture，迁移 5 扁平文件 | ✅ |
| **tests/test_memory/conftest.py** — 共享 kb_with_temp_dir + 知识文件 fixture，迁移 4 文件 | ✅ |
| **tests/test_utils/conftest.py** — 模式占位，迁移 2 文件 | ✅ |
| **Fixture 去重** — `ctx`/`MockDataSource`/`MockFailingDataSource`/`kb_with_temp_dir` 等不再重复定义 | ✅ |
| **全量 941 tests passed（零回归）** | ✅ |

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

Phase R 实盘加固（P0/P1 优先）：

| 优先级 | 事项 | 预估 | 前置 |
|:------:|:-----|:----:|:----:|
| ~~🔥~~ | ~~**TD-032 FallbackSource 永不恢复主源**~~ | ~~~1h~~ | ~~—~~ |
| | **✅ TD-032 已修复** — 备用模式每次先尝试主源，成功自动切回 | | |
| 🔴 | **TD-036 backend 路由测试覆盖** — 5/6 文件零测试（indicators 已补） | ~2d | — |
| 🔴 | **TD-038 .env 明文 API 密钥** | ~30min | — |
| 🟡 | **TD-058 模块级 conftest 缺失** — debate 示范完成 ✅，4 模块待继续 | ~1.5h | 测试策略文档 ✅ |
| 🟡 | ~~**TD-059 无契约测试**~~ | ~~~1h~~ | |
| | **✅ TD-059 已修复** — `tests/contract/test_data_to_debate.py` 4 项契约测试 | | |
| 🟡 | **TD-039 API 速率限制** — 特别 debate/run | ~1h | — |
| 🟡 | **TD-040 LLM Provider fallback 链** | ~1d | — |
| 🟡 | **TD-041 数据新鲜度标注** | ~2h | — |

### 当前 Git 状态

```
最新提交: e848d45 — fix: TD-036 backend 全路由测试覆盖（77 测试）
工作区: 干净 — TD-036 已关闭
```

### 测试覆盖

| 测试文件 | 测试数 |
|---------|:------:|
| `tests/test_debate/*.py` | 235（✅ 已迁移到模块目录） |
| `tests/test_risk_*.py` | 26 |
| `tests/test_trader_*.py` | 20 |
| `tests/test_backtest_*.py` | 65（含 20 桥接） |
| `tests/test_e2e_full_pipeline.py` | 5 |
| `tests/test_memory_*.py` | 29 |
| `tests/test_agents_*.py` | 58+4 skip |
| `tests/test_trader_bridge.py` | 14 |
| `tests/test_debate_trust.py` | 54+10 |
| Provider 层测试 | 19 |
| `tests/test_backend_indicators.py` | 43 |
| `tests/test_backend/*.py` 🆕 | 77（路由全量覆盖 ✅） |
| 其他 | 80 |
| 边界条件测试（14 新增） | 14 |
| **Python 全量** | **941 collected** |

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
紧急指数：6.0/10（⬇️ 3 处 except:pass 已修复 + QA 防线就位）

✅ 已关闭（19 条）：
  原有 9 条：TD-002 / TD-009 / TD-010 / TD-011 / TD-012 / TD-013 / TD-014 / TD-015 / TD-016
  新增 10 条：TD-020 / TD-021 / TD-022 / TD-023 / TD-024 / TD-025 / TD-026 / TD-027 / QA系统(except:pass清零) / **TD-036**

🔧 修复中（2 条）：
  TD-001  LLM 封装层（惰性导入优化完成，模型路由待补）
  TD-004  测试基座（核心完成，backtest 待补）

📋 待评估（18 条）：
  P1 🔴 TD-038 .env 明文密钥 / TD-039 无速率限制
  P1 🟡 TD-003 MessageRouter 内存存储 / TD-005 双配置源 / TD-006 无校验
  P1 🟡 TD-007 ensure_dirs / TD-008 价格硬编码 / TD-017 反思闭环缺失
  P1 🟡 TD-018 编排层成本优化 / TD-019 单 LLM 依赖 / TD-033 数组变异
  P2 🟢 TD-034 条件逻辑错误 / TD-037 边界条件测试 / TD-040 LLM fallback / TD-041 新鲜度标注

  新增 QA: Pydantic 字段约束补齐 / CI 门禁升级（coverage+bandit）/ 文档同步检测

开放债务：28 条（⬇️ TD-036 已关闭）
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

## 5. 下一步优先级（2026-06-18 — TD-058 剩余 4 模块 conftest ✅）

> **本次完成**：
> - 🔴 **TD-058 剩余 4 模块 conftest** — agents/data/memory/utils 全部完成
> - `tests/test_agents/conftest.py` — 提取 ctx/buffet_lite/munger_lite/make_analysis
> - `tests/test_data/conftest.py` — 共享 MockDataSource + collector 系列 fixture
> - `tests/test_memory/conftest.py` — 共享 kb_with_temp_dir + 知识文件 fixture
> - `tests/test_utils/conftest.py` — 模式占位
> - 迁移 11 个扁平测试文件到模块目录，Fixture 去重
> - 同步更新债务日志（TD-058 → CLOSED ✅）+ HANDOVER.md
>
> **前期完成**：
> - TD-036 backend 全路由测试覆盖 ✅ / TD-032 FallbackSource 恢复主源 ✅ / TD-059 契约测试 ✅
> - 全代码库测试架构审查 + 测试策略文档 + 学习卡片 #17
> - QA 质量保障体系 Module 12 + Phase R P0 修复（TD-028~031）+ Batch 6
>
> **全量 941 tests collected, 全部通过** ✅
>
> **当前阶段**：TD-058 ✅、TD-036 ✅、TD-032 ✅、TD-059 ✅。
> 建议下一步：**TD-038 密钥管理 → TD-039 API 速率限制 → TD-040 LLM Provider fallback**。

### 🥇 Phase R 实盘加固（TD-036/032/058/059 全部完成 ✅）

| 优先级 | 说明 | 涉及范围 | 工作量 |
|:------:|:-----|:--------:|:-----:|
| | ~~🔴 **TD-058 模块级 conftest** — ~~4 模块~~ | ~~`tests/`~~ | ~~~1.5h~~ |
| | **✅ TD-058 已修复** — 4 模块 conftest + 11 文件迁移 | | |
| | ~~🔴 **TD-036 backend 路由测试** — ~~创建 `test_backend/`~~ | ~~`tests/`~~ | ~~~2d~~ |
| | **✅ TD-036 已修复** — 77 测试覆盖 17 端点 | | |
| 🔴 P1 | **TD-038 .env 密钥管理** — 密钥轮换 + 凭据管理器 | `config/` | ~30min |
| 🟡 P1 | **TD-039 API 速率限制** — slowapi + debate/run 特别限流 | `backend/` | ~1h |
| 🟡 P1 | **TD-040 LLM Provider fallback** — DeepSeek→OpenAI 自动降级 | `src/utils/` | ~1d |
| 🟡 P2 | **TD-041 数据新鲜度标注** — KLine/Quote 采集时间戳 + 前端展示 | `src/data/` + `frontend/` | ~2h |

### 🥈 后续方向

| 优先级 | 说明 | 涉及范围 | 工作量 |
|:------:|:-----|:--------:|:-----:|
| 🟡 R2 | **全 API 错误路径覆盖** — 超时/空数据/异常 → 结构化错误响应 | `backend/` | ~1d |
| 🟡 R3 | **一键启动脚本** — 你父母双击就能用 | `scripts/` | ~1h |
| 🟡 R3 | **浏览器全功能验证** — 所有页面实际操作一遍 | 全局 | ~1h |
| 🟢 R4 | **置信度量化 + 胡说检测** — AI 不确定时明确说"不确定" | `src/debate/` | ~2d |
| 🟢 R4 | **📊 交易复盘看板（Trade Retro Board）** — AI推荐记录 + 用户操作 + 实际盈亏 + 准确率统计 | `src/` + `frontend/` | ~2d |
| 🟢 R4 | **回测看板** — AI 历史建议准确率可视化 | `frontend/` | ~2d |

### 📊 交易复盘表（核心交互说明）

辩论系统输出 AI 建议后，自动记录到复盘表。每行记录：

```
日期 | 股票 | AI推荐(方向+置信度) | 用户操作 | 实际盈亏% | 是否正确 | 偏差分析
```

**3 个产出**：
1. 后端 Pydantic 模型 + `/api/retro/` 查询+统计
2. 前端表格组件（筛选/排序）
3. 自动采集机制：辩论触发时记录推荐，后端定时拉行情填盈亏

> 关联 TD-017 M2 反思闭环 — 复盘数据是 Agent 学习改进的输入。

### 下个会话推荐启动顺序

```
1. /resume-session 恢复上下文
2. TD-038 密钥管理 → TD-039 API 速率限制
3. 后续：TD-040 LLM Provider fallback → TD-041 数据新鲜度标注
```

> **最后更新**：2026-06-18（TD-058 剩余 4 模块 conftest ✅） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

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

> **最后更新**：2026-06-18（TD-058 剩余 4 模块 conftest ✅） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

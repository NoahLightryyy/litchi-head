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
| **最新提交** | `14312ee` — docs: docs 重组收尾 — ROUTING + SPEC 精简 + .legacy 清理 + 路径修复 |

---

## 2. 当前会话状态（2026-06-16 — M3 信任度评分完成）

> **本次完成**：M3 信任度评分 `src/debate/trust.py`，54 测试全部通过。

### 完成内容

| 事项 | 状态 |
|:-----|:----:|
| `AgentOutcome` + `AgentTrustMetrics` + `TrustReport` 数据模型 | ✅ |
| `TrustTracker.record_outcome()` / `record_outcome_from_analysis()` 记录 | ✅ |
| `TrustTracker.get_trust_report()` 查询信任度画像 | ✅ |
| 方向准确率 / 各方向准确率统计 | ✅ |
| Brier score 置信度校准 | ✅ |
| 置信度偏差 / 乐观偏差检测 | ✅ |
| 校准曲线数据生成 | ✅ |
| 趋势检测（improving/declining/stable） | ✅ |
| `compute_weight_factor()` 权重因子函数 | ✅ |
| `flush()` 持久化到 MemoryStore（带去重） | ✅ |
| 54 测试全部通过（Lint + Type + Test ✅） | ✅ |
| SPEC.md M3 章节新增 | ✅ |

### 重要：docs/ 重组 — 新结构图

```
docs/
├── README.md                 ← 全文档路由表
├── 00-overview/              ← 🏠 总览（4 文件：OVERVIEW + GLOSSARY + TECH_STACK + ROADMAP）
├── 01-guides/                ← 📐 流程规范 + AI 路由
│   └── debt/                 ← 债务按类型拆分（7 文件）
├── 02-requirements/          ← 📋 产品需求
├── 03-modules/               ← 🔧 ★ 核心：9 个模块，各一个文件夹
│   ├── 01-data-collection/   ← README + SPEC + RESEARCH + ADR
│   ├── 02-debate-engine/     ← README + SPEC + RESEARCH + ADR
│   └── ...（同格式）
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

### 当前 Git 状态

```
已提交: b7caa37 — feat: 回测←→辩论桥接适配器 — TradePlan → TradeRecord 转换 + 20 测试
工作区: trust.py + 54 tests（干净待提交）
```

### 测试覆盖

| 测试文件 | 测试数 |
|---------|:------:|
| `tests/test_debate_*.py` | 199（含 54 M3 🆕） |
| `tests/test_risk_*.py` | 26 |
| `tests/test_trader_*.py` | 20 |
| `tests/test_backtest_*.py` | 65（含 20 桥接 🆕） |
| `tests/test_e2e_full_pipeline.py` | 5 |
| `tests/test_memory_*.py` | 29 |
| `tests/test_agents_*.py` | 58+4 skip |
| 其他 | 78 |
| **全量** | **691 passed** |

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

## 5. 下一步优先级（2026-06-16 更新：M3 信任度评分完成）

> **本次完成**：M3 信任度评分 `src/debate/trust.py` + 54 测试全通过。
> 下一步建议：**M4 动态权重** — 根据信任度自动调整 aggregate 权重。

### 🥇 下一步

| 优先级 | 说明 | 涉及范围 | 工作量 |
|:------:|:-----|:--------:|:-----:|
| ~~🟡 **P1**~~ | ~~**回测→辩论桥接** — TradePlan → TradeRecord 适配器~~ ✅ 已完成 | `backtest/bridge.py` | 中 |
| ~~🟡 **P1**~~ | ~~**M3 信任度评分** — Agent 输出 vs 实际结果追踪~~ ✅ 已完成 | `debate/trust.py` | 中 |
| 🟡 **P2** | **M4 动态权重** — 用 `compute_weight_factor()` 调整 aggregate 权重 | `debate/orchestrator.py` | 小-中 |
| ⬇️ **P2** | **C1 简报分区输出** — format_market_brief 按区块分区 | `data/collector.py` | 小 |
| ⬇️ **P2** | **前端 MVP** — Streamlit 3 页面 | 前端 | ~2d |

### 下个会话推荐启动顺序

```
1. `/resume-session` 恢复上下文
2. ~~回测→辩论桥接~~ ✅ 已完成
3. ~~M3 信任度评分~~ ✅ 已完成
4. M4 动态权重 — aggregate 接入 compute_weight_factor()
```

> **最后更新**：2026-06-16（M3 信任度评分完成 — trust.py + 54 tests） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

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
| `src/data/models.py` | 5 个 Pydantic 数据契约 |
| `src/data/cache.py` | DataCache 内存 TTL 缓存 |
| `src/data/collector.py` | DataCollector 封装 akshare 6 类数据 |
| `src/debate/models.py` | 辩论数据模型（含 D1+D2+D3+D4 扩展） |
| `src/debate/orchestrator.py` | LangGraph 辩论编排器（含 D1+D2+D3+D4+M1） |
| `src/debate/reflection.py` | M2 反思闭环（Record→Compare→Reflect→Inject） |
| `src/backtest/models.py` 🆕 | 回测数据模型（BacktestConfig/TradeRecord/BacktestReport） |
| `src/backtest/engine.py` 🆕 | BacktestEngine 回测模拟引擎 |
| `src/backtest/metrics.py` 🆕 | 绩效指标计算（夏普/回撤/胜率/盈亏比/CAGR） |

### 辩论模块测试

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_debate_orchestrator.py` | 52 | 辩论编排器 MVP |
| `tests/test_debate_d1_cross_review.py` | 25 | D1 交叉审阅+反驳 |
| `tests/test_debate_d2_direction_constraint.py` | 31 | D2 强制输出方向 |
| `tests/test_debate_d3_independent_review.py` | 23 | D3 独立评审 |
| `tests/test_debate_m1_history_injection.py` | 22 | M1 历史决策注入 |
| `tests/test_debate_d4_vote_summary_extension.py` | 15 | D4 VoteSummary 扩展 |

### 关键调研文档

| 文档 | 说明 |
|------|------|
| `docs/00-overview/OVERVIEW.md` | 项目概览（新读者起点） |
| `docs/03-modules/` | 全部功能模块规格 |
| `docs/03-modules/02-debate-engine/SPEC.md` | 辩论引擎规格（含 TradingAgents 源码分析） |
| `docs/01-guides/debt/ROUTER.md` | 技术债务路由索引 |
| `docs/05-decisions/README.md` | 跨模块 ADR 索引 |

---

> **最后更新**：2026-06-15（docs 重组全部完成 — ROUTING + SPEC 精简 + .legacy 清理 + 全路径修复） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

# 🔄 AI 会话交接文档

> **用途**：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
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
| **最新提交** | 待提交（本次为上下文优化会话，见工作日志 2026-06-14-4） |

---

## 2. 当前会话状态（2026-06-15 — P0 端到端链路验证完成）

> **P0 端到端链路验证** — 全 9 层辩论链路 E2E 测试 5 pass + 成本测算 + 真 Bug 修复。
> 617 tests（+5 E2E），零回归。

> **P0 回测引擎基础实现** — BacktestEngine + 45 tests。Phase 1 最后一个空模块已填补。
> 324+ tests（子集验证），全部模块就绪。

### 重要：回测引擎上线

**`src/backtest/` 由空骨架变为可用工具**。三大组件：
- `BacktestEngine` — 逐日回放模拟（入场/持仓/出场）
- `PerformanceMetrics` — 夏普/回撤/胜率/盈亏比/CAGR
- `BacktestReport` — 完整净值曲线 + 交易明细

### 重要：端到端链路验证完成

**`tests/test_e2e_full_pipeline.py`** — 5 项全链路测试，覆盖：
- 基础 6 层流程（→ analyst → master → review → review_report → aggregate）
- 全 9 层链路（+ risk + trader + pm）
- 带 memory/reflection 的全链路
- 网络异常 + 部分节点失败容错
- `to_summary_dict` 序列化

**同时发现并修复了一个真 Bug** — `trader/orchestrator.py` 中 `_format_vote_for_trader` 函数使用 dict 语法 `.get()` 操作 Pydantic 的 `VoteSummary` 对象，导致 enable_trader=True 时全链路崩溃。

### 重要：新增 resume-session Skill

**新会话启动直接执行 `/resume-session`**，封装了三层启动流程。不再需要手动读 AI自动化工作流程.md。

### 架构哲学转变

旧：「7位投资大师各说各的 → 投票」— 辩论团伙
新：「分析师 → 策略师 → 辩论 → 评审 → 裁决」— 专业交易团队

**核心原则**：体系 > 天才。信息必须垂直递进，每层产出是下层输入。

### 当前辩论流程

```
collect_data → analyst_round (4位专业分析师) → strategy_round (大师综合报告)
  → review_round (D1) → review_report (D3) → aggregate (D3+D4)
  → risk_round (R1 三层风控) → trader_round (T1 交易员) → pm_round (PM裁决) → END
       ↑ M1 历史注入              ↑ D2 方向约束
       ↑ M2 反思注入（可选）       ↑ enable_reflection=True 时生效
```

| 层级 | 节点 | 角色 | 人数 |
|:----|:-----|:-----|:---:|
| 第 1 层 | `analyst_round` | 专业分析师（基本面/技术面/情绪面/宏观面） | 4 |
| 第 3 层 | `master_round` (strategy) | 策略师（基于报告综合判断，保留大师人格） | 5 |
| 辩论层 | `review_round` | 交叉审阅+反驳（D1） | - |
| 评审层 | `review_report` | 独立评审（D3+D4） | 1 |
| 聚合层 | `aggregate` | 加权投票汇总 | - |
| 风控层 | `risk_round` | 三层风控辩论（R1 — Aggressive/Conservative/Neutral） | 3 |
| 交易员层 | `trader_round` | 交易员制定多步执行计划（T1 — ExecutionStep/TradePlan） | 1 |
| PM层 | `pm_round` | Portfolio Manager 最终裁决 | 1 |

### 当前 Git 状态

```
已提交: c87242a — docs: DeepSeek 模型快慢分离策略
工作区: Batch Loop 规则 + E2E 测试 + 成本脚本 + trader bug 修复（未提交）
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|---------|:------:|---------|
| `tests/test_data_*.py` | 48+5 skip | 数据层全部 |
| `tests/test_debate_*.py` | 145 | 编排器 + 分析师层 + D1 + D2 + D3 + D4 + M1 |
| `tests/test_risk_*.py` | 26 | R1 三层风控辩论 + PM裁决 |
| `tests/test_trader_*.py` | 20 | T1 交易员层（模型 + 节点 + 集成） |
| `tests/test_backtest_*.py` | 45 | 回测引擎 + 绩效指标 + 模型 |
| `tests/test_e2e_full_pipeline.py` | 5 🆕 | E2E 全链路（9 层） |
| `tests/test_memory_*.py` | 29 | MemoryStore + MemoryManager MVP |
| `tests/test_agents_*.py` | 58+4 skip | 全部 Agent |
| 其他 | 78 | 冒烟/通信/费用/知识库/Skill + complexity_router |
| **全量** | **617 passed** | |

### 项目核心状态

| 维度 | 评分 | 关键发现 |
|:----|:----:|:---------|
| 工程管理 | A | ADR/债务/CI/记忆系统 — 成熟度持续提升 |
| 代码完成度 | A- | 8 模块就绪，Phase 1 全部空模块已填补 |
| 测试质量 | A- | 45 backtest tests（新增），零回归 |
| 文档完整度 | A | 行业知识库 + TradingAgents 源码分析 + 交易纪律调研 |
| 产品可演示性 | C | 分析链路可运行，需前端展示 |

### 硬伤跟踪

1. **🟡 子 Agent 不可用** — 跟随主会话走 DeepSeek，Claude 模型调用将 401
2. **🟢 ~~backtest 空模块~~** — ✅ **已实现（P0 回测引擎基础 + 45 tests）**

### 当前配置现状

| 层级 | 配置 | 状态 |
|------|------|:----:|
| **Claude Code 主会话** | Windows 用户 env: DeepSeek 端点 + DeepSeek Key | ✅ |
| **子 Agent（内置）** | 跟随主会话 → DeepSeek（Claude 调用会 401） | ⚠️ |
| **Python 应用代码** | `.env`: DeepSeek 默认 + 灵算（`provider=anthropic`） | ✅ |

### TradingAgents 源码分析结论

**已采纳**：多轮对抗辩论、独立评审层、记忆注入、风控辩论（可复用 `debate/` 基础设施）

**不采纳**：信息隔离（大师需要全貌做风格化判断）、单 Bull/Bear 对抗（四组大师架构是差异化优势）

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

## 5. 下一步优先级（2026-06-15 更新：P0 端到端链路验证完成）

> 本次为 P0 端到端链路验证 + Batch Loop 规则 + 成本测算。617 tests，全 9 层链路验证通过。

### 🥇 下一步

| 优先级 | 代号 | 说明 | 涉及模块 | 工作量 |
|:------:|:----:|:-----|:--------:|:-----:|
| 🟡 **P1** | **回测→辩论桥接** | TradePlan → TradeRecord 适配器，接入编排器 | `backtest/` + `debate/` | 中 |
| 🟡 **P1** | **M3 信任度评分** | Agent 输出 vs 实际结果准确率追踪 | `debate/` | 中 |
| ⬇️ **P2** | **C1 简报分区输出** | format_market_brief 按区块分区 | `data/collector.py` | 小 |
| ⬇️ **P2** | **前端 MVP** | Streamlit 3 页面（需求已定） | 前端 | ~2d |

### 已完成（Phase 1 全部）

| 优先级 | 代号 | 说明 | 状态 |
|:------:|:----:|:-----|:----:|
| ✅ | D1~D4 + M1+R1+T1+M2 | 辩论引擎全部模块 | 已完成 |
| ✅ | P0 回测引擎基础 | BacktestEngine + 45 tests | 已完成 |
| ✅ | **P0 端到端链路验证** | 9 层全链路 E2E 测试 + 成本测算 | 已完成 🆕 |
| ✅ | Batch Loop 规则 | CLAUDE.md + 交接文档 + 流程规范 | 已完成 🆕 |
| 🔧 | TD-017 反思闭环缺失 | 架构补充（M2 已实现，复盘确认） | 修复中 |

> **最后更新**：2026-06-15（P0 端到端链路验证完成 + Batch Loop 规则上线） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

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
| `docs/调研分析/行业开源方案对照知识库.md` | 7条战线全景知识库 |
| `docs/调研分析/功能模块/` | 9 个功能模块文件夹 |
| `docs/调研分析/功能模块/02-辩论决策引擎/TradingAgents源码分析/README.md` | TradingAgents v0.2.4 源码深度分析 |

---

> **最后更新**：2026-06-14（架构批判与市场对照 + 优先级重排 + TD-017/018/019 🆕） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

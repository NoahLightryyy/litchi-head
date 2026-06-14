# 🔄 AI 会话交接文档

> 用途：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
> **新 AI 启动流程：**
> 
> ```
> 记忆层自动注入       ← project-identity + architecture-decisions + current-state
>   ↓                  （来自 memory 系统，不需要我读文件）
> 交接文档 §2 + §5     ← 当前状态 + 下一步（约 3K token）
>   ↓
> 最新工作日志         ← 前一次会话具体内容
>   ↓
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
| **最新提交** | `203fb0c` — feat: Phase 1 分析师层 — 从辩论团伙到专业交易团队 |

---

## 2. 当前会话状态（2026-06-14 — T1 交易员层 + 流程修复 + 决策索引）

> **T1：交易员执行规划层 — PM 与执行之间的 Trader 角色。**
> **流程修复 — 战略意图落笔原则 + 决策检索索引，防止灵感丢失。**
> 辩论引擎全部模块（D1/D2/D3/D4/M1/R1/T1 + 分析师层）已完成，537 tests。

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
已提交: 9e94767 — feat: R1 三层风控辩论 + 交易纪律落地
工作区: T1 交易员层未提交（src/trader/ + tests/test_trader_t1.py）
        流程修复未提交（docs/流程规范/AI自动化工作流程.md §3.1-bis）
        战略决策索引 + 团队构建展望 未提交（docs/架构设计/）
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|---------|:------:|---------|
| `tests/test_data_*.py` | 48+5 skip | 数据层全部 |
| `tests/test_debate_*.py` | 145 | 编排器 + 分析师层 + D1 + D2 + D3 + D4 + M1 |
| `tests/test_risk_*.py` | 26 | R1 三层风控辩论 + PM裁决 |
| `tests/test_trader_*.py` | 20 | T1 交易员层（模型 + 节点 + 集成） |
| `tests/test_memory_*.py` | 29 | MemoryStore + MemoryManager MVP |
| `tests/test_agents_*.py` | 58+4 skip | 全部 Agent |
| 其他 | 78 | 冒烟/通信/费用/知识库/Skill + complexity_router |
| **全量** | **~537 passed, 4 skipped** | |

### 项目核心状态

| 维度 | 评分 | 关键发现 |
|:----|:----:|:---------|
| 工程管理 | A | ADR/债务/CI/记忆系统 — 成熟度持续提升 |
| 代码完成度 | B+ | 7 模块就绪，专业团队架构 Phase 1 完成 |
| 测试质量 | A- | 517 passed, 零回归 |
| 文档完整度 | A | 行业知识库 + TradingAgents 源码分析 + 交易纪律调研 |
| 产品可演示性 | C | 分析链路可运行，需前端展示 |

### 硬伤跟踪

1. **🟢 ~~risk 模块~~** — ✅ **已实现（R1 三层风控辩论 + PM裁决 + 交易纪律）**
2. **🟡 子 Agent 不可用** — 跟随主会话走 DeepSeek，Claude 模型调用将 401
3. **🔴 1 个空模块** — backtest（仅 `__init__.py`）

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
  src/memory/      — knowledge_base / skill_disk / store / manager（MVP ✅）

空架子模块（⬜）：
  src/backtest/    — 回测引擎
```

### 3.2 技术债务一览

```
紧急指数：0.5/10（历史最低）

✅ 已关闭（9 条）：
  TD-002 / TD-009 / TD-010 / TD-011 / TD-012 / TD-013 / TD-014 / TD-015 / TD-016

🔧 修复中（2 条）：
  TD-001  LLM 封装层（惰性导入优化完成，模型路由待补）
  TD-004  测试基座（517 tests，backtest 待补）

📋 已确认（5 条，全部低优）：
  S2 🟡 TD-003 MessageRouter 内存存储 / TD-005 双配置源
  S3 🟢 TD-006 EvidenceItem 无校验 / TD-007 ensure_dirs / TD-008 价格硬编码

开放债务：5 条（历史最低）
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

## 5. 下一步优先级（2026-06-14 更新：R1 三层风控辩论完成）

### 🥇 辩论深度进化（方向 A — 全部完成 ✅）

| 优先级 | 步骤 | 说明 | 状态 |
|:------:|:----:|:-----|:----:|
| ✅ | **D1 第二轮交叉审阅+反驳** | 大师互相看分析后反驳/补充 | 已完成 |
| ✅ | **D2 强制输出方向** | 每位大师末尾加方向判断 | 已完成 |
| ✅ | **D3 独立评审 Agent** | 独立 LLM 评审 + 权重建议 | 已完成 |
| ✅ | **M1 历史决策注入** | MemoryManager 接入辩论编排器 | 已完成 |
| ✅ | **D4 VoteSummary 结构化扩展** | VoteSummary 增加评审修正字段 | 已完成 |
| ✅ | **Phase 1 分析师层** | 4 位专业分析师 + 策略师角色转换 | 已完成 |
| ✅ | **R1 三层风控辩论** | Aggressive/Conservative/Neutral + PM裁决 + 交易纪律 | 已完成 |
| ✅ | **T1 交易员层** | ExecutionStep/TradePlan + trader_round 节点 | 🆕 已完成 |

### 🥇 专业交易团队 — 下一步

| 优先级 | 代号 | 说明 | 涉及模块 | 工作量 |
|:------:|:----:|:-----|:--------|:------:|
| 📌 | **M2 交易后反思** | 决策结果 → 实际收益 → 反思分析 → 更新记忆 | `memory/` + `debate/` | 中 |
| 🥈 | **C1 简报分区输出** | format_market_brief 按区块分区 | `data/collector.py` | 小 |
| 🥈 | **端到端链路验证** | 全链路跑通 + 真实 LLM 集成 | 多模块 | 中 |
| 🥈 | **M3 信任度评分** | 每位 Agent 输出 vs 实际结果准确率追踪 | `debate/` | 中 |
| 🥉 | **回测引擎基础** | 简单策略回测框架 | `src/backtest/` | 中 |

> **最后更新**：2026-06-14（T1 交易员层 + 流程修复 + 决策索引，537 tests） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

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

> **最后更新**：2026-06-12（第 9 次 — D4 VoteSummary 结构化扩展，491 tests） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

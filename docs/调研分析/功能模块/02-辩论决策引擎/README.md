# 功能模块：辩论决策引擎

> ⚡ 这是 litchi-head 的核心模块，也是你最需要深挖的方向。

## 所属战线：多 Agent 辩论决策 ⬅ 你的主战场

> **战线格局**：TradingAgents（角色分工线）vs AI Hedge Fund（人格模拟线）vs ContestTrade（内部竞赛线）vs **你（四组辩论+评审线）**
>
> [查看战线完整分析](../../行业开源方案对照知识库.md#-战线-1多-agent-辩论决策)

### 战线上谁在做什么

```
                    ┌── 角色分工路线 ── TradingAgents (71k⭐)
                    │    模拟华尔街投研团队，5层递进，Bull/Bear辩论
                    │
  多Agent辩论决策 ──┼── 人格模拟路线 ── AI Hedge Fund (51k⭐)
                    │    14位传奇投资人各抒己见，投票综合
                    │
                    ├── 内部竞赛路线 ── ContestTrade
                    │    多Agent竞争、优胜劣汰、只采纳最优者
                    │
                    └── 你的路线 ── litchi-head
                         四组大师辩论 + 独立评审 + 加权汇总
                         辩论深度上比前三者都更深入
```

### 你的位置

你是这条战线上的新入局者，但**辩论深度**上你有独特设计——TradingAgents 只有一组 Bull/Bear 对抗，你有**四组各自辩论+评审**。缺点是你的轮次和张数都还比较浅（单轮，分析合一），需要从对手那里吸取精华。

### 关键启示

| 来自谁 | 启示 |
|--------|------|
| **TradingAgents** | 多轮对抗辩论机制、强制立场（必须选看多/看空）、三层风控辩论 |
| **AI Hedge Fund** | 大师人格的提示词工程、14种投资哲学各有具体规则 |
| **ContestTrade** | 内部竞赛+优胜劣汰抑制幻觉，适合作为辩论的前置过滤 |

---

## 模块定义

多 Agent 辩论 + 评审 + 加权决策的核心流程。

**职责边界**：
- ✅ 多大师/多策略的并行或顺序分析
- ✅ 看多/看空对抗辩论
- ✅ 评审 Agent 综合裁决
- ✅ 结构化投票输出
- ❌ 不负责数据采集（那是数据采集模块的事）
- ❌ 不负责最终交易执行（那是交易执行模块的事）
- ❌ 不负责 Agent 的提示词人格设计（那是人格与提示词模块的事）

## 你在 litchi-head 中的位置

| 源码 | 说明 |
|------|------|
| `src/debate/orchestrator.py` | 编排器：LangGraph StateGraph 驱动全流程（5 节点，含 M1 历史注入 + D2 方向约束） |
| `src/debate/models.py` | 辩论数据模型（DebateInput / DebateResult / AgentAnalysis / IndependentReview 等） |
| `src/memory/store.py` | MemoryStore 抽象接口 + JsonFileStore 实现（M1 接入点） |
| `src/agents/master_agent.py` | 通用 MasterAgent（通过配置控制行为） |

## 行业参照项目

| 项目 | ⭐ | 战线角色 | 值得看的 |
|------|-----|---------|---------|
| **TradingAgents** | 71k | 战线领头羊 | Bull/Bear 多轮对抗辩论 + Research Manager 综合 + 分层架构 |
| **AI Hedge Fund** | 51k | 人格模拟路线 | 14位大师人格的提示词工程、Web UI 与回测器一体化 |
| **ContestTrade** | — | 内部竞赛路线 | 内部竞赛机制 + 优胜劣汰抑制幻觉 |

## 架构对照分析

### 你现在的架构（M1 历史决策注入 + D2 方向约束已接入）

```
┌──────────────────────────────────────────────────────────────┐
│  MemoryStore.search("episodic", "debate")                      │
│    → _format_history_context()                                 │
│    → 注入 DebateState.history_context                          │
│       ↓                                                       │
│  collect_data（采集数据）                                       │
│       ↓                                                       │
│  master_round（顺序调各位大师独立分析，prompt 含历史上下文）       │
│    ├─ 大师A：生成 AgentAnalysis（含 📜 历史决策 + 🧭 方向约束）   │
│    ├─ 大师B：生成 AgentAnalysis（含 📜 历史决策 + 🧭 方向约束）   │
│    └─ 大师C：生成 AgentAnalysis（含 📜 历史决策 + 🧭 方向约束）   │
│       ↓                                                       │
│  review_round（第二轮交叉审阅，prompt 含历史上下文 + 方向展示）    │
│       ↓                                                       │
│  review_report（独立评审，prompt 含历史上下文 + 方向分布）         │
│       ↓                                                       │
│  aggregate（投票加权汇总 → VoteSummary.direction_distribution）  │
│       ↓                                                       │
│  _save_decision_to_memory() → MemoryStore.put()                │
└──────────────────────────────────────────────────────────────┘
```

特点：单轮、分析==评审合一、无交叉审阅、D2 强制方向已接入。

### TradingAgents 的做法（核心可借鉴）

```
┌──────────────────────────────────────────────────────┐
│  Phase 1: 分析师团队（4个并行）                        │
│    基本面/舆情/新闻/技术各出报告                       │
│       ↓                                              │
│  Phase 2: 研究员辩论（串行，默认2轮）                  │
│    Round 1: Bull写看多报告, Bear写看空报告（背对背）    │
│    Round 2: 互看对方报告后反驳                        │
│    Research Manager 综合两方 → 辩论总结               │
│       ↓                                              │
│  Phase 3: Trader（基于分析+辩论 → 交易提案）           │
│       ↓                                              │
│  Phase 4: 风控辩论（3个并行）                          │
│    激进/中性/保守 三维度评估                           │
│       ↓                                              │
│  Phase 5: Portfolio Manager（最终裁决）                │
└──────────────────────────────────────────────────────┘
```

**关键设计**：
1. **强制立场** — 研究员必须选看多或看空，不能中立
2. **多轮对抗** — 看到对方论证后必须反驳，逼出深层推理
3. **信息隔离** — 分析师只看数据不出决策，研究员只看分析不接触原始数据

### ContestTrade 的内部竞赛（可做前置过滤）

```
┌──────────────────────────────────────────────┐
│  数据团队（并行）         研究团队（并行）      │
│  Data Agent 1 ──→ 因子   Researcher 1 ──→ 提案 │
│  Data Agent 2 ──→ 因子   Researcher 2 ──→ 提案 │
│  Data Agent 3 ──→ 因子   Researcher 3 ──→ 提案 │
│        ↓                       ↓               │
│  内部竞赛（评分+排名）    内部竞赛（评分+排名）     │
│  只采纳Top因子 ───→    只采纳Top提案            │
└──────────────────────────────────────────────┘
```

**和你的异同**：
- 你是"讨论→综合"，ContestTrade 是"竞争→优胜劣汰"
- 你的评审是"裁判"，他们的竞赛是"淘汰赛"
- 可以结合：先竞赛筛选候选人 → 再辩论深入 → 评审综合

---

## 关键研究问题（2026-06-12 第 8 次更新：D2 强制输出方向完成）

### M1 — 历史决策注入 ✅ 实施完成
- [x] **已实施**：`MemoryStore` 接入辩论编排器，大师 prompt 自动注入历史决策参考。
- [x] **查询**：辩论前自动查询 `("episodic", "debate")` 命名空间下的历史决策。
- [x] **格式化**：`_format_history_context()` 将 MemoryItem 列表转为可读的 LLM prompt 文本。
- [x] **注入点**：同时注入大师分析（master_round）、交叉审阅（review_round）、独立评审（review_report）三级 prompt。
- [x] **保存**：辩论结束后 `_save_decision_to_memory()` 自动保存共识/评分/大师摘要。
- [x] **异常熔断**：所有 MemoryStore 操作在 try/except 中，失败不阻塞辩论。
- [x] **向后兼容**：`memory_store=None` 时行为完全不变。
- [x] **结论**：低成本高收益——修改 orchestrator.py 约 80 行新增代码，22 个测试，零回归。历史记忆让大师有了"自我复盘"能力。

### D1 — 多轮对抗辩论 ✅ 实施完成
- [x] **已分析**：TradingAgents 的多轮对抗靠 Prompt 约束，不是靠复杂逻辑——Bull/Bear Prompt 中写"你必须反驳对方观点"。
- [x] **已实施**：第二轮交叉审阅已加入 LangGraph 图——每位大师完成第一轮分析后，看到所有同行分析并生成结构化反驳。
- [x] **已验证**：8 次 LLM 调用（4 位大师×2轮）token 成本可控，360 测试全通过，DeepSeek 成本是 GPT-4o 的 1/10。
- [x] **结论**：TradingAgents 的"看到完整论点→要求反驳"机制已适配移植。关键代码见 `orchestrator.py:_run_review_for_master()`。

### D2 — 强制立场与信息隔离 ✅ 实施完成
- [x] **已分析**：TradingAgents 用角色分配（Bull/Bear）实现强制立场，不给中立选项。
- [x] **已实施**：大师 prompt 末尾加固化的 direction 约束（Bullish/Bearish/Neutral）。
- [x] **Pydantic 验证**：`InvestmentAnalysis.direction` 使用 `pattern=r"^(Bullish|Bearish|Neutral)$"` 约束。
- [x] **归一化**：无效 direction 值在 orchestrator 层规范化为 Neutral，防止下游异常。
- [x] **聚合**：`VoteSummary.direction_distribution` 自动统计方向分布。
- [x] **对接 D3**：review_round 和 review_report prompt 均展示大师方向分布。
- [x] **31 个新测试**：模型/映射/聚合/集成/兼容全覆盖，436 全量通过，零回归。
- [x] **结论**：最小改动（prompt 末尾加约束 + 一个 Pydantic 字段），低风险高收益。每位大师必须选方向，评审层直接可看到方向分布。
- [ ] TradingAgents 的信息隔离（Analyst 只看数据，Researcher 只看报告）适用于你的场景吗？ — **暂不实施**：大师需要全貌来做风格化判断。

### D3 — 独立评审层 ✅ 实施完成
- [x] **已实施**：在 `review_round → aggregate` 之间插入 `review_report` 节点。
- [x] **模型**：`IndependentReview(BaseModel)` — 13 字段，含裁判独立评级/权重建议/偏见识别。
- [x] **聚合升级**：`weight_suggestions` 作为置信度乘数影响 `weighted_score`，无需修改原始评分。
- [x] **向后兼容**：`review_report=None` 时 aggregate 行为不变。
- [x] **已验证**：23 个新测试，全量 383 通过，零回归。
- [x] **结论**：独立 LLM 评审人格 = 双维度交叉验证（数学加权 + 裁判判断），实现成本低回报高。

### D4 — 结构化评审输出
- [ ] VoteSummary 是否需要扩展评审修正字段？（review_score / adjusted_weights / review_notes）
- [ ] TradingAgents 的 5-tier 评分（Buy/Overweight/Hold/Underweight/Sell）是否比你的更细化？

### 幻觉抑制
- [ ] 辩论 vs 竞赛 vs 投票，哪种最能抑制 LLM 幻觉？
- [ ] ContestTrade 的内部竞赛机制能否作为你辩论流程的前置过滤？
- [x] **已分析**：TradingAgents 的"强制立场+强制反驳"本身就是一种幻觉抑制手段。

---

## 子文件夹说明

| 路径 | 用途 |
|------|------|
| `./辩论机制设计/` | 辩论流程架构、轮次策略、对抗模式设计 |
| `./评审机制设计/` | 评审 Agent 设计、评分标准、裁决规则 |
| `./TradingAgents源码分析/` | **已更新** — 完整 TradingAgents v0.2.4 源码深度分析（4 层可落地项） |
| `./ContestTrade源码分析/` | ContestTrade 内部竞赛机制的源码阅读笔记 |
| `./AI Hedge Fund大师分析/` | AI Hedge Fund 的大师人格+投票机制分析 |

## 深挖方向建议（2026-06-12 第 8 次更新：D2 强制输出方向 ✅）

> 以下优先级基于 TradingAgents 源码分析和 MemoryStore MVP 的结论，按"低改动高收益"排序。

### ✅ D1 — 第二轮交叉审阅+反驳（已完成）
**来源**：TradingAgents 多轮对抗 | **工作量**：中 | **涉及文件**：`debate/orchestrator.py` + `debate/models.py`

**实施情况**（2026-06-11）：
- `RebuttalAnalysis(BaseModel)` — LLM 输出的结构化反驳（含 adjusted_score/rating/confidence）
- `PeerReviewRound(BaseModel)` — 集合类，含 `get_for_agent()` 便利方法
- `_run_review_for_master()` — 辅助函数，构造 peer context prompt + 调用 LLM
- `make_review_round_node()` — LangGraph 节点工厂，循环所有成功大师
- 图结构：`master_round → review_round → aggregate`
- 失败大师不参与，仅 1 位成功时整轮跳过
- `VoteSummary.adjustments_applied` 标记消费者是否有调整发生
- 25 个新测试，360 全量通过，零回归

**代码审查修复**：
- `getattr` fallbacks → 直接属性访问
- latency_ms 追踪
- `Optional[None]` sentinel 替代 `0`/`""`
- 直接 `skill.system_prompt` 替代 `MasterAgent` 实例化

- 关键代码改动：orchestrator.py 中 `master_round` 后加 `cross_review_round`
- 约束：DeepSeek 单次 8K tokens 以内，8 次调用可控
- 不更改现有大师人格定义，只加一轮"反驳"prompt

### ✅ D3 — 独立评审 Agent（辩论模块 ✅ 实施完成）
**来源**：TradingAgents Research Manager | **工作量**：中 | **影响范围**：`debate/models.py` + `orchestrator.py`

在 `review_round → aggregate` 之间插入 `review_report` 节点。独立 LLM 评审人格阅读所有大师分析 + 反驳后输出结构化评审报告。

**实施情况**（2026-06-12）：
- `IndependentReview(BaseModel)` — 13 字段（裁判独立评级/权重建议/偏见识别/盲点提示等）
- `_run_independent_review()` — 辅助函数，构建包含大师分析+反驳的评审 prompt
- `make_review_report_node()` — LangGraph 节点工厂，失败/无大师时返回空评审
- `aggregate` 升级 — `weight_suggestions` 作为置信度乘数，不修改原始评分
- 图结构：`master_round → review_round → review_report → aggregate`
- 完全向后兼容：`review_report` 为空时 aggregate 行为不变
- `DebateResult.to_summary_dict()` 含独立评审信息
- 23 个新测试，383 全量通过，零回归

### ✅ M1 — 历史决策注入（辩论模块 ✅ 实施完成）
**来源**：MemoryStore MVP 向下游消费 | **工作量**：小 | **影响范围**：`debate/orchestrator.py` + `memory/store.py`

**实施情况**（2026-06-12）：
- `_format_history_context()` — 记忆条目 → 可读的 LLM prompt 文本，支持逆序/过滤/截断
- `DebateState.history_context` — LangGraph state 字段，自动传递到所有节点
- `DebateOrchestrator.__init__(memory_store)` — 可选参数，向后兼容
- `_save_decision_to_memory()` — 辩论结果自动保存到 `("episodic", "debate")` 命名空间
- 三级 prompt 注入：master_round + review_round + review_report 均获得历史上下文
- 异常熔断：所有 MemoryStore 操作失败不阻塞辩论流程
- 22 个新测试，405 全量通过，零回归

### ✅ D2 — 强制输出方向（辩论模块 ✅ 实施完成）
**来源**：TradingAgents 强制立场 | **工作量**：小 | **影响范围**：大师提示词模板 + 模型定义

每位大师的分析末尾必须输出 `Bullish/Bearish/Neutral` 方向判断，Neutral 必须说明理由。

**实施情况**（2026-06-12）：
- `InvestmentAnalysis.direction` 新增 Pydantic pattern 约束字段 (Bullish/Bearish/Neutral)
- `MasterAgent.run()` prompt 末尾加"强制方向判断"段落
- 落盘归一化：无效 direction 值被规范化为 Neutral
- `AgentAnalysis.direction` + `VoteSummary.direction_distribution` 追踪
- review_round + review_report prompt 均展示大师方向分布
- 历史记忆含方向标签 `[Bullish]`
- 31 个新测试，436 全量通过，零回归

### 🥈 D4 — VoteSummary 结构化扩展（辩论模块）
**来源**：TradingAgents structured output | **工作量**：小 | **影响范围**：`debate/models.py`

扩展 `VoteSummary` 模型增加评审修正字段。

- Prior to D3 实施：先预留字段（`review_score`, `adjusted_weight`, `review_notes`）
- 与 D3 联动：D3 实施后填充这些字段

### 📌 长期
- 结合 TradingAgents"多轮对抗" + "独立评审" + "三维风控" + 你自己的"四组大师辩论"，形成独特范式

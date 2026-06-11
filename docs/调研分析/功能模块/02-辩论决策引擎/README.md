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
| `src/debate/orchestrator.py` | 编排器：LangGraph StateGraph 驱动全流程 |
| `src/debate/models.py` | 辩论数据模型（DebateInput / DebateResult / AgentAnalysis 等） |
| `src/agents/master_agent.py` | 通用 MasterAgent（通过配置控制行为） |
| `src/agents/base.py` | Agent 基类（AgentContext） |

## 行业参照项目

| 项目 | ⭐ | 战线角色 | 值得看的 |
|------|-----|---------|---------|
| **TradingAgents** | 71k | 战线领头羊 | Bull/Bear 多轮对抗辩论 + Research Manager 综合 + 分层架构 |
| **AI Hedge Fund** | 51k | 人格模拟路线 | 14位大师人格的提示词工程、Web UI 与回测器一体化 |
| **ContestTrade** | — | 内部竞赛路线 | 内部竞赛机制 + 优胜劣汰抑制幻觉 |

## 架构对照分析

### 你现在的架构（单轮分析 + 直接汇总）

```
┌──────────────────────────────────────────────────┐
│  collect_data（采集数据）                           │
│       ↓                                           │
│  master_round（顺序调各位大师独立分析）               │
│    ├─ 大师A：生成 AgentAnalysis                     │
│    ├─ 大师B：生成 AgentAnalysis                     │
│    └─ 大师C：生成 AgentAnalysis                     │
│       ↓                                           │
│  aggregate（投票加权汇总 → DebateResult）           │
└──────────────────────────────────────────────────┘
```

特点：单轮、分析==评审合一、无交叉审阅、无强制立场。

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

## 关键研究问题（2026-06-11 第 5 次更新：D1 实施完成）

### D1 — 多轮对抗辩论 ✅ 实施完成
- [x] **已分析**：TradingAgents 的多轮对抗靠 Prompt 约束，不是靠复杂逻辑——Bull/Bear Prompt 中写"你必须反驳对方观点"。
- [x] **已实施**：第二轮交叉审阅已加入 LangGraph 图——每位大师完成第一轮分析后，看到所有同行分析并生成结构化反驳。
- [x] **已验证**：8 次 LLM 调用（4 位大师×2轮）token 成本可控，360 测试全通过，DeepSeek 成本是 GPT-4o 的 1/10。
- [x] **结论**：TradingAgents 的"看到完整论点→要求反驳"机制已适配移植。关键代码见 `orchestrator.py:_run_review_for_master()`。

### D2 — 强制立场与信息隔离
- [x] **已分析**：TradingAgents 用角色分配（Bull/Bear）实现强制立场，不给中立选项。
- [ ] 你的大师是保留"可以中立"的选项，还是强制输出方向？建议：保留中立但要说明理由。
- [ ] TradingAgents 的信息隔离（Analyst 只看数据，Researcher 只看报告）适用于你的场景吗？
- [x] **结论**：信息隔离不直接适用于四组大师场景——大师需要全貌来做风格化判断。建议改用"简报分区输出"（见 01-数据采集）。

### D3 — 独立评审层
- [x] **已分析**：TradingAgents 的 Research Manager 只看辩论历史，不看原始数据，用 Pydantic 结构化输出约束结果。
- [ ] 你的 aggregate 步骤是否拆为两步：LLM 评审（论证质量）→ 加权汇总（一致性检验）？
- [ ] 独立评审的 Key 设计：是否可以看到原始评分？是否可以看到辩论历史？
- [ ] 评审结果是否需要动态影响大师权重？还是只参与最终综合判定？

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

## 深挖方向建议（2026-06-11 第 5 次更新：D1 实施 ✅）

> 以下优先级基于 TradingAgents 源码分析的结论，按"低改动高收益"排序。

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

### 🥇 D3 — 独立评审 Agent（辩论模块）
**来源**：TradingAgents Research Manager | **工作量**：中 | **影响范围**：`debate/models.py` + `orchestrator.py`

`aggregate` 步骤前加一层 LLM 评审：评审 Agent 看辩论记录后输出结构化评审报告。

- 评审不看原始数据，只看大师分析+辩论记录
- 输出格式：`ReviewReport(BaseModel)` — 评分修正 + 综合推荐 + 分歧点分析
- 现有 aggregate 逻辑升级为"LLM 评审 + 数学加权"双重验证

### 🥇 D2 — 强制输出方向（辩论模块 ↔ 人格模块）
**来源**：TradingAgents 强制立场 | **工作量**：小 | **影响范围**：大师提示词模板

每位大师的分析末尾必须输出 `Bullish/Bearish/Neutral` 方向判断，Neutral 必须说明理由。

- 不改大师人格，只在 prompt 末尾加一条格式约束
- 对接 D3 评审层：评审可以直接看到各大师的方向分布

### 🥈 D4 — VoteSummary 结构化扩展（辩论模块）
**来源**：TradingAgents structured output | **工作量**：小 | **影响范围**：`debate/models.py`

扩展 `VoteSummary` 模型增加评审修正字段。

- Prior to D3 实施：先预留字段（`review_score`, `adjusted_weight`, `review_notes`）
- 与 D3 联动：D3 实施后填充这些字段

### 📌 长期
- 结合 TradingAgents"多轮对抗" + "独立评审" + "三维风控" + 你自己的"四组大师辩论"，形成独特范式

# 模块：辩论决策引擎 — 调研分析

> 本文档记录该模块在行业中的竞争格局、竞品分析、架构对比等调研信息。
> 是 SPEC.md 设计决策的背景依据，不是实现规格。
> 需要调研背景时阅读，日常开发不需要。
>
> 关联：SPEC.md（模块规格）| [战线分析](../../99-archive/KNOWLEDGE_BASE.md#-战线-1多-agent-辩论决策)

---

## 所属战线

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

**你的位置**：你是这条战线上的新入局者，但**辩论深度**上有独特设计——TradingAgents 只有一组 Bull/Bear 对抗，你有**四组各自辩论+评审**。缺点是轮次还比较浅（单轮），需要从对手那里吸取精华。

## 竞品分析

| 项目 | ⭐ | 战线角色 | 值得看的 |
|------|-----|---------|---------|
| **TradingAgents** | 71k | 战线领头羊 | Bull/Bear 多轮对抗辩论 + Research Manager 综合 + 分层架构 |
| **AI Hedge Fund** | 51k | 人格模拟路线 | 14位大师人格的提示词工程、Web UI 与回测器一体化 |
| **ContestTrade** | — | 内部竞赛路线 | 内部竞赛机制 + 优胜劣汰抑制幻觉 |

### 关键启示

| 来自谁 | 启示 |
|--------|------|
| **TradingAgents** | 多轮对抗辩论机制、强制立场（必须选看多/看空）、三层风控辩论 |
| **AI Hedge Fund** | 大师人格的提示词工程、14种投资哲学各有具体规则 |
| **ContestTrade** | 内部竞赛+优胜劣汰抑制幻觉，适合作为辩论的前置过滤 |

## 架构对比分析

### TradingAgents 的做法（核心可借鉴）

```
Phase 1: 分析师团队（4个并行）
  基本面/舆情/新闻/技术各出报告
     ↓
Phase 2: 研究员辩论（串行，默认2轮）
  Round 1: Bull写看多报告, Bear写看空报告（背对背）
  Round 2: 互看对方报告后反驳
  Research Manager 综合两方 → 辩论总结
     ↓
Phase 3: Trader（基于分析+辩论 → 交易提案）
     ↓
Phase 4: 风控辩论（3个并行）
  激进/中性/保守 三维度评估
     ↓
Phase 5: Portfolio Manager（最终裁决）
```

**关键设计**：
1. **强制立场** — 研究员必须选看多或看空，不能中立
2. **多轮对抗** — 看到对方论证后必须反驳，逼出深层推理
3. **信息隔离** — 分析师只看数据不出决策，研究员只看分析不接触原始数据

### ContestTrade 的内部竞赛（可做前置过滤）

```
数据团队（并行）         研究团队（并行）
  Data Agent 1 → 因子     Researcher 1 → 提案
  Data Agent 2 → 因子     Researcher 2 → 提案
  Data Agent 3 → 因子     Researcher 3 → 提案
       ↓                       ↓
  内部竞赛（评分+排名）    内部竞赛（评分+排名）
  只采纳Top因子 →        只采纳Top提案
```

**和你的异同**：
- 你是"讨论→综合"，ContestTrade 是"竞争→优胜劣汰"
- 你的评审是"裁判"，他们的竞赛是"淘汰赛"
- 可以结合：先竞赛筛选候选人 → 再辩论深入 → 评审综合

### 你现在 vs TradingAgents 的编排对比

| 维度 | litchi-head | TradingAgents |
|:-----|:-----------|:--------------|
| 流程 | 线性：collect → master → review → report → aggregate | 4层混合：分析师(并行)→研究员(串行)→交易员→风控(并行)→PM |
| 轮次 | 单轮 | 默认2轮，可配置 |
| 辩论形式 | 交叉审阅（大师互相评审+反驳） | Bull/Bear 对抗辩论 |
| 评审 | 独立评审 Agent（第三方裁判） | Research Manager（综合方） |
| 风控 | 内置在 `DebateResult` 评分中 | 独立三层风控辩论 |
| 信息隔离 | 大师看全貌 | 分析师只看数据，研究员只看报告 |
| 历史记忆 | MemoryStore 自动注入 | BM25-based FinancialSituationMemory |

---

## 研究问题

### 短期（Phase 1）

- [ ] 你的"虚拟投资"功能回测框架如何对接辩论模块的输出？
- [ ] TradePlan → TradeRecord 适配器接口设计？
- [ ] M3 信任度评分：Agent 输出 vs 实际结果如何追踪？

### 中期（Phase 2）

- [ ] TradingAgents 的信息隔离（Analyst 只看数据，Researcher 只看报告）适用于你的场景吗？
- [ ] 多轮对抗辩论：从单轮扩展到多轮，prompt 怎么写才能逼出深层推理？
- [ ] 辩论 vs 竞赛 vs 投票，哪种最能抑制 LLM 幻觉？
- [ ] ContestTrade 的内部竞赛机制能否作为辩论流程的前置过滤？
- [ ] VoteSummary 是否需要扩展评审修正字段？（已实施 D4）
- [ ] TradingAgents 的 5-tier 评分（Buy/Overweight/Hold/Underweight/Sell）是否比你的更细化？

### 长期

- [ ] 结合 TradingAgents"多轮对抗" + "独立评审" + "三维风控" + 你自己的"四组大师辩论"，形成独特范式。

---

## 子文件夹索引

| 路径 | 用途 |
|------|------|
| `./辩论机制设计/` | 辩论流程架构、轮次策略、对抗模式设计 |
| `./评审机制设计/` | 评审 Agent 设计、评分标准、裁决规则 |
| `./TradingAgents源码分析/` | TradingAgents v0.2.4 源码深度分析 |
| `./ContestTrade源码分析/` | ContestTrade 内部竞赛机制源码阅读笔记 |
| `./AI Hedge Fund大师分析/` | AI Hedge Fund 大师人格+投票机制分析 |

---

> **最后更新**：2026-06-15（从 SPEC.md 拆分为独立调研文档）

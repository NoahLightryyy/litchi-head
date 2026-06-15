# 模块：辩论决策引擎

> ⚡ litchi-head 的核心模块。多大师并行分析 + 交叉审阅 + 独立评审 + 加权决策。

## 模块定义

多 Agent 辩论 + 评审 + 加权决策的核心流程。

**职责边界**：
- ✅ 多大师独立并行分析（每位大师风格化判断）
- ✅ 第二轮交叉审阅（每位大师看到其他大师分析后反驳/修正）
- ✅ 独立评审 Agent 综合裁决（第三方裁判独立评级）
- ✅ 结构化投票输出（方向/置信度/评分）
- ✅ 历史决策注入（MVC 模式：MemoryStore → 格式化 → 注入 prompt）
- ❌ 不负责数据采集（那是 `data/` 的事）
- ❌ 不负责最终交易执行（那是 `trader/` 的事）
- ❌ 不负责 Agent 的提示词人格设计（那是 `agents/` + Skill 插件盘的事）

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/debate/orchestrator.py` | LangGraph StateGraph 编排器（5 节点：collect → master_round → review_round → review_report → aggregate） |
| `src/debate/models.py` | 辩论数据模型（DebateInput / DebateResult / AgentAnalysis / IndependentReview / VoteSummary 等） |
| `src/debate/reflection.py` | M2 反思闭环（Record → Compare → Reflect → Inject） |
| `tests/test_debate_orchestrator.py` | 编排器 MVP 测试（52） |
| `tests/test_debate_d1_cross_review.py` | 交叉审阅测试（25） |
| `tests/test_debate_d2_direction_constraint.py` | 方向约束测试（31） |
| `tests/test_debate_d3_independent_review.py` | 独立评审测试（23） |
| `tests/test_debate_m1_history_injection.py` | 历史注入测试（22） |
| `tests/test_debate_d4_vote_summary_extension.py` | VoteSummary 扩展测试（15） |

## 架构（当前状态）

```
MemoryStore.search("episodic", "debate")
  → _format_history_context()
  → 注入 DebateState.history_context
     ↓
collect_data（采集数据）
     ↓
master_round（顺序调大师独立分析，含历史上下文 + 方向约束）
  ├─ 大师A：生成 AgentAnalysis（含方向 + 评分 + 置信度）
  ├─ 大师B：生成 AgentAnalysis
  └─ 大师C：生成 AgentAnalysis
     ↓
review_round（第二轮交叉审阅 + 反驳）
     ↓
review_report（独立评审，不含辩论）
     ↓
aggregate（投票加权汇总 → VoteSummary）
     ↓
_save_decision_to_memory()
     ↓
END
```

特点：单轮、深度讨论型（非对抗型）、分析==评审分离、D2 强制方向已接入。

## 数据契约（关键模型）

| 模型 | 位置 | 说明 |
|:-----|:-----|:------|
| `DebateInput` | `models.py` | 辩论输入（ticker / 数据 / 配置） |
| `AgentAnalysis` | `models.py` | 大师分析输出（方向 / 评分 / 置信度 / 推理） |
| `RebuttalAnalysis` | `models.py` | 反驳输出（adjusted_score / rating / confidence） |
| `IndependentReview` | `models.py` | 独立评审（13 字段：评级 / 权重建议 / 偏见识别） |
| `VoteSummary` | `models.py` | 汇总结果（direction_distribution / weighted_score / review_*） |
| `DebateResult` | `models.py` | 最终输出（含完整辩论记录） |

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| D0 — 基础编排器 MVP | ✅ | 52 |
| D1 — 第二轮交叉审阅 + 反驳 | ✅ | 25 |
| D2 — 强制输出方向 | ✅ | 31 |
| D3 — 独立评审层 | ✅ | 23 |
| D4 — VoteSummary 扩展评审修正 | ✅ | 15 |
| M1 — 历史决策注入 | ✅ | 22 |
| M2 — 反思闭环 | 🟡 已实现，待深度集成 | — |

**辩论模块总测试：168 项（全部通过）**

## 下一步

| 优先级 | 说明 | 工作量 |
|:------:|:-----|:------:|
| 🟡 P1 | **回测→辩论桥接** — TradePlan → TradeRecord 适配器 | 中 |
| 🟡 P1 | **M3 信任度评分** — Agent 输出 vs 实际结果追踪 | 中 |
| ⬇️ P2 | 多轮对抗辩论（当前单轮，考虑扩展到多轮） | 中 |

---

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 战线分析 / 竞品对比 / 设计决策背景
> **最后更新**：2026-06-15（从调研笔记精简为规格文档）

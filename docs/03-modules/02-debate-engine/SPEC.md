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
| M3 — 信任度评分 ✅ | 已实现 | 54 |
| M4 — 动态权重 🆕 | ✅ 已实现 | 10 |

**辩论模块总测试：232 项（含 M3 + M4）**

## M3 信任度评分

> **定位**（PROFESSIONAL-TEAM-OUTLOOK.md Phase 4）：每位 Agent 输出 vs 实际结果的准确率追踪。
> M3 是 M4 动态权重的前置数据基础。

### API

```python
from src.debate import TrustTracker

tracker = TrustTracker(memory_store=store)

# 记录一次 Agent 预测结果
tracker.record_outcome(
    agent_name="master.buffett",
    predicted_direction="Bullish",
    predicted_score=75,
    predicted_confidence=0.85,
    actual_direction="Bullish",
    actual_price_change_pct=+3.5,
)

# 从 AgentAnalysis 直接记录（便捷包装）
tracker.record_outcome_from_analysis(
    agent_name="master.buffett",
    score=75, confidence=0.85, direction="Bullish",
    actual_direction="Bullish", actual_price_change_pct=+3.5,
)

# 查询信任度画像
report = await tracker.get_trust_report("master.buffett")
# → TrustReport(agent_name, metrics, summary, is_reliable)

# 持久化到 MemoryStore
await tracker.flush()
```

### 核心指标

| 指标 | 说明 | 产品含义 |
|:-----|:-----|:---------|
| win_rate | 方向准确率 | 谁更靠谱 |
| bullish/bearish/neutral_win_rate | 各方向准确率 | 偏哪个方向的判断更准 |
| brier_score | 置信度校准（0=完美） | 说 90% 置信时实际对了多少 |
| confidence_bias | 置信度偏差 | 过度自信 or 过于保守 |
| optimism_bias | 评分乐观偏差 | 总是评高分但方向不准 |
| calibration_curve | 校准曲线数据 | 可视化用 |
| trend_direction | 趋势（improving/declining/stable） | 越用越好还是退化 |

### 关键设计决策

- **零 LLM 成本**：纯数学统计，不消耗推理预算
- **数据不足时安全降级**：< 5 样本 → 默认值，5-20 温和加权，> 20 全量
- **持久化**：namespace `("trust", "debate")` 下的 MemoryStore，去重写入
- **compute_weight_factor()**：供 M4 aggregate 使用的权重因子函数（0.5-1.5）
- **与 M2 关系**：M2 定性（为什么错），M3 定量（谁的预测更可靠）

### 文件

| 文件 | 说明 |
|:-----|:------|
| `src/debate/trust.py` | TrustTracker + AgentOutcome/TrustMetrics/TrustReport |
| `tests/test_debate_trust.py` | 54 测试（模型/记录/统计/校准/权重/持久化/边界） |

## M4 动态权重

> **定位**：根据 M3 TrustTracker 的历史准确率自动调整 aggregate 投票权重。
> M4 是 M3 信任度评分在决策聚合环节的应用。

### 设计

```
M3 TrustTracker.get_trust_report("master.buffett")
  → compute_weight_factor(metrics) → 0.5-1.5
  ↓
DebateOrchestrator(enable_trust=True).run(input)
  → 预加载所有大师的信任度因子到 DebateState.trust_weight_factors
  ↓
aggregate_node
  → 读取 trust_weight_factors
  → 与 D3 weight_suggestions 相乘得到 combined_factor
  → weighted_score 计算应用 combined_factor
  ↓
VoteSummary.trust_weight_factors 记录
```

### API 变更

#### `DebateOrchestrator.__init__()` 新增参数

| 参数 | 类型 | 默认值 | 说明 |
|:-----|:-----|:------:|:-----|
| `enable_trust` | `bool` | `False` | 启用 M4 动态权重。需同时提供 `memory_store` |

#### `DebateState` 新增字段

| 字段 | 类型 | 说明 |
|:-----|:-----|:------|
| `trust_weight_factors` | `dict` | `{agent_name: factor}`，compute_weight_factor 预计算值 |

#### `VoteSummary` 新增字段

| 字段 | 类型 | 说明 |
|:-----|:-----|:------|
| `trust_weight_factors` | `dict[str, float]` | 本次聚合使用的信任度因子（用于回溯/展示） |

### 权重叠加逻辑

```
combined_factor = D3_weight_suggestion × M4_trust_factor
                  1.0 (默认)         1.0 (默认)

weighted_score = Σ(score × confidence × combined_factor)
               / Σ(confidence × combined_factor)
```

### 安全降级

- `memory_store` 不提供 → 无信任度查询，因子全为 1.0
- 某 Agent 无信任度记录 → 该 Agent 因子为 1.0
- `TrustTracker.get_trust_report()` 返回 `is_reliable=False` → 不设因子（1.0）
- 所有异常在 `try/except` 内吞噬，不阻塞辩论流程

### 文件

| 文件 | 说明 |
|:-----|:------|
| `src/debate/orchestrator.py` | aggregate_node 叠加信任度因子（10 行变更） |
| `src/debate/models.py` | VoteSummary.trust_weight_factors 新增 |
| `tests/test_debate_m4_dynamic_weight.py` | 10 测试（权重/叠加/序列化/降级） |

## 下一步

| 优先级 | 说明 | 工作量 | 状态 |
|:------:|:-----|:------:|:----:|
| 🟡 P1 | ~~**回测→辩论桥接** — TradePlan → TradeRecord 适配器~~ | 中 | ✅ |
| 🟡 P1 | ~~**M3 信任度评分** — Agent 输出 vs 实际结果追踪~~ | 中 | ✅ 已实现 |
| 🟡 P2 | ~~**M4 动态权重** — 根据历史准确率自动调整 aggregate 权重~~ | 小 | ✅ |
| ⬇️ P2 | 多轮对抗辩论（当前单轮，考虑扩展到多轮） | 中 | ⬜ |
| ⬇️ P2 | **C1 简报分区输出** — format_market_brief 按区块分区 | 中 | ⬜ |

---

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 战线分析 / 竞品对比 / 设计决策背景
> **最后更新**：2026-06-16（M4 动态权重完成）

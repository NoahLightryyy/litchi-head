---
department: 辩论引擎部
codebase: src/debate/
last_updated: 2026-07-23
---

# 🎯 辩论引擎部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| 9 层辩论链路（data→analyst→review→vote→risk→trader→pm→reflection→summary） | ✅ | LangGraph StateGraph 编排 |
| D1 交叉审阅（赞同+补充+异议三段式） | ✅ | 大师间双向三段式互评 |
| D2 强制输出方向 | ✅ | 按市场环境约束辩论方向 |
| D3 独立评审 | ✅ | 第三方独立评判 |
| D4 加权投票汇总 | ✅ | 含 M3 信任度因子叠加 |
| M1 历史决策注入 | ✅ | 前次辩论决策参考 |
| M2 反思闭环（reflection.py） | ✅ | Record→Compare→Reflect→Inject |
| M3 信任度评分（trust.py） | ✅ | 759 行信任度追踪系统 |
| M4 动态权重 | ✅ | 信任度→投票权重映射 |
| R1 三层风控辩论（risk/） | ✅ | src/risk/ 独立模块 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 辩论编排器（test_orchestrator） | 17 |
| D1 交叉审阅（test_d1_cross_review） | 25（✅ DP-002 三段式改造） |
| D2 方向约束（test_d2_direction） | 31 |
| D3 独立评审（test_d3_independent） | 23 |
| M1 历史注入（test_m1_history） | 22 |
| D4 投票扩展（test_d4_vote） | 15 |
| 信任度（test_trust） | 54 |
| M4 动态权重（test_m4_dynamic） | 10 |
| **辩论模块合计** | **235** |

### 关键指标

- LLM 调用/辩论：~12-15 次（目标 ≤ 8 次）
- 全链路耗时含 LLM：~20-30s
- 置信度量化：全部输出带评分 + 置信度

---

## 开放债务

| ID | 描述 | 优先级 | 预估 |
|:---|:-----|:------:|:----:|
| TD-018 | 编排层成本优化 — 9 层链路无短路，~15 次 LLM 调用 | 🟡 | 1d |
| TD-017 | 缺少反思/学习闭环（M2 交易后反思） | 🟢 | 2d |

### 文件大小超标

| 文件 | 行数 | 红线 | 行动 |
|:-----|:----:|:----:|:-----|
| `orchestrator.py` | **1622** | 800 | 🔴 需拆分（计划见 STANDARDS.md） |
| `trust.py` | **759** | 800 | 🟡 接近红线 |

---

## 下一步优先级

### 现有债务

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🔴 | **拆分 orchestrator.py**（1622→800）— 按节点拆分到 `orchestrator/nodes/` 目录 | 无 |
| 2 🟡 | TD-018 成本优化 — 短路优化、层合并、模型分层 | 无 |

### 基本面深度（FD 系列，2026-07-23 更新）

> FD-001 全链路已完成：数据部 FD-001a~e（数据模型→Provider→AKShare→Collector→简报格式化）
> + 辩论部 FD-001f~g（辩论注入 + 分析师增强）。

| FD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **FD-001f** 🥇 | **辩论注入财务数据** — `collect_data_node` 调用 `DataCollector.get_financials()`，存入 `market_data["financials"]` + 传入 `format_market_brief()` | ✅ | 数据部 FD-001e | ~1h |
| **FD-001g** 🥇 | **基本面分析师增强** — 分析师通过 `market_data["brief"]` 自动消费含真实财务数据的简报（基本面分析师 prompt 中的 ROE/利润率/负债率已有真实数据可分析） | ✅ | FD-001f | ~1h |
| **FD-001h** 🥇 | **大师知识过滤器扩展** — 巴菲特、格雷厄姆直接接收财务指标；林奇、达利欧通过分析师报告间接使用 | ⬜ **待办** | FD-001g | ~2h |

### 数据流变更（确认）

```
collect_data_node（已增强 ✅）
  ├── 行情数据（已有）
  ├── K 线数据（已有）
  ├── 新闻数据（已有）
  └── 财务数据 ✅ ← DataCollector.get_financials(code)
       ↓
  market_data["financials"] = list[FinancialMetrics]（结构化数据）
       ↓
  format_market_brief(financials=...) → fundamentals 区段填充真实数据
       ↓
analyst_round
  ├── fundamental 分析师 ← 真实财务数据（已非占位符 ✅）
  ├── technical (不变)
  ├── sentiment (不变)
  └── macro (不变)
       ↓
master_round（所有大师看到更高质量的分析师报告）
  ├── 巴菲特 ← 关注 ROE/自由现金流/负债率（直接从分析师报告吸收）
  ├── 格雷厄姆 ← 关注 PB/PE/净运营资本
  ├── 林奇 ← 关注 PEG/营收增长趋势
  └── 其余大师 ← 通过分析师报告间接获益
```

> **FD-001g 已达成**：`analysts.py` 中基本面分析师的 prompt 原已有 ROE/利润率/负债率 分析框架，
> 此前因"暂无基本面数据"占位符无数据可分析；现在 `format_market_brief()` 输出含真实 6 维度财务数据，
> 随 `market_data["brief"]` 注入分析师 prompt，且不需要修改 analyst prompt 本身。
> 待完善：**FD-001h 大师知识过滤器** — 让特定大师直接从结构化 `FinancialMetrics` 获取数据（如巴菲特看 ROE/格雷厄姆看 PB）。

> **背景**：M3 TrustTracker 有 `record_outcome()` API 但**从未被任何代码实际调用**，导致 M4 动态权重长期无数据可依赖。你需要"结果参数回调相关策略"——一个统一的事件分发机制。
> 完整方案见 [ROADMAP.md RC 轨道](../../../00-overview/ROADMAP.md#rc-结果回调轨道2026-06-23-新增--规划阶段)。

| RC | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **RC-002** ✅ | **M3-EXT 按板块信任度校准** — `AgentOutcome.sector` 新增字段 + TrustTracker 按板块胜率 + `m3_ext` 回调 + `reflect_on_decision()` 实际结果 dispatch 已完成 | 记忆系统部 RC-001 核心引擎 | 已完成 |
| **RC-005** 🥈 | **CALIBRATE 置信度校准** — Brier score 过高时自动注入校准提示或降低置信度贡献权重 | RC-002 | ~1h |
| **RC-006** 🥉 | **STRAT-ROUTE 策略路由** — 追踪每位大师在不同市场条件下的胜率，持续不及格时自动降级 | RC-002 | ~2h |

**关键变更**：

```python
# src/debate/trust.py — AgentOutcome 新增 sector 字段
class AgentOutcome(BaseModel):
    ...
    sector: str = ""  # 🆕 板块标识（如 "食品饮料", "新能源"）

# compute_weight_factor() 新增 sector 参数
def compute_weight_factor(metrics: AgentTrustMetrics, sector: str = "") -> float:
    # 提供 sector 时使用按板块胜率
    if sector and metrics.sector_win_rates.get(sector):
        win_rate = metrics.sector_win_rates[sector]
    else:
        win_rate = metrics.win_rate
    ...

# src/debate/orchestrator.py — reflect_on_decision() 收到实际结果后 dispatch
await self.callback_engine.dispatch(
    CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
    context={
        "actual_outcome": actual_outcome,
        "agent_analyses": decision["agent_analyses"],
    },
    source="debate.reflect_on_decision",
)
```

**2026-07-10/13 落地状态**：
- `src/debate/trust.py`：`AgentOutcome.sector`、`AgentTrustMetrics.sector_win_rates`、`sector_sample_counts` 已上线。
- `compute_weight_factor(metrics, sector=...)`：板块样本数达到可靠阈值时使用板块胜率，否则回退总体胜率。
- `src/callback/callbacks/m3_ext.py`：新增 `ACTUAL_OUTCOME_RECEIVED` 事件回调，将 `agent_analyses + actual_outcome` 写入 TrustTracker。
- `src/debate/orchestrator.py`：`enable_trust=True` 时自动注册 M3-EXT；`reflect_on_decision()` 收到 `ActualOutcome` 后 dispatch 实际结果事件。
- `tests/test_debate/test_trust.py` + `tests/test_callback/test_m3_ext.py`：覆盖按板块统计、板块权重、事件写入、失败分析跳过、缺字段显式失败。
- 未完成边界：复盘看板、用户行为追踪、风控自适应仍需 RC-003/R4/RC-004 接入。

### 基本面深度下放任务（⬜ 待辩论引擎部）

| FD | 事项 | 状态 | 依赖 | 预估 |
|:--:|:-----|:----:|:----|:----:|
| **FD-001h** 🥇 | **大师知识过滤器扩展** — 巴菲特、格雷厄姆直接接收财务指标；林奇、达利欧通过分析师报告间接使用 | ⬜ **待办** | FD-001g | ~2h |

### 数据流变更

```
collect_data_node（已增强）
  ├── 行情数据（已有）
  ├── K 线数据（已有）
  ├── 新闻数据（已有）
  └── 财务数据 ✅ ← DataCollector.get_financials(code)
       ↓
  market_data["financials"] = list[FinancialMetrics]（结构化数据）
       ↓
  format_market_brief(financials=...) → fundamentals 区段填充真实数据
       ↓
analyst_round
  ├── fundamental 分析师 ← 真实财务数据（已非占位符）
  ├── technical (不变)
  ├── sentiment (不变)
  └── macro (不变)
       ↓
master_round（所有大师看到更高质量的分析师报告）
  ├── 巴菲特 ← 关注 ROE/自由现金流/负债率（直接从分析师报告吸收）
  ├── 格雷厄姆 ← 关注 PB/PE/净运营资本
  ├── 林奇 ← 关注 PEG/营收增长趋势
  └── 其余大师 ← 通过分析师报告间接获益
```

> **FD-001g 已达成**：`analysts.py` prompt 原已分析框架，无需修改 prompt 本身 ——
> `format_market_brief()` 输出的 6 维度财务数据随 `market_data["brief"]` 自动注入所有分析师。
> 待办：**FD-001h** 让特定大师直接从结构化 `FinancialMetrics` 获取数据。

### 用户经验反馈闭环（UI 系列，2026-06-23 新增 — 架构第9层）

> 完整方案见 [USER_FEEDBACK_LOOP.md](../../02-requirements/USER_FEEDBACK_LOOP.md)。
> 辩论引擎部在闭环中负责：M2 反思注入升级 + RC-002 M3-EXT + RC-005 CALIBRATE + RC-006 STRAT-ROUTE。

| UI | 事项 | 依赖 | 预估 |
|:--:|:-----|:----|:----:|
| **UI-1a** 🥇 | **RC-002 M3-EXT 按板块信任度校准** — AgentOutcome.sector + TrustTracker 按板块胜率 | RC-001 核心引擎 | ~2h |
| **UI-1b** 🥇 | **M2 反思注入升级** — 加入用户行为偏差维度（用户系统性逆 AI 操作模式） | RC-003 用户行为数据 | ~2h |
| **UI-2a** 🥈 | **RC-005 CALIBRATE 置信度校准** — Brier score 过高时自动注入校准乘数 | UI-1a | ~1h |
| **UI-4a** 🥉 | **RC-006 STRAT-ROUTE 策略路由** — 按市场条件追踪大师胜率、自动降级 | UI-1a | ~2h |

| DP | 事项 | 预估 |
|:--:|:-----|:----:|
| **DP-002** 🥇 | **D1 同侪审阅** — prompt 从"反驳"改为"赞同+补充+异议"三段式审阅，测试验证输出结构变化但无回归 | ✅ 已完成 |
| **DP-003** 🥇 | **偏斜公示** — D4 聚合后统计正面/负面观点比例，输出偏斜度（`BiasReport`）供前端消费 | ~1h |
| **DP-004** 🥇 | **TrustTracker 旋钮扩展** — 增加 `发言顺序权重`、`参与资格阈值`、`置信度校准系数` 三种新旋钮，全用公式计算不经过 LLM | ~2h |
| **DP-006** 🥈 | **镜子反思** — 辩论结束后产出一份历史对比（上次类似市况谁的判断准），展示给用户看，不自动注入 | ~2h |
| **DP-007** 🥈 | **信息隔离** — StateGraph 每层结束后裁剪 state，只保留该层的 Pydantic 结构化 model，删除原始 prompt 和中间结果 | ~2h |

### DP-003 偏斜度输出接口

```python
# D4 聚合后新增
@dataclass
class BiasReport:
    positive_count: int          # 正面观点数
    negative_count: int          # 负面观点数
    buy_ratio: float             # 买入建议比例
    sell_ratio: float            # 卖出建议比例
    hold_ratio: float            # 持有建议比例
    overall_bias: float          # 总体偏斜度（正=偏乐观，负=偏悲观）
    historical_avg_bias: float   # 历史平均偏斜度
```

### 关联文件

| 文件 | 说明 |
|:-----|:------|
| `src/debate/trust.py` | 759 行 → 扩展旋钮（DP-004） |
| `src/debate/orchestrator.py` | 1622 行 → DP-002 修改 review prompt 为三段式 |
| `src/debate/models.py` | 368 行 → 加 `BiasReport`、`MirrorReport` |
| `src/debate/orchestrator.py` | 1622 行 → state 裁剪（DP-007）

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/debate/orchestrator.py` | 1622 | 🔴 编排器主体（需拆分） |
| `src/debate/trust.py` | 759 | 🟡 信任度评分引擎 |
| `src/debate/models.py` | 368 | 辩论数据模型（D1-D4 + M1-M4） |
| `src/debate/reflection.py` | 345 | M2 反思闭环 |
| `src/debate/analysts.py` | 135 | 大师分析师 Prompt |
| `src/risk/orchestrator.py` | 488 | 风控辩论编排 |
| `src/risk/profiles.py` | 180 | 风险画像配置 |
| `docs/06-departments/02-debate-engine/ROLE.md` | — | 👤 辩论引擎部角色定义 |
| `docs/06-departments/02-debate-engine/STANDARDS.md` | — | 📐 辩论引擎部技术规范 |

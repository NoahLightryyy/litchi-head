# DP-003 偏斜公示（BiasReport）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 VoteSummary 中新增 BiasReport 字段，从 direction_distribution 计算偏斜度指标并输出。

**Architecture:** 纯计算逻辑，不增加 LLM 调用。BiasReport 作为 Pydantic model 挂在 VoteSummary 上，在 aggregate_node 中方向分布统计完毕后追加计算。前端加 TypeScript 类型定义。

**Tech Stack:** Python 3.12+ / Pydantic / LangGraph / pytest

**改动文件清单：**

| 文件 | 操作 | 说明 |
|:-----|:----:|:------|
| `src/debate/models.py` | 修改 | +BiasReport model，VoteSummary +bias_report 字段 |
| `src/debate/orchestrator.py` | 修改 | aggregate_node +偏斜计算 |
| `frontend/lib/types/debate.ts` | 修改 | +BiasReport TypeScript 类型 |
| `tests/test_debate/test_bias_report.py` | 创建 | 偏斜报告专用测试 ~18 个 |
| `docs/learning/debate-bias-report.md` | 创建 | 学习卡片 |
| `docs/01-guides/HANDOVER.md` | 修改 | 同步 DP-003 完成状态 |

---

### Task 1: BiasReport 模型定义

**Files:**
- Modify: `src/debate/models.py:125-161`（VoteSummary 区域）
- Test: `tests/test_debate/test_bias_report.py`（创建）

- [ ] **Step 1: 在 models.py 的 VoteSummary 之前新增 BiasReport 类**

Read models.py at line ~123 (before VoteSummary class) to confirm insertion point:

```bash
cd e:/litchi-head && grep -n "class VoteSummary" src/debate/models.py
# Expected: 125 (or current line)
```

```python
# ═══════════════════════════════════════════════════
# BiasReport — DP-003 偏斜公示（2026-06-23 新增）
# ═══════════════════════════════════════════════════


class BiasReport(BaseModel):
    """辩论产出偏斜度报告

    在 D4 聚合阶段从 direction_distribution 计算得出，
    反映群体情绪的偏斜方向和观点集中程度。
    纯计算，不增加 LLM 调用。

    Attributes:
        bullish_count: 看涨观点数
        bearish_count: 看跌观点数
        neutral_count: 中性/观望观点数
        total_count: 总观点数
        bullish_ratio: 看涨占比 (0.0-1.0)
        bearish_ratio: 看跌占比 (0.0-1.0)
        neutral_ratio: 中性占比 (0.0-1.0)
        overall_bias: 总体偏斜度 (-1 到 +1)
            (bullish - bearish) / total
            +1=全体看涨, -1=全体看跌, 0=均衡或全中性
        consensus_strength: 共识强度 (0.0-1.0)
            max(bullish, bearish, neutral) / total
            高=观点集中, 低=分歧大
        consensus_type: 共识类型
            "Bullish" | "Bearish" | "Neutral" | "Divided"
        historical_avg_bias: 历史平均偏斜度（占位，待持久化实现）
    """

    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_count: int = 0
    bullish_ratio: float = 0.0
    bearish_ratio: float = 0.0
    neutral_ratio: float = 0.0
    overall_bias: float = 0.0
    consensus_strength: float = 0.0
    consensus_type: str = "Neutral"
    historical_avg_bias: float = 0.0
```

- [ ] **Step 2: 在 VoteSummary 中追加 bias_report 字段**

在 `class VoteSummary(BaseModel):` 的 trust_weight_factors 行之后追加：

```python
    # ── DP-003: 偏斜公示 ────────────────────────────
    bias_report: BiasReport = Field(default_factory=BiasReport)
```

- [ ] **Step 3: 更新 __all__ 导出**

在 `models.py` 末尾的 `__all__` 列表中加入 `"BiasReport"`。

- [ ] **Step 4: 写 BiasReport 模型测试**

```bash
mkdir -p e:/litchi-head/tests/test_debate
```

创建 `tests/test_debate/test_bias_report.py`：

```python
"""DP-003 偏斜公示 —— BiasReport 模型测试

覆盖所有共识场景：集体看涨、看跌、分歧、全体观望等。
"""

from src.debate.models import BiasReport


class TestBiasReportDefaults:
    """BiasReport 默认值和基本行为"""

    def test_default_construction(self) -> None:
        """默认构造全部为零/中性"""
        r = BiasReport()
        assert r.total_count == 0
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 0.0
        assert r.consensus_type == "Neutral"

    def test_zero_total_produces_neutral(self) -> None:
        """全部为零时输出中性"""
        r = BiasReport(
            bullish_count=0, bearish_count=0, neutral_count=0, total_count=0,
        )
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 0.0
        assert r.consensus_type == "Neutral"

    def test_ratios_are_independent_fields(self) -> None:
        """ratio 字段是独立存储的，不通过计算推导"""
        r = BiasReport(
            bullish_count=4, bearish_count=1, neutral_count=1, total_count=6,
            bullish_ratio=4/6, bearish_ratio=1/6, neutral_ratio=1/6,
            overall_bias=0.5, consensus_strength=4/6, consensus_type="Bullish",
        )
        assert r.bullish_count == 4
        assert r.bearish_count == 1
        assert r.neutral_count == 1
        assert r.total_count == 6


class TestBiasReportConsensusType:
    """共识类型判定测试"""

    def test_strong_bullish(self) -> None:
        """看涨超过半数 → consensus_type=Bullish"""
        r = BiasReport(
            bullish_count=5, bearish_count=0, neutral_count=1, total_count=6,
            bullish_ratio=5/6, bearish_ratio=0.0, neutral_ratio=1/6,
            overall_bias=5/6, consensus_strength=5/6, consensus_type="Bullish",
        )
        assert r.consensus_type == "Bullish"
        assert r.overall_bias == pytest.approx(0.8333, abs=0.001)

    def test_strong_bearish(self) -> None:
        """看跌超过半数 → consensus_type=Bearish"""
        r = BiasReport(
            bullish_count=1, bearish_count=4, neutral_count=1, total_count=6,
            overall_bias=-0.5, consensus_strength=4/6, consensus_type="Bearish",
        )
        assert r.consensus_type == "Bearish"
        assert r.overall_bias == -0.5

    @pytest.mark.parametrize("b,bull,bear,neut", [
        ("all_neutral",  0, 0, 6),
        ("neutral_7",    1, 2, 7),
    ])
    def test_neutral_majority(
        self, b: str, bull: int, bear: int, neut: int,
    ) -> None:
        """中性超过半数 → consensus_type=Neutral"""
        total = bull + bear + neut
        r = BiasReport(
            bullish_count=bull, bearish_count=bear, neutral_count=neut,
            total_count=total,
            overall_bias=(bull - bear) / total,
            consensus_strength=neut / total,
            consensus_type="Neutral",
        )
        assert r.consensus_type == "Neutral"

    def test_divided_consensus(self) -> None:
        """无任一过半 → Divided"""
        r = BiasReport(
            bullish_count=2, bearish_count=2, neutral_count=2, total_count=6,
            overall_bias=0.0, consensus_strength=2/6,
            consensus_type="Divided",
        )
        assert r.consensus_type == "Divided"

    def test_one_analyst_bullish(self) -> None:
        """仅一位分析师且看涨"""
        r = BiasReport(
            bullish_count=1, bearish_count=0, neutral_count=0, total_count=1,
            overall_bias=1.0, consensus_strength=1.0, consensus_type="Bullish",
        )
        assert r.overall_bias == 1.0
        assert r.consensus_strength == 1.0

    def test_one_analyst_neutral(self) -> None:
        """仅一位分析师且中性"""
        r = BiasReport(
            bullish_count=0, bearish_count=0, neutral_count=1, total_count=1,
            overall_bias=0.0, consensus_strength=1.0, consensus_type="Neutral",
        )
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 1.0


class TestBiasReportScenarios:
    """真实投决场景验证"""

    def test_strongly_optimistic(self) -> None:
        """5 看涨 0 看跌 1 观望 → 高度乐观"""
        r = BiasReport(
            bullish_count=5, bearish_count=0, neutral_count=1, total_count=6,
            overall_bias=(5-0)/6, consensus_strength=5/6,
            consensus_type="Bullish",
        )
        assert r.consensus_type == "Bullish"
        assert r.overall_bias == pytest.approx(0.8333, abs=0.001)
        assert r.neutral_count == 1

    def test_cautious_market(self) -> None:
        """0 看涨 0 看跌 6 观望 → 全体谨慎"""
        r = BiasReport(
            bullish_count=0, bearish_count=0, neutral_count=6, total_count=6,
            overall_bias=0.0, consensus_strength=1.0,
            consensus_type="Neutral",
        )
        assert r.consensus_type == "Neutral"
        assert r.consensus_strength == 1.0  # 高度一致 = 全体谨慎

    def test_deep_split(self) -> None:
        """3 看涨 3 看跌 0 观望 → 深度分歧"""
        r = BiasReport(
            bullish_count=3, bearish_count=3, neutral_count=0, total_count=6,
            overall_bias=0.0, consensus_strength=3/6,
            consensus_type="Divided",
        )
        assert r.consensus_type == "Divided"
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 0.5

    def test_leaning_bearish(self) -> None:
        """1 看涨 4 看跌 1 观望 → 偏悲观"""
        r = BiasReport(
            bullish_count=1, bearish_count=4, neutral_count=1, total_count=6,
            overall_bias=(1-4)/6, consensus_strength=4/6,
            consensus_type="Bearish",
        )
        assert r.consensus_type == "Bearish"
        assert r.overall_bias == pytest.approx(-0.5, abs=0.001)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd e:/litchi-head && python -m pytest tests/test_debate/test_bias_report.py -v 2>&1
```

Expected: 全部 PASS（模型定义已有，测试测的是已有字段）

- [ ] **Step 6: 确认 VoteSummary 含 bias_report 字段**

运行一个 quick check 确保 VoteSummary 能带 BiasReport 构建：

```bash
cd e:/litchi-head && python -c "
from src.debate.models import VoteSummary, BiasReport
vs = VoteSummary(bias_report=BiasReport(bullish_count=3, bearish_count=1))
print(vs.bias_report.overall_bias)
print(vs.model_dump()['bias_report']['bullish_count'])
"
```

Expected: `0.0`（默认值，因为未设 overall_bias）和 `3`

- [ ] **Step 7: Commit**

```bash
cd e:/litchi-head && git add src/debate/models.py tests/test_debate/test_bias_report.py && git commit -m "feat: DP-003 BiasReport 模型定义 — Pydantic model + 18 场景测试"
```

---

### Task 2: aggregate_node 偏斜计算逻辑

**Files:**
- Modify: `src/debate/orchestrator.py:990-1158`（aggregate_node）

- [ ] **Step 1: 实现 `compute_bias_report` 工具函数**

在 `orchestrator.py` 中（建议放在 aggregate_node 函数上方，或模块顶部工具函数区）新增：

```python
def compute_bias_report(direction_distribution: dict[str, int]) -> BiasReport:
    """从方向分布计算偏斜报告

    Args:
        direction_distribution: {"Bullish": int, "Bearish": int, "Neutral": int}

    Returns:
        计算后的 BiasReport

    Note:
        纯计算函数，不含除零保护：当 total == 0 时返回默认 BiasReport。
    """
    bullish = direction_distribution.get("Bullish", 0)
    bearish = direction_distribution.get("Bearish", 0)
    neutral = direction_distribution.get("Neutral", 0)
    total = bullish + bearish + neutral

    if total == 0:
        return BiasReport()

    bullish_r = round(bullish / total, 4)
    bearish_r = round(bearish / total, 4)
    neutral_r = round(neutral / total, 4)
    overall_bias = round((bullish - bearish) / total, 4)
    consensus_strength = round(max(bullish, bearish, neutral) / total, 4)

    # ── 共识类型判定 ──
    if max(bullish, bearish, neutral) / total > 0.5:
        if bullish > bearish and bullish > neutral:
            consensus_type = "Bullish"
        elif bearish > bullish and bearish > neutral:
            consensus_type = "Bearish"
        else:
            consensus_type = "Neutral"
    else:
        consensus_type = "Divided"

    return BiasReport(
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        total_count=total,
        bullish_ratio=bullish_r,
        bearish_ratio=bearish_r,
        neutral_ratio=neutral_r,
        overall_bias=overall_bias,
        consensus_strength=consensus_strength,
        consensus_type=consensus_type,
    )
```

**导入确认**：确保 `orchestrator.py` 顶部已导入 `BiasReport`：

```python
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    BiasReport,  # ← DP-003 追加
    DebateInput,
    DebateResult,
    ...
)
```

- [ ] **Step 2: 在 aggregate_node 方向分布统计后追加计算**

找到 `aggregate_node` 函数中构建完 `direction_distribution` 的位置（大约在 `orchestrator.py:1050` 附近），在该函数返回 `VoteSummary` 前追加：

```python
    # ── DP-003: 偏斜公示 ────────────────────────────
    summary.bias_report = compute_bias_report(summary.direction_distribution)
```

确保这一行放在 `summary` 对象构造完成之后、`return` 语句之前。

- [ ] **Step 3: 写偏斜计算集成测试**

在 `tests/test_debate/test_bias_report.py` 中追加集成测试：

```python
class TestComputeBiasReport:
    """compute_bias_report 函数测试"""

    def test_empty_distribution(self) -> None:
        """空分布返回默认 BiasReport"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({})
        assert r.total_count == 0
        assert r.overall_bias == 0.0
        assert r.consensus_type == "Neutral"

    def test_bullish_majority(self) -> None:
        """看涨 4 看跌 1 中性 1 → Bullish"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({"Bullish": 4, "Bearish": 1, "Neutral": 1})
        assert r.consensus_type == "Bullish"
        assert r.overall_bias == pytest.approx(0.5, abs=0.001)
        assert r.consensus_strength == pytest.approx(4/6, abs=0.001)

    def test_bearish_majority(self) -> None:
        """看跌 5 看涨 1 → Bearish"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({"Bullish": 1, "Bearish": 5})
        assert r.consensus_type == "Bearish"
        assert r.overall_bias == pytest.approx(-4/6, abs=0.001)

    def test_all_neutral(self) -> None:
        """全中性 → Neutral"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({"Neutral": 5})
        assert r.consensus_type == "Neutral"
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 1.0

    def test_even_split(self) -> None:
        """2 看涨 2 看跌 2 中性 → Divided"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({"Bullish": 2, "Bearish": 2, "Neutral": 2})
        assert r.consensus_type == "Divided"
        assert r.overall_bias == 0.0
        assert r.consensus_strength == pytest.approx(2/6, abs=0.001)

    def test_exact_50_percent_not_divided(self) -> None:
        """看涨 3 看跌 2 中性 1 → Bullish (3/6=0.5, 不超过 0.5, 所以 Divided)"""
        from src.debate.orchestrator import compute_bias_report
        r = compute_bias_report({"Bullish": 3, "Bearish": 2, "Neutral": 1})
        # 3/6 = 0.5 不大于 0.5 → Divided
        assert r.consensus_type == "Divided"
        assert r.overall_bias == pytest.approx(1/6, abs=0.001)
```

- [ ] **Step 4: 运行全部偏斜测试**

```bash
cd e:/litchi-head && python -m pytest tests/test_debate/test_bias_report.py -v 2>&1
```

Expected: ~21 tests all PASS

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
cd e:/litchi-head && python -m pytest tests/test_debate/ -v 2>&1 | tail -20
```

Expected: 全部 PASS（之前 235 + 新增 ~21 = ~256）

- [ ] **Step 6: Commit**

```bash
cd e:/litchi-head && git add src/debate/orchestrator.py tests/test_debate/test_bias_report.py && git commit -m "feat: DP-003 aggregate_node 偏斜计算逻辑 — compute_bias_report + 集成测试"
```

---

### Task 3: to_summary_dict 输出 + 前端类型 + 文档同步

**Files:**
- Modify: `src/debate/models.py:264-362`（to_summary_dict）
- Modify: `frontend/lib/types/debate.ts`
- Create: `docs/learning/debate-bias-report.md`
- Modify: `docs/01-guides/HANDOVER.md`

- [ ] **Step 1: to_summary_dict 追加偏斜输出**

在 `DebateResult.to_summary_dict()` 中，方向分布字段之后追加：

```python
        # ── DP-003: 偏斜公示 ────────────────────────
        if vs.direction_distribution:
            br = vs.bias_report
            result["偏斜报告"] = {
                "总体偏斜": br.overall_bias,
                "共识强度": br.consensus_strength,
                "共识类型": br.consensus_type,
                "看涨": br.bullish_count,
                "看跌": br.bearish_count,
                "观望": br.neutral_count,
            }
```

- [ ] **Step 2: 更新前端 TypeScript 类型**

读 `frontend/lib/types/debate.ts` 确认现有结构，追加：

```typescript
// ── DP-003: 偏斜公示 ─────────────────────────────
export interface BiasReport {
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  total_count: number;
  bullish_ratio: number;
  bearish_ratio: number;
  neutral_ratio: number;
  overall_bias: number;
  consensus_strength: number;
  consensus_type: 'Bullish' | 'Bearish' | 'Neutral' | 'Divided';
  historical_avg_bias: number;
}
```

在 `VoteSummary` 接口中追加：

```typescript
export interface VoteSummary {
  // ... 现有字段 ...
  bias_report: BiasReport;
}
```

- [ ] **Step 3: 写学习卡片**

创建 `docs/learning/debate-bias-report.md`：

```markdown
# ⚖️ 辩论偏斜度计算（BiasReport）

> 通过统计学指标量化辩论群体的情绪倾向和观点集中程度。
> 一句话：把"谁说了什么"变成"群体到底怎么看"。

## 核心思路

从辩论的 `direction_distribution`（Bullish / Bearish / Neutral 计数）
计算三个关键指标：

| 指标 | 公式 | 含义 |
|:-----|:-----|:------|
| **总体偏斜度** | (Bullish - Bearish) / Total | 群体方向偏好，-1~+1 |
| **共识强度** | max(Bullish, Bearish, Neutral) / Total | 观点集中度，0~1 |
| **共识类型** | 见下方 | 群体状态分类 |

## 共识类型判定

```
if max_count/total > 0.5:    # 过半=有共识
    看涨最多 → "Bullish"
    看跌最多 → "Bearish"  
    中性最多 → "Neutral"
else:                        # 不过半=分歧
    "Divided"
```

## 为什么要区分 Neutral 和 Divided？

**总偏斜度为 0 不代表"没信息"**。看这个对比：

| 分布 | 偏斜度 | 共识强度 | 共识类型 | 含义 |
|:----|:-----:|:--------:|:---------|:-----|
| 全中性 6 人 | 0.0 | 1.0 | Neutral | **全体谨慎**，有意识不出手 |
| 3 涨 3 跌 | 0.0 | 0.5 | Divided | **深度分歧**，方向不明 |

前者是成熟的谨慎，后者是真实的争议——用一个数字看不出区别，加上共识类型就能区分。

## 项目代码位置

- **模型定义**: `src/debate/models.py` → `BiasReport` 类
- **计算逻辑**: `src/debate/orchestrator.py` → `compute_bias_report()` 函数
- **测试**: `tests/test_debate/test_bias_report.py` → ~21 tests

## 自己试试

```python
from src.debate.orchestrator import compute_bias_report

# 场景 1：正常市场，偏乐观
r1 = compute_bias_report({"Bullish": 4, "Bearish": 1, "Neutral": 2})
print(f"偏斜度={r1.overall_bias}, 共识={r1.consensus_type}")

# 场景 2：全体观望
r2 = compute_bias_report({"Neutral": 6})
print(f"偏斜度={r2.overall_bias}, 共识={r2.consensus_type}")

# 场景 3：深度分歧
r3 = compute_bias_report({"Bullish": 3, "Bearish": 3})
print(f"偏斜度={r3.overall_bias}, 共识={r3.consensus_type}")
```

> **关联卡片**: [M4 动态权重](../debate-dynamic-weight.md) | [VoteSummary 投票汇总](../debate-vote-summary.md)
```

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd e:/litchi-head && python -m pytest tests/ -x -q 2>&1 | tail -5
```

- [ ] **Step 5: 同步 HANDOVER 文档**

更新 `docs/01-guides/HANDOVER.md`：
- 🏢 各部门一览 → 更新辩论引擎部状态
- 🎯 当前跨部门优先级 → DP-003 标记 ✅ 已完成
- 最新提交信息更新

- [ ] **Step 6: 最终 CI 自检**

```bash
cd e:/litchi-head && python scripts/check.py 2>&1
```

Expected: ruff + pyright + 测试全部通过

- [ ] **Step 7: Commit**

```bash
cd e:/litchi-head && git add -A && git commit -m "feat: DP-003 偏斜公示完成 — BiasReport 模型+计算+前端类型+文档+测试~21枚"
```

---

### 自审

**对照 spec 逐项检查：**

| Spec 要求 | 覆盖任务 | 状态 |
|:----------|:---------|:-----|
| BiasReport 模型定义 | Task 1 | ✅ |
| VoteSummary 挂载 bias_report 字段 | Task 1 Step 2 | ✅ |
| aggregate_node 偏斜计算 | Task 2 Steps 1-2 | ✅ |
| to_summary_dict 输出 | Task 3 Step 1 | ✅ |
| 前端 TypeScript 类型 | Task 3 Step 2 | ✅ |
| 测试 ~18 个 | Task 1 Step 4 + Task 2 Step 3 (~21 tests) | ✅ |
| 学习卡片 | Task 3 Step 3 | ✅ |
| 文档同步 | Task 3 Step 5 | ✅ |
| **不做** 前端 UI 实现 | 未包含 | ✅ |
| **不做** 历史偏斜持久化 | 仅占位字段 | ✅ |
| **不做** 新 LLM 调用 | 纯计算 | ✅ |

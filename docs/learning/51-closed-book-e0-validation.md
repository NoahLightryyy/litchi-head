# 51｜闭卷评测与两阶段验证

## 一句话

> 先用冻结历史题淘汰明显无效的复杂系统，再用在线影子样本验证真实运行；不要把评测集变成训练集。

---

## 为什么需要它？

### 问题场景

项目已经有多 Agent、辩论、风控、校准和回测指标，但“模块存在”不能证明它们比单 Agent
或简单规则更有价值。如果一上来就建设完整在线实验平台，会继续扩大工程规模；如果边看
100 条历史题的成绩边改 Prompt，又会把正式答案泄漏进系统。

### 它的解法

把验证拆成两段：E0 在 KR-4 前用冻结的 100 条历史时点题做闭卷证伪，只决定停止、扩样
或证据不足；E1 在生产链完成后连续运行 4～8 周影子样本，验证真实数据、成本、恢复与
市场状态。E0 不训练模型，也不允许用测试题调参。

---

## 项目里的真实设计与代码

打开 `docs/superpowers/specs/2026-08-10-e0-validation-checkpoint-design.md`，可以看到 E0
固定比较完整系统、同模型单 Agent、现金、买入持有和 20 日动量，5 日为唯一主周期。

现有能力直接复用：

```python
# src/backtest/metrics.py
def calculate_sharpe(
    daily_returns: list[float],
    risk_free_rate: float = 0.02,
    trading_days: int = 252,
) -> float:
    """计算年化夏普比率。"""


def calculate_max_drawdown(
    equity_curve: list[PortfolioSnapshot],
) -> float:
    """计算最大回撤。"""

# src/debate/trust.py
brier_sum = 0.0
for outcome in outcomes:
    correctness = 1.0 if outcome.is_correct else 0.0
    brier_sum += (outcome.predicted_confidence - correctness) ** 2
brier_score = brier_sum / n if n > 0 else 0.0
```

关键点不是再造指标，而是让所有参赛器读取同一时点证据、保留完整失败分母，并在运行前
冻结样本、代码、模型、Prompt、成本和随机种子。

Task 1 已把这些要求落实为不可变契约：

```python
# src/backtest/e0/models.py
class E0Manifest(_FrozenModel):
    regime_policy: RegimePolicy
    fee_profile: FeeProfile
    position_profile: PositionProfile
    confidence_policy: ConfidencePolicy
    samples: tuple[E0Sample, ...]


class DecisionRecord(_FrozenModel):
    evidence_hash: str
    as_of: datetime
    decision_at: datetime
    status: RunnerStatus
```

正式 `E0Manifest` 在模型边界直接拒绝非 25×4、单股超过 2 条、单日超过 5 条或重复候选；
`DecisionRecord` 拒绝 `as_of > decision_at` 以及与时间差不一致的新鲜度。冻结 JSON 同时拒绝
`NaN`、`Infinity` 和重复 key，避免同一字节在不同解析器中产生不同事实。

---

## 和训练集有什么不同？

| 对比 | 训练/开发集 | E0 正式题集 |
|:-----|:------------|:------------|
| 能否调 Prompt/权重 | 可以 | 不可以 |
| 能否重复看答案优化 | 可以 | 不可以 |
| 目标 | 让系统变好 | 判断当前系统是否值得继续 |
| 结果 | 新版本 | 停止、扩样或证据不足 |

---

## 面试会怎么问

> **Q：为什么不直接用 100 条样本证明 Sharpe 更高？**
>
> A：股票与日期存在相关性，名义 100 条的有效样本量更低。E0 适合发现明显失效、过度
> 自信和架构浪费，不足以证明长期收益稳定。只有冻结方案后扩大到 300～500 条，并完成
> 连续 E1 影子验证，才能逐步增加证据强度。

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_backtest/e0/test_models.py -q`；
2. 在测试 fixture 中把 `DecisionRecord.as_of` 改到 `decision_at` 之后，观察未来证据被拒绝；
3. 把冻结 JSON 改成 `{"price": 10, "price": 11}`，观察重复事实被拒绝；
4. 思考：如果看完结果后把 5 日主周期改成 20 日，这轮实验为什么已经失效？

---

**上一篇：[50｜运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

**下一篇：待后续卡片**

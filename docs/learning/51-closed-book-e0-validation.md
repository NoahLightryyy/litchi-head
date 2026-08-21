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

Task 2 把“冻结”扩展到磁盘：`src/backtest/e0/store.py` 使用同目录临时文件、`fsync` 和
`os.replace` 发布 manifest 与 JSONL；相同记录重放是字节稳定 no-op，不同内容占用同一
决策 key 则失败。`terminal.json` 最后发布，并同时绑定 manifest、decisions、labels、
report JSON 和 Markdown 的哈希；终态后公开追加接口全部拒绝写入。

Task 3 冻结正式题集：`src/backtest/e0/sampling.py` 只读取候选中已经冻结的决策前窗口，
重新计算区间收益和样本标准差年化波动率。分类优先级固定为高波动、上涨、下跌、横盘；
候选先按 ID 排序，再用固定 seed 洗牌，并同时满足每状态 25 条、单股最多 2 条、单日最多
5 条。未使用的合法候选按预注册顺序保存，排除候选保存稳定错误码，不能在看到结果后再
挑替补。

```python
# src/backtest/e0/sampling.py
E0_DECIMAL_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
)

ordered_candidates = tuple(sorted(candidates, key=lambda item: item.candidate_id))
random.Random(random_seed).shuffle(shuffled)
```

这里不仅固定 Decimal 精度，也固定舍入模式和指数范围。否则同一候选在不同调用进程的
全局 Decimal context 下可能跨过分类阈值，使 manifest 不再只由冻结输入决定。采样入口与
manifest 模型边界还会共同拒绝语义重复样本，以及 selected、excluded、replacement 三组
身份冲突。

Task 4 加入三个完全确定性的参照系：`CashRunner`（B0）永远持有现金，`BuyHoldRunner`
（B1）只根据清单中冻结的决策时可成交证明决定是否按统一仓位买入，`Momentum20Runner`
（B3）比较最新收盘价与 20 个交易会话前的收盘价。规则 runner 不产生 Token 或模型成本，
也不读取标签。

```python
# src/backtest/e0/runners.py
if bar_date >= sample.decision_at.date():
    raise E0RunnerEvidenceError("future_bar_forbidden", ...)
if bar_date >= evidence.as_of.date():
    raise E0RunnerEvidenceError("bar_after_evidence_as_of", ...)

if closes[-1] > closes[-21]:
    return LONG
return CASH
```

日 K 线只有日期、没有可证明的完成时刻，因此使用保守边界：必须严格早于 evidence
snapshot 的自然日。这里还直接比较两个正价格，而不先做 Decimal 除法；对于“收益是否大于
零”这个问题两者数学等价，却不会被调用进程的 Decimal 精度把极小正收益舍入成零。

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
4. 运行 `python -m pytest tests/test_backtest/e0/test_store.py -q`，观察删除终态 ledger、
   篡改记录和注入 `os.replace` 失败都会形成可重复的完整性失败；
5. 运行 `python -m pytest tests/test_backtest/e0/test_sampling.py -q`，再尝试切换 Decimal
   rounding mode，观察分类结果仍保持一致；
6. 运行 `python -m pytest tests/test_backtest/e0/test_runners.py -q`，观察快照后的 K 线、
   决策日 K 线、错误实验身份和不足 21 个收盘价都会失败关闭；
7. 思考：如果看完结果后把 5 日主周期改成 20 日，这轮实验为什么已经失效？

---

**上一篇：[50｜运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

**下一篇：待后续卡片**

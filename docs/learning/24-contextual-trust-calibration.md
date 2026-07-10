# 24 按场景校准信任度 — Contextual Trust

## 一句话

> 一个大师“总体靠谱”不代表在每个板块都靠谱；RC-002 让 TrustTracker 按板块记录胜率，避免系统把食品饮料上的成功经验错误套到新能源、银行或科技股上。

---

## 为什么需要它？

### 问题场景

如果只看总体胜率，某个 Agent 可能因为擅长消费股而看起来很强。但它一到半导体就连续误判，总体胜率却还没明显下降。实盘里这会让系统在错误场景里继续给它高权重。

这就是“平均数遮住了场景差异”。投资判断很依赖行业、周期和市场结构，不能只问“这个人整体准不准”，还要问“它在这个场景准不准”。

### 它的解法

RC-002 给 `AgentOutcome` 增加 `sector` 字段，并在 `AgentTrustMetrics` 里计算：

- `sector_win_rates`: 每个板块的方向准确率
- `sector_sample_counts`: 每个板块的样本量

`compute_weight_factor(metrics, sector=...)` 在板块样本数达到可靠阈值时使用板块胜率；样本不足时回退总体胜率，避免小样本误导。

---

## 项目里的真实代码

打开 `src/debate/trust.py`：

```python
sector_groups: dict[str, list[AgentOutcome]] = {}
for outcome in outcomes:
    if outcome.sector:
        sector_groups.setdefault(outcome.sector, []).append(outcome)

sector_win_rates: dict[str, float] = {}
sector_sample_counts: dict[str, int] = {}
for sector, sector_outcomes in sector_groups.items():
    sector_sample_counts[sector] = len(sector_outcomes)
    sector_correct = sum(1 for o in sector_outcomes if o.is_correct)
    sector_win_rates[sector] = round(sector_correct / len(sector_outcomes), 3)
```

再看 `src/callback/callbacks/m3_ext.py`：

```python
tracker.record_outcome_from_analysis(
    agent_name=agent_name,
    direction=_str_field(analysis, {}, "direction") or "Neutral",
    actual_direction=actual_direction,
    actual_price_change_pct=_float_field(actual, "actual_price_change_pct"),
    sector=_str_field(actual, event.context, "sector"),
)
```

第一段负责“怎么算”，第二段负责“结果来了怎么写进去”。这两个合起来，才让回测或真实市场结果进入按板块信任度统计。

---

## 和总体胜率有什么不同？

| 对比 | 总体胜率 | 按场景信任度 |
|:-----|:---------|:-------------|
| 粒度 | 所有股票混在一起 | 按板块/场景拆分 |
| 优点 | 稳定、样本多 | 能发现局部擅长和局部失效 |
| 风险 | 掩盖短板 | 小样本容易误导 |
| 本项目处理 | 作为默认回退 | 样本数达到阈值才启用 |

---

## 面试会怎么问

> **Q: 为什么 sector 样本不足时不直接使用 sector_win_rate？**
>
> A: 因为 1/1 或 2/2 的胜率没有统计可靠性。项目里用 `sector_sample_counts` 控制，板块样本达到阈值才覆盖总体胜率，否则回退总体指标，避免过拟合短期噪声。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_debate/test_trust.py`
2. 找到 `test_sector_weight_uses_sector_win_rate_when_reliable`
3. 把 `sector_sample_counts["食品饮料"]` 从 5 改成 4，看看权重为什么会回退到总体胜率
4. 再打开 `tests/test_callback/test_m3_ext.py`，看 `ACTUAL_OUTCOME_RECEIVED` 事件如何把实际结果写入 TrustTracker

---

**上一篇：[结果回调引擎 — 让结果自动触发系统学习](23-result-callback-engine.md)** ← 链接

**下一篇：待补** ← 链接

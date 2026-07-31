# 40 点时复权：为什么“今天看到的因子”不能改写昨天的判断

## 一句话

> 点时复权不是把价格变得更顺眼，而是只用决策当时已经可得的 RAW 快照和公司行动因子，重建当时真正能看到的价格坐标。

---

## 为什么需要它？

同一家公司后来可能修订分红、配股或送转信息。如果历史回测直接使用今天下载的
最新前复权序列，旧决策会偷偷获得未来才发布的修订，结果看似更准，实际不可复现。

本项目把三个时间/版本同时钉住：

```text
KR-1 RAW snapshot
  ├─ raw_snapshot_id
  ├─ raw_snapshot_as_of
  └─ raw_completed_through

CorporateActionFactor
  ├─ known_at
  ├─ revision
  └─ factor content hash

AdjustedKlineSeries
  └─ as_of
```

算法只选择 `known_at <= as_of` 的因子修订，并要求每根 RAW bar 都不超过 KR-1
已经证明完成的日期。它不凭“现在已经 15:00”猜数据稳定，也不把供应商的前复权
成品当事实。

## 项目里的真实代码

打开 `src/data/kline_adjustment.py`：

```python
if any(bar.trade_date > raw_completed_through for bar in bars):
    raise ValueError("RAW bars exceed the snapshot completion proof")

eligible = [
    factor
    for factor in factors
    if factor.known_at <= as_of and factor.ex_date <= reference_date
]
```

股本事件还保存精确比例与因子来源精度。3:1 拆股的价格因子只能近似写成
`0.33333333`，因此不能要求 Decimal 精确等于 `1/3`；项目用 `Fraction` 对精确
比例和来源声明的半个精度单位做校验，既接受合法舍入，也拒绝 `0.5 / 1.01`
这类方向相反但数值严重错误的组合。

## 三种价格/数量口径

| 字段 | 口径 | 用途 |
|:--|:--|:--|
| OHLC | `adjusted_qfq_asof` | 技术指标与点时比较 |
| volume | `adjusted_qfq_asof` | 股本变化后的可比量能 |
| amount | `raw` | 当日真实成交额事实 |

复权价是数学坐标，不是可成交价格。下单仍必须使用 RAW/实时行情。

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_kline_adjustment.py -q`；
2. 找到因子修订测试，把新版 `known_at` 改到查询 `as_of` 之前；
3. 观察历史价格和组合 `factor_version` 同时变化；
4. 再把 `raw_completed_through` 改到最后一根 bar 之前，确认算法失败关闭。

思考题：如果只保存“qfq”而不保存 RAW 快照 ID、因子内容哈希和 `as_of`，半年后
还能证明当时的 AI 没有看见未来吗？

## 前后链接

- 上一张：[39｜决策 Baseline 与影子验证](39-decision-baseline-shadow-validation.md)
- 下一张：[41｜累计复权因子与公司行动](41-cumulative-factor-vs-corporate-action.md)

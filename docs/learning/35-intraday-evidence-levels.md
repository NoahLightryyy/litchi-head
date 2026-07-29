# 35｜分时证据分级：看见行为，不等于认出账户

> 一句话：L1 分时能可靠描述价格和成交行为，但没有订单生命周期与账户身份时，
> 不能把异常走势直接叫作“主力”或“量化”。

## 三个数据层级

| 层级 | 看得到 | 项目允许输出 |
|:-----|:-------|:-------------|
| L1 分钟行情 | OHLC、成交量、成交额 | VWAP、开盘区间、同期量能、量价事实 |
| Tick / Order Flow | 逐笔成交、买卖方向 | 主动买卖失衡、CVD、疑似拆单 |
| Level-2 / MBO | 委托、撤单、订单编号、深度 | 冰山、补单、快速撤单等行为模式 |

公开 L1 没有账户身份，所以 `src/data/intraday.py` 的
`IntradayBattlefieldSnapshot.attribution_supported` 被固定为 `False`。这不是少做
一个功能，而是防止把推测包装成事实。

## 为什么两个来源一致仍可能一起错

东方财富和腾讯分钟端点都把成交量写成“手”。两边原始数值完全一致，如果只做
数值对账会误以为正确；但成交额除以成交量后，VWAP 会被放大 100 倍。

项目在 `src/data/providers/intraday.py` 先把两源成交量都乘 100 归一化为“股”，
再在 `src/data/intraday_runtime.py` 对已结束分钟做价格、累计量和分钟集合核验。

这说明多源验证有两层：

1. **来源一致性**：两家是否看到同一市场事实；
2. **语义正确性**：单位、时间标签和字段含义是否解释正确。

缺任何一层都可能“两个来源一起错”。

## `FINAL` 与 `PROVISIONAL`

两家端点采用分钟结束标签。比如 14:40:22：

- `14:40` 表示已经结束的分钟；
- `14:41` 表示正在形成的当前分钟。

因此项目保留当前条参与实时 VWAP，但把它标记为 `PROVISIONAL`，提醒下游成交量和
高低价仍会变化。已完成分钟才参加跨源历史对账。

## Relative Volume 为什么暂时为空

“放量”应该比较过去多个交易日的同一时刻，而不是只和上一分钟比较。开盘天然比
午后活跃，简单环比会制造假异常。

项目要求至少 20 个完整交易日的同分钟累计量基线。历史不足时返回：

```text
relative_volume = None
limitations = ["relative_volume_baseline_insufficient"]
```

这比给出一个看似精确但没有基线的倍数更安全。

## 自己试试

1. 打开 `src/data/providers/intraday.py`，找到成交量乘 100 的位置；
2. 打开 `src/data/intraday_runtime.py`，找到 0.01 元与 500 股的对账门槛；
3. 运行 `python -m pytest tests/test_data/test_intraday_evidence.py -q`；
4. 把测试中的腾讯累计量改大 20,100 股，观察信封变成 `complete=False`。

## 前后链接

- 上一张：[34｜实时行情对账：新鲜不等于一致](34-realtime-quote-reconciliation.md)
- 相关决策：[ADR-013 多源证据完整性](../05-decisions/ADR-013-multi-source-evidence.md)

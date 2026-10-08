# 55｜多源汇总不是把两个数字取平均

## 一句话

> 多源行情的价值不是“多拿几份数据”，而是保留来源身份、验证时间和价格是否一致，并在
> 单源、冲突和全失败时给下游不同的可消费结论。

---

## 为什么需要它？

### 问题场景

股票代码 `000001` 是平安银行，但指数代码 `000001` 是上证指数；如果沿用股票市场路由，
新浪会请求 `sz000001`，东方财富会请求 `0.000001`，两路都可能返回“看似合法但身份错误”
的数据。即使代码正确，把两家价格直接平均也会掩盖时间错位、字段漂移或真实冲突。

### 它的解法

项目为三大指数维护独立映射：上证 `1.000001/sh000001`，深证
`0.399001/sz399001`，创业板 `0.399006/sz399006`。东方财富、新浪和腾讯共九个请求有界并发执行，每个结果保留
`source_id/upstream_id/status/latency/as_of/error_code`。

所有成功来源价格差不超过 0.01 点，并通过所在交易时段的时间对齐才形成完整共识。盘中（含午休）
仍要求时间差不超过 3 秒；收盘、周末、节假日及开盘集合竞价前，各源均为最近已完成
交易日的 15:00 后报价时按交易日对齐，不比较秒差。使用既有官方交易日历；跨日、
未来时间、未收盘报价及日历覆盖未知均不适用此例外。单源可用时保留真实数据并
标注 `INDEX_SINGLE_SOURCE`；2026-09-04 起首页冲突也展示一个有效来源并旁注冲突，
不声称验证通过；全部来源失败只能使用 30 秒内曾通过双源校验的
缓存。缓存不是第三个来源，也不能覆盖当前冲突。

---

## 项目里的真实代码

打开 `src/data/index_quote_runtime.py`：

```python
if max(prices) - min(prices) > INDEX_PRICE_TOLERANCE + 1e-9:
    return IndexQuoteService._display_quote(successful, name), [IndexLimitation(
        code="INDEX_PRICE_CONFLICT",
        index_code=code,
        message=f"{name} 多源价格差超过 0.01 点",
    )], True
```

这里选择时间最新的有效单源（同时间按 upstream_id 字典序最大值确定），并返回
`source_count=1` 与 `display_source`，不会平均、不会写入双源缓存。即使三项都存在
价时冲突，仍以 HTTP 200 `partial` 展示并旁注；正式 AI 决策门禁不受首页显示策略影响。

打开 `src/data/collector.py`：健康快照只暴露固定安全文案和稳定错误码。原始 ProxyError、
URL 与查询参数由调用点日志保存，不进入前端横幅。

---

## 和顺序 fallback 有什么不同？

| 对比 | 主备 fallback | 多源汇总 |
|:-----|:--------------|:---------|
| 正常时调用 | 只调主源 | 三源有界并发 |
| 能否发现主源错误值 | 不能 | 可以比较价时与身份 |
| 单源失败 | 切备用但不披露完整性 | 返回 `partial` 和逐源诊断 |
| 两源冲突 | 通常选主源 | 有效单源展示，旁注冲突 |
| 健康观察 | 一个聚合状态 | 按 upstream 独立统计 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_data/test_index_quote_runtime.py -q`；
2. 找到 `test_one_index_conflict_is_displayed_with_explicit_limitation`；
3. 把新浪价格从 `3943.55` 改为 `3943.54`，观察它从冲突变成完整共识；
4. 查看 `test_closed_session_alignment_preserves_intraday_and_price_checks`：同为 9 月 30 日收盘后报价，在国庆休市时对齐，在 10 月 8 日开盘后不能继续豁免；
5. 再把两源都改成失败，确认仅 30 秒内的已核验缓存能返回 `stale`。

---

**上一篇：[54｜HTTP 200 不等于数据成功](54-truthful-market-api-status.md)**

**下一篇：[56｜健康检查分层：连得上不等于有数据](56-layered-health-contract.md)**

## 2026-10-07：第三来源与降级状态

`src/data/providers/tencent_index_quotes.py` 从腾讯分钟接口的 `qt` 快照读取指数报价，
严格检查 `sh000001/sz399001/sz399006`、指数类型 `ZS`、价格及 `qt[30]` 北京时间。
成交量按手转股，成交额取原始元值；指数共识仅比较价格与时间，不声称成交量也已交叉核验。
请求失败不填零，分钟序列时间与请求完成时间都不能冒充报价时间。

东方财富故障而新浪、腾讯一致时，三张卡片仍是 `source_count=2`，整个采集批次
保留 `partial` 和东方财富故障诊断。三个来源均成功时必须全部一致；不能投票隐藏
第三方冲突。相同上游的两个适配器不能算两个来源。正式交易门禁不受首页新来源影响。

自己试试：运行 `pytest tests/test_data/test_tencent_index_quotes.py tests/test_data/test_index_quote_runtime.py -q`，
查看第三来源失败、成功、价格冲突和重复上游测试。

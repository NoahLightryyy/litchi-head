# 34 实时行情对账：新鲜不等于一致

## 一句话

> 实时行情不能只判断“接口成功”，还要同时验证真实来源、交易所时间、交易阶段、
> 单位和跨源一致性；任何一项无法证明，就不能交给 AI 做实盘分析。

---

## 为什么需要它？

### 问题场景

同一只股票从两个接口取回 `11.28`，看起来已经完成“双源验证”，但仍可能有四个坑：

1. 两个适配器实际都包装东方财富，不是两个独立上游；
2. 一个价格是刚生成的，另一个已经停更一分钟；
3. 东方财富成交量以“手”返回，新浪以“股”返回，直接比较会相差 100 倍；
4. 午休或收盘后的最后价格没有继续变化，但这不代表可以启动新的“实时”辩论。

更危险的是把错误写成空列表。业务层会把“行情源坏了”误认为“股票没有行情”，
随后继续执行完整 LLM 链，最后产出结构完整但依据残缺的结论。

### 它的解法

项目把判断拆成三层：

1. **来源层**：东方财富和新浪分别使用真实 `upstream_id`；
2. **单源层**：验证请求代码与新浪响应变量代码一致、交易所生成时间、数据年龄
   和单位；
3. **跨源层**：验证时间差不超过 3 秒、价格差不超过一个最小价位。

连续竞价采用 10 秒可用上限、30 秒硬过期上限。10–30 秒之间仍保留
`quote_suspect` 诊断，但已经禁止 AI 使用。这个区分有利于运维判断是短暂抖动还是
明确断流，不会放宽业务门禁。

这里的连续竞价边界是上午 9:30–11:30、下午 13:00–14:57；14:57–15:00 是收盘
集合竞价，不能沿用连续竞价判断。代码识别上海 `sh`、深圳 `sz` 和北京 `bj`，
其中北交所旧 `4/8` 号段和新 `920` 号段都必须路由到北京市场。

---

## 项目里的真实代码

打开 `src/data/providers/quotes.py`：

```python
quote = StockQuote(
    code=code,
    price=_number(data.get("f43"), "f43") / 100,
    volume=_integer(data.get("f47"), "f47") * 100,
    fetched_at=datetime.fromtimestamp(
        _integer(data.get("f86"), "f86"),
        tz=SHANGHAI,
    ),
)
```

这里同时完成价格缩放、成交量从“手”到“股”的归一化，以及交易所时间保留。
`SourceResult.fetched_at` 是本系统收到响应的时间，`StockQuote.fetched_at` 在这条新
链路中保存上游行情生成时间，两者不能混为一谈。

再打开 `src/data/quote_runtime.py`：

```python
if age_seconds > QUOTE_WARNING_SECONDS:
    return _unusable(
        result,
        status=SourceStatus.STALE,
        error_code="quote_suspect",
        error_message="Realtime quote is older than 10 seconds",
    )

if skew > QUOTE_PAIRING_SECONDS:
    # 两个来源不是同一个时间切片，不能直接比较价格
    ...

if price_delta > QUOTE_PRICE_TICK + 1e-9:
    # 同时间切片相差超过一个最小价位
    ...
```

最后由 `src/debate/orchestrator.py` 在第一个 LLM 节点前检查信封。只要
`complete=False`，LangGraph 立即结束并抛出 `EvidenceIncompleteError`。编排器
默认构造就会加载该门禁；测试若使用合成行情，必须显式声明旁路，防止生产脚本因
忘记注入依赖而失败开放。

---

## 和“允许相差 0.5%”有什么不同？

| 对比 | 固定百分比 | 时间对齐 + 最小价位 |
|:-----|:-----------|:--------------------|
| 低价股 | 可能放过多个价位差 | 按实际报价精度判断 |
| 高价股 | 允许的绝对差过大 | 仍限制为一个报价档位 |
| 快速行情 | 不知道是否比较了同一时刻 | 先验证时间，再比较价格 |
| 断流 | 价格碰巧相同可能被放过 | 独立检查数据年龄 |
| 休市 | 容易把最后收盘价当实时价 | 明确禁止启动新辩论 |

交易所和专业行情系统普遍强调时间戳、序列完整性、心跳以及
`LIVE / DELAYED / FROZEN / SUSPECT` 状态，而不是规定一个适用于所有品种的统一
百分比。项目的数字阈值是根据 A 股 Level-1 约 3 秒快照节奏制定的风险策略，不应
误写成交易所强制标准。

参考：

- 深交所行情接口规范：`https://www.szse.cn/marketServices/technicalservice/interface/P020240531618144293021.pdf`
- LSEG 实时行情状态：`https://developers.lseg.com/en/article-catalog/article/10-important-things-you-need-know-you-write-elektron-real-time-application`
- Interactive Brokers 行情类型：`https://www.interactivebrokers.com/docs/tws-api/doc/market-data-delayed/introduction`

---

## 面试会怎么问

> **Q：为什么两个行情源价格不同，不能马上判断其中一个错了？**
>
> A：必须先看来源是否独立、交易所时间是否对齐、市场处于什么阶段，以及价格和
> 成交量单位是否一致。快速行情中，错开几秒的两个正确快照也可能相差多个价位。
> 因此先做时间配对，再按最小价位比较；无法配对时标记可疑并失败关闭。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_data/test_quote_evidence.py`。
2. 把 `quote_at` 改为当前时间前 11 秒，运行该测试文件，观察
   `quote_suspect`。
3. 把新浪价格从 `11.28` 改成 `11.30`，观察 `quote_price_conflict`。
4. 思考题：如果未来接入逐笔行情，应该优先用价格容差，还是用频道序号和消息序号？

---

**上一篇：[滚动证据与 Fail-Closed 门禁](33-rolling-evidence-fail-closed.md)**

**下一篇：待补充**

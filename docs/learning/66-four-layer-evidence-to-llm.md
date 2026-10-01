# 66 四层行情怎样安全进入 LLM

## 一句话

> 数据层交付一个冻结联合后，辩论层只负责“分区展示、限制披露和阻断路由”，不能再次选源、复权或改写价格坐标。

---

## 为什么需要它？

### 问题场景

同一只股票盘中同时存在前复权日线、已结束分钟、实时成交价和尚未收盘的动态日 OHLC。
如果把它们重新塞进旧 `KLine[]`，模型很容易把前复权价当成订单价，或把盘中动态条说成
“今日已收盘突破”。更隐蔽的问题是 Decimal 复权成交量被旧整数模型强制转换后丢失精度。

### 它的解法

`KlineBusinessResult` 是数据层唯一冻结输入。辩论适配层先分类：完整结果分成四个明确
区段；可重试的缺源/陈旧转成 `EvidenceLimitation`；冲突或需要人工处理的损坏直接阻断。
适配层从不读取累计因子快照、公司行动条款或来源容差，也不把 QFQ 序列转换回旧模型。

---

## 项目里的真实代码

打开 `src/debate/kline_context.py`：

```python
def classify_kline_business_result(result: KlineBusinessResult):
    if isinstance(result, KlineBusinessEnvelope):
        return "complete"
    if any(
        diagnostic.retry_disposition is KlineRetryDisposition.OPERATOR_ACTION
        or any(source.status is SourceStatus.CONFLICTED
               for source in diagnostic.source_diagnostics)
        for diagnostic in result.layer_diagnostics
        if not diagnostic.complete
    ):
        return "blocked"
    return "limited"
```

`format_kline_business_context()` 再把完整结果写成四区 Prompt：

- `FINAL_DAILY / QFQ`：只解释历史技术结构；
- `FINAL_MINUTE / RAW`：只包含已经结束的分钟；
- `LIVE_QUOTE / RAW`：成交和订单价格坐标；
- `PROVISIONAL / RAW`：明确标为尚未收盘。

`src/debate/orchestrator.py` 保存 `EvidenceReference`，让结果和记忆都能追到
`raw_snapshot_id`、`factor_version`、`as_of` 和三组上游；受限结果在聚合后直接结束，
不会进入风控、交易员或 PM。

---

## 和“重新格式化旧 KLine[]”有什么不同？

| 对比 | 旧数组兼容 | 四层适配 |
|:-----|:-----------|:---------|
| 价格坐标 | RAW/QFQ 容易混淆 | 每区显式标记 |
| 动态日线 | 可能混入完成日线 | 独立 `PROVISIONAL` |
| 缺源 | 可能留下半份数据 | 只留下结构化限制 |
| 可追溯 | 很难知道所用因子 | 保存快照与因子版本 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_debate/test_kline_evidence_context.py -q`；
2. 找到 `test_complete_result_reaches_llm_and_persists_version_reference`，查看 Prompt 与记忆断言；
3. 把失败诊断改成 `SourceStatus.CONFLICTED`，确认分析师和大师调用数仍为零；
4. 思考：为什么即使 `LIVE_QUOTE` 层完整，也不能从失败联合里私自取出它继续下单？

---

**上一篇：[65｜线程安全不是“用了 GIL 就行”](65-atomic-health-snapshot.md)**

**下一篇：** 待续

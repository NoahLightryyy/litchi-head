# 50｜运行时证据怎样安全合流

> 一句话：组装多源行情时要先验证信封身份与完整性，再读取 payload；否则缓存残留和
> 错接线路都可能把失败数据伪装成成功输入。

## 项目里的真实问题

KR-1/2 日线、分时和实时报价各自已经完成双源核验，但它们原先只是三条旁路线。
`src/data/kline_business_runtime.py` 的任务不是重新对账，而是把已经核验的结果安全地
映射到 KR-3A 四层业务信封。

关键顺序是：

1. 先检查三类 `EvidenceEnvelope.complete`；
2. 再检查能力槽位分别是 `KLINE / INTRADAY / REALTIME_QUOTE`；
3. 再检查三个 `request.stock_code` 与业务证券一致；
4. 校验 KR-1 的 `daily_snapshot_id` 与 KR-2 序列的 `raw_snapshot_id` 相等；
5. 最后才读取条目并构造业务对象。

如果先读条目再看状态，失败信封里遗留的缓存 payload 就可能被误用。这也是为什么
测试专门保留条目、只把 `complete` 改成 `false`：它能抓住真实的错误分支，而不是
只验证一个空列表。

即使上游标记完整，canonical 实时报价也必须恰好一条：0 条代表没有可用事实，多条
代表选择规则失效。两种情况都应失败关闭，不能用 `next()` 静默拿第一条。

复权序列和日线证据信封“各自完整”仍不够：它们还必须指向同一个内容寻址 RAW
快照。显式传入持久化返回的 snapshot ID 并与序列血缘比较，才能防止跨快照拼接。

## 为什么只筛 `FINAL` 分钟

分时运行时的 canonical 列表可能同时包含已结束分钟和当前形成中的分钟。组装器只把
`IntradayBarState.FINAL` 转为冻结 `FinalMinuteBar`；当前分钟不能因进入统一信封就
自动获得“已完成”语义。

当日动态 OHLCV 则来自双源核验后的 RAW `StockQuote`，单独构造成
`ProvisionalSessionBar`。它能供盘中分析使用，但仍不能混进完成日线数组。

## 为什么不完整信封里的缓存条目不能变成“部分成功”

`EvidenceEnvelope.complete=False` 是对整条证据链的结论，不是“这次请求碰巧少了一条”的
提示。缓存的 `items` 可能来自上一次成功请求，也可能只覆盖一个上游；一旦继续读取它们，
调用者就会拿到看起来完整的行情，却不知道本次核验已经失败。

因此 `assemble_kline_business()` 先检查三个信封的完整性，再决定是否读取 payload。任何一层
不完整时返回 `KlineBusinessFailure`，结果中只有四层诊断和稳定错误码，不包含
`final_daily_bars`、`final_minute_bars`、`live_quote` 或 `provisional_session_bar`。

## 为什么报价失败会同时影响 `LIVE_QUOTE` 和 `PROVISIONAL`

`PROVISIONAL` 不是第二套独立行情，它是由同一条 canonical RAW `StockQuote` 构造出的盘中
动态 OHLC。报价信封不完整时，实时层没有可核验事实，动态日条也就没有合法输入。因此失败
结果同时标记 `LIVE_QUOTE=live_quote_evidence_incomplete` 和
`PROVISIONAL=provisional_quote_dependency_incomplete`；这能让下游准确看到依赖关系。

报价信封完整但不是恰好一条时，两个层也会分别得到 `live_quote_cardinality_invalid` 和
`provisional_quote_dependency_invalid`。只有单一报价本身不能构造成有效 OHLC 时，实时层仍可
完整，而 `PROVISIONAL` 单独报 `provisional_quote_invalid`。

## 为什么程序接线错误仍然抛异常

把实时信封接到日线参数，或请求 `000001` 却传入为 `600000` 收集的信封，不是上游暂时失败，
而是调用代码违背接口契约。`assemble_kline_business()` 会保留严格组装器的 `ValueError`，而不把
它们压缩成业务失败；否则部署或重构错误会被错误地当成“稍后重试”的市场数据问题。

打开 `src/data/kline_business_runtime.py` 可对照：接线/证券身份校验发生在失败分类之前，完整
输入才调用 `assemble_complete_kline_business()`。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_kline_business_runtime.py -q`；
2. 在 `tests/test_data/test_kline_business_runtime.py` 的 `_incomplete()` 调用处，把任一
   日线、分时或报价信封变为 `complete=False`，但保留其中的 `items`；
3. 运行对应的 unified assembler 测试，并检查返回 `layer_diagnostics` 是否始终包含四层，
   同时确认序列和报价 payload 没有出现在 `model_dump()`；
4. 再把 `quote_evidence` 接到 `daily_evidence` 参数，观察能力槽位校验仍抛出异常；
5. 查看成功结果，确认 10:01 的临时分钟没有进入 `final_minute_bars`。

---

**上一篇：[49｜四层行情信封](49-four-layer-market-envelope.md)**

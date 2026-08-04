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

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_kline_business_runtime.py -q`；
2. 把测试中的 `intraday_evidence.complete` 改成 `false` 但保留 `items`，观察组装器
   在读取条目前拒绝；
3. 把 `quote_evidence` 接到 `daily_evidence` 参数，观察能力槽位校验；
4. 查看成功结果，确认 10:01 的临时分钟没有进入 `final_minute_bars`。

---

**上一篇：[49｜四层行情信封](49-four-layer-market-envelope.md)**

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

## 多个来源同时失败时怎样归并

KR-3B-2 在成功组装器之外新增 `assemble_kline_business()`。它返回判别联合：四层
全部成功时返回 `KlineBusinessEnvelope`，任一层失败时返回
`KlineBusinessFailure`，不会再把运行时失败压成无法展示的普通 `ValueError`。

归并时要同时保留两种信息：

- `KlineLayerDiagnostic.error_code` 是该层的稳定主错误码，供业务分支和 API 使用；
- `source_diagnostics` 保存每个不可用来源的 `source_id`、真实 `upstream_id`、状态、
  错误码、信息和采集时间，但不保存残缺行情条目。

主错误不能依赖集合遍历顺序。项目固定按“冲突 → 陈旧 → 采集失败 → 不支持”选择，
同级再按错误码和来源身份排序。全局错误码则按
`FINAL_DAILY → FINAL_MINUTE → LIVE_QUOTE → PROVISIONAL` 排列并去重，因此同一报价
故障虽然同时关闭实时价和动态日条，也只产生一个全局主码。

重试也不是一个模糊布尔值：

| 处置 | 含义 | 例子 |
|:-----|:-----|:-----|
| `retry_fresh` | 丢弃本次结果，重新采集后再试 | 网络抖动、短时陈旧、盘中源冲突 |
| `wait_for_condition` | 等市场或覆盖条件变化，禁止紧循环 | 非连续竞价、缺独立来源、历史覆盖不足 |
| `operator_action` | 自动重试无意义，需要修数据或接线 | 脏响应、身份错误、快照血缘冲突 |

如果同一层同时出现多种处置，选择更保守的一档。这样上层不会因为其中一个网络错误可重试，
就掩盖同时存在的脏响应或身份冲突。

能力槽位或请求证券接错仍然抛编程契约异常。它们不是市场数据暂时不可用，若转换成普通
业务失败会掩盖部署缺陷。相反，快照血缘不一致、canonical 报价数量错误和报价时间戳
无效属于真实运行时完整性失败，会进入四层诊断。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_kline_business_runtime.py -q`；
2. 把测试中的 `intraday_evidence.complete` 改成 `false` 但保留 `items`，观察组装器
   在读取条目前拒绝；
3. 把 `quote_evidence` 接到 `daily_evidence` 参数，观察能力槽位校验；
4. 查看成功结果，确认 10:01 的临时分钟没有进入 `final_minute_bars`。
5. 让两个报价来源分别返回 `STALE` 和 `CONFLICTED`，确认逐源诊断都保留，但
   `quote_price_conflict` 成为稳定主错误码。

---

**上一篇：[49｜四层行情信封](49-four-layer-market-envelope.md)**

**下一篇：[52｜证据不完整时怎样继续推理而不伪装完整](52-evidence-limited-reasoning.md)**

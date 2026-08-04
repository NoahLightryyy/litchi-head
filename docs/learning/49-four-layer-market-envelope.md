# 49｜四层行情信封：盘中可用，不等于已经收盘

> 盘中 AI 不必等待收盘，但必须把完成日线、已结束分钟、实时快照和动态日线分成四个不可混淆的层。

## 为什么不能继续传一条 K 线数组

上午 10 点已经有实时价格和今日高低点，但今天的日线仍会变化。若把动态 OHLC
追加进历史日线，均线、突破和形态代码就可能把“盘中一度发生”说成“收盘确认”。

项目在 `src/data/kline_business.py` 固定四层：

- `final_daily_bars`：只含上一交易日及以前的统一前复权完成日线；
- `final_minute_bars`：只接受状态为 `FINAL` 的已结束分钟；
- `live_quote`：双源核验的 RAW 实时价格，不能拿复权价当成交价；
- `provisional_session_bar`：今日仍会变化的 RAW OHLC，固定标记 `PROVISIONAL`。

模型会检查证券身份、上海交易日、时间顺序、`as_of` 和独立上游。动态交易日只要
与完成日线最后一天相同，整个成功信封就构造失败。

## 为什么失败结果不带“能用的那一半”

`KlineBusinessResult` 是按 `complete` 判别的联合：

```python
KlineBusinessResult = Annotated[
    KlineBusinessEnvelope | KlineBusinessFailure,
    Field(discriminator="complete"),
]
```

成功分支四层全部必填；失败分支只允许四层诊断和错误码。这样下游不能因为看见一
条旧实时价或一组残缺分钟，就绕过完整性门禁继续调用 LLM。

## “冻结外壳”为什么还不够

Pydantic 的 `frozen=True` 默认只冻结当前模型。若内部仍放一个可变 `StockQuote`，
调用方依然可能执行 `envelope.live_quote.price = 99.99`。因此业务信封会把实时行情
和完成分钟转换成专用冻结模型；完成日线和动态日线本身也已冻结。

这叫深度不可变：审计对象不仅不能换掉，里面的市场事实也不能原地改写。

## 收盘晋升怎样做到可重试又不覆盖

`promote_provisional_session()` 使用动态状态、最终日线、RAW 快照 ID、因子版本和
双上游身份生成确定性 SHA-256。`promoted_at` 不进入 ID，所以网络重试时间不同也
不会生成第二条逻辑记录：

- 内容相同：直接返回既有 `DailyPromotionRecord`；
- 内容不同：抛出 `DailyPromotionConflictError`，保留原审计记录；
- 底层 RAW 快照早于动态条、证据时间在晋升之后、证券/交易日不一致：晋升前直接
  拒绝。

记录本身保存完整动态条、最终日线及两者证据时间；从存储回放时会重新计算
`promotion_id`。因此即使有人只改了收盘价却保留旧哈希，模型重建也会失败关闭。

函数本身不改写 RAW 或存储，因此一次失败后可以在证据补齐时安全重试。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_kline_business_envelope.py -q`；
2. 把动态日线日期改成最后一根完成日线日期，观察成功信封被拒绝；
3. 构造信封后尝试修改 `live_quote.price`，观察冻结校验；
4. 用同一最终证据、不同 `promoted_at` 重试晋升，再换一个 RAW 快照 ID 比较结果。

---

**上一篇：[48｜PDF 表格与修订链](48-pdf-table-idempotency-and-revision-linking.md)** ｜
**下一篇：[50｜运行时证据怎样安全合流](50-runtime-evidence-assembly.md)**

# 47｜已核验公司行动因子：供应商尾数为什么不能直接当真

> 公司行动因子必须同时满足“累计除数相邻变化”和“官方条款公式复算”，并把真实可验证精度写进结果。

## 为什么需要两条证据链

新浪累计 QFQ 除数能告诉我们复权序列发生了多大变化，却没有说明变化来自现金分红、
送转还是配股。CNINFO/交易所公告能给出条款，却不能证明某个行情供应商实际采用的
累计因子。任取一边直接生成复权结果，都可能把错误隐藏进历史 K 线。

项目因此只把相邻累计除数的 `newer / older` 当作候选价格乘数，再用登记日 RAW
收盘价和官方条款独立复算：

```text
价格乘数 = (登记日收盘价 - 除权现金 + 配股价 × 配股增量)
           / (登记日收盘价 × 行动后总股本倍数)
```

纯送转的成交量乘数等于行动后/行动前股本比；纯现金分红保持 RAW 成交量不变。

## 项目里的真实代码

打开 `src/data/kline_adjustment.py`：

```python
price_factor = newer.cumulative_divisor / older.cumulative_divisor
expected_price_factor = (record_close - cash + rights_value) / (
    record_close * volume_factor
)

formula_matches = lower_price_factor <= expected_price_factor <= upper_price_factor
if price_factor_precision < Decimal("0.000000000001"):
    formula_matches = price_factor.quantize(
        Decimal("0.000000000001"),
        rounding=ROUND_HALF_EVEN,
    ) == expected_price_factor.quantize(
        Decimal("0.000000000001"),
        rounding=ROUND_HALF_EVEN,
    )
```

低精度累计除数按其声明精度传播区间核验；新浪返回 16 位小数时，真实样本显示末尾
约有 `1e-14` 级舍入噪声，因此采用用户批准的 12 位 `ROUND_HALF_EVEN` 门限。
输出仍保存完整候选因子，但把 `price_factor_precision` 标为 `1e-12`，避免下游误以为
尾部 16 位都经过官方证据验证。12 位可见差异继续失败关闭。

## 为什么不能直接用绝对误差

“误差小于 `1e-12`”和“双方四舍六入五成双到 12 位后相等”不是同一规则。项目采用
后者，是因为它明确描述可对外声明的十进制位数，也能稳定处理恰好落在半步边界的值。
对只有 4 位的上游值，则不能假装拥有 12 位精度，仍以原始量化区间为准。

## 点时与版本边界

- `known_at` 取新浪快照和官方事件采集时间的较晚者；
- `factor_version` 绑定转换器版本、完整官方事件和新浪响应哈希；
- 公告历史发布时间不能倒推成系统已经采集到该证据；
- 累计快照或官方事件单独出现时，都不能进入复权和 AI。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_corporate_action_factor_conversion.py -q`；
2. 在真实尾差夹具中把累计除数最后几位改到 12 位结果发生变化，观察转换失败；
3. 把累计除数精度改成 `0.0001`，观察输出不会虚报成 `1e-12`；
4. 思考：如果 `known_at` 使用公告发布日期而不是采集时间，历史回测会发生什么？

---

**上一篇：[46｜公告修订归链](46-corporate-action-revision-linking.md)**

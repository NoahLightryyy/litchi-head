# 43 公告正文解析：正则能匹配，不等于证据可以相信

## 一句话

> 金融公告解析必须先锚定“最终实施章节”，再对候选值去重和查冲突；模板没覆盖时
> 明确拒绝，比猜出一个看似合理的数字更安全。

---

## 为什么需要它？

一份权益分派公告会同时出现股东会预案、全年方案、已实施中期分红、本次实施金额、
含税金额、税后金额和补缴情形。如果对整篇 PDF 使用第一次正则命中，可能把全年
金额重复算成本次分红；如果把所有“每 10 股转增 4 股”相加，又会因正文重述而
重复应用。

项目因此只解析深交所标准模板中的“本次实施的权益分派方案”和最终登记日章节。
现金优先选择明确标注“含税”的主方案；同一个送股或转增条款重复出现只算一次，
不同值则整批失败。上交所表格、配股发行日程、差异化分派和修订生命周期尚未建立
独立语法，所以当前显式失败关闭。

---

## 项目里的真实代码

打开 `src/data/providers/cninfo_actions.py`：

```python
gross_candidates: set[tuple[Decimal, Decimal]] = set()
fallback_candidates: set[tuple[Decimal, Decimal]] = set()

for match in _CASH_PATTERN.finditer(section_body):
    candidate = (
        Decimal(match.group("base")),
        Decimal(match.group("amount")),
    )
    if "含税" in section_body[match.end() : match.end() + 40]:
        gross_candidates.add(candidate)

candidates = gross_candidates or fallback_candidates
if len(candidates) > 1:
    raise ValueError("official corporate-action cash terms conflict")
```

关键点不是正则本身，而是正则之后的“候选集合语义”：重复同值不会改变结果，
不同值不会由文本顺序决定胜负。

分页也采用相同纪律：每页 `totalAnnouncement` 必须稳定，页容量必须符合总数，
整个批次的公告 ID 必须唯一。否则第二页重复第一页时，系统可能恰好凑够条数，
却漏掉真正的实施或终止公告。

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_cninfo_corporate_actions.py -q`；
2. 把税后金额放在含税金额之前，确认结果仍取含税主方案；
3. 把同一“每 10 股转增 4 股”复制一遍，确认比例仍为 `7/5`；
4. 把第二个值改为 5 股，确认整批失败而不是选第一个。

---

## 前后链接

- 上一张：[42｜官方公司行动条款契约](42-official-corporate-action-contract.md)
- 下一张：待新增

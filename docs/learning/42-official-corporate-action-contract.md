# 42 官方公司行动条款契约：公告不是因子，但必须能被机器严格核验

## 一句话

> 官方公告先被规范成可审计、可版本化的公司行动条款；只有再与独立累计除数匹配，
> 才能生成复权因子。

---

## 为什么需要它？

### 问题场景

公告可能写“每 10 股派 2.36 元”“每 10 股转增 5 股”或同时包含派息、送转和
配股。若解析器直接产出一个价格乘数，系统就无法回答：这个乘数来自哪份公告、
公告何时被系统获得、解析规则是哪一版、股本比例是否被浮点数改写。

更危险的是把新浪累计 QFQ 除数反推成事件类型。相同的相邻比值可能来自现金、
送转或组合事件；没有官方条款，只能知道“发生了变化”，不能知道该怎样校验价格
和成交量。

### 它的解法

项目把证据分为三层：

1. `OfficialCorporateActionDocument` 保存公告身份、发布时间、HTTPS 原文链接和
   SHA-256；
2. `OfficialCorporateActionEvent` 保存系统采集时间、解析器版本、除权日和严格
   条款，但明确不包含价量乘数；
3. 后续 KR-2B-2C 才把稳定事件与新浪相邻累计除数匹配，生成
   `CorporateActionFactor`。

这样，公告条款和因子侧证据可以独立失败、独立审计，也不会因解析器升级改写旧
决策。事件的最终 `known_at` 必须取两路证据采集时间的较晚者。

---

## 项目里的真实代码

打开 `src/data/kline_adjustment.py`：

```python
class OfficialCorporateActionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: int = Field(ge=1, strict=True)
    record_date: date
    ex_date: date
    collected_at: datetime
    parser_version: str = Field(min_length=1)
    documents: tuple[OfficialCorporateActionDocument, ...] = Field(min_length=1)
    cash_dividend_per_share: Decimal | None = Field(default=None, gt=0, strict=True)
    share_ratio_numerator: int | None = Field(default=None, gt=0, strict=True)
    share_ratio_denominator: int | None = Field(default=None, gt=0, strict=True)
```

`strict=True` 拒绝把 `1.0`、`"1"` 或 `True` 偷偷转成整数；金额使用 `Decimal`，
股本比例保存精确分子/分母。`extra="forbid"` 让上游字段漂移立即报错，而不是静默
丢弃。文档按发布时间、外部 ID、哈希确定性排序，并分别拒绝重复 ID 和重复内容。

条款矩阵也失败关闭：

- 现金分红只能有每股现金；
- 送转/拆股的股本比例必须大于 1；
- 合股比例必须小于 1；
- 配股必须同时有配股比例和认购价；
- 组合事件至少包含两类有效成分。

这里的送转/拆并股比例表示“行动后股数 / 行动前股数”；配股比例单独保存，避免
把认购行为与无偿股本变化混为一谈。

---

## 和复权因子有什么不同？

| 对比 | 官方条款事件 | `CorporateActionFactor` |
|:-----|:-------------|:------------------------|
| 回答的问题 | 官方公告说发生了什么 | 历史价量具体乘多少 |
| 主要证据 | CNINFO/交易所公告 | 官方条款 + 新浪相邻累计除数 |
| 是否含价量乘数 | 不含 | 包含并经过核验 |
| 能否直接进入 AI/回测 | 不能 | 完整门禁通过后才可以 |

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_data/test_corporate_action_contract.py -q`；
2. 把合法事件的 `revision=1` 改成 `revision=1.0`，确认严格类型拒绝；
3. 删除配股认购价，确认不完整条款失败关闭；
4. 思考：为什么 `published_at` 早于决策日，仍不能替代系统实际获得证据的
   `collected_at`？

---

## 前后链接

- 上一张：[41｜累计复权因子](41-cumulative-factor-vs-corporate-action.md)
- 下一张：[43｜公告正文解析为什么必须失败关闭](43-corporate-action-document-parsing.md)

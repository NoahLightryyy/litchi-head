# 48｜PDF 表格与修订链：重复不是冲突，模糊相似也不是引用

> 官方 PDF 解析要把“相同值重复出现”和“不同值发生冲突”分开，同时只用可证明的完整标题或精确 ID 归链修订。

## 为什么 PDF 会把正确数据变成两个匹配

上交所权益分派公告常在“重要内容提示”和正文“相关日期”中重复同一张表。
PyMuPDF 又会把每个表格单元格拆成独立行，因此同一组登记日、除权日可能被正则
匹配两次。若代码要求“匹配次数必须等于 1”，合法公告就会失败；若简单取第一个，
两张表日期真正不一致时又会静默放行。

项目的处理方式是先把每次匹配转成日期对，再用集合归并：

```python
date_pairs = {
    (parsed_record_date, parsed_ex_date)
    for row in _SSE_DATE_ROW_PATTERN.finditer(text)
}
if len(date_pairs) != 1:
    raise ValueError("... missing or conflicting")
```

两个相同日期对会幂等变成一个；零个或两个不同日期对仍失败关闭。

## 修订公告为什么不能做模糊标题匹配

真实 `688503` 链包含原实施公告、更正通知和同日发布的“实施公告（修订版）”。
PDF 抽取可能在标题内部插入空格和换行，但公告 ID、汉字和标点并没有变化。项目只
删除 Unicode 空白后比较完整标题，或使用带身份边界的精确公告 ID：

```python
normalized_text = re.sub(r"\s+", "", document_text)
normalized_title = re.sub(r"\s+", "", announcement.document.title)

mentioned = exact_id_match is not None or normalized_title in normalized_text
```

这不是关键词模糊匹配。“年度权益分派”“更正”之类短词不能证明替代关系；若一个
通知同时命中两个实施公告，仍会因歧义失败。

## 差异化分红要保留两个现金口径

`688503` 修订版使用“总股本扣减回购股份后的股本”表示参与分派股本，并用官方
公式给出摊薄后的每股现金红利。解析器保存：

- 实际派发：`distribution_cash_per_share = 0.432`；
- 除权调整：`adjustment_cash_per_share = 0.413`；
- 总股本：`242,033,643`；
- 参与分派股本：`231,483,309`。

复权公式只能使用除权调整口径，不能把股东实际收到的金额直接代入。

## 项目里的真实证据

- `tests/fixtures/cninfo/600000_1224119803_relevant.txt`：普通分红重复日期表；
- `tests/fixtures/cninfo/688503_1225378571_relevant.txt`：差异化分红修订版；
- `tests/test_data/test_cninfo_corporate_actions.py`：重复归并、修订版标题、标题空白和
  差异化股本公式回归；
- `src/data/providers/cninfo_actions.py`：解析器版本 `v4`。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_cninfo_corporate_actions.py -q`；
2. 把普通分红夹具第二张表的除权日改一天，观察解析失败；
3. 删除修订通知中的完整原公告标题，观察修订链拒绝归链；
4. 思考：为什么“同日发布”本身不足以证明两个公告属于同一修订链？

---

**上一篇：[47｜已核验公司行动因子](47-verified-corporate-action-factor.md)**

# 46｜公告修订归链：看见“更正”不等于知道该替换谁

> 修订公告只有在“旧实施公告 → 修订通知 → 修订后完整正文”唯一可证时才能生效。

## 为什么标题匹配不够

同一家公司一年内可能发布多份权益分派公告；公告 ID 还可能互为前缀。仅凭标题含
“更正”或字符串包含 ID，既可能替错事件，也可能把终止公告当成仍有效的实施方案。
实盘复权一旦用错日期或金额，用户通常无法从图形上立即发现。

项目在 `src/data/providers/cninfo_actions.py` 中先下载官方正文和 SHA-256，再要求正文
唯一引用已经发布的实施公告。ID 使用字母数字边界匹配，修订通知不能替代未来公告。
更正类还必须找到唯一的“更正后”完整实施正文；延期、终止、取消则清空有效集合。

## 项目里的真实代码

```python
matching_roots = [
    root_id
    for root_id, documents in chain_documents.items()
    if any(
        document.document.published_at <= revision_notice.document.published_at
        and _mentions(revision_notice.document_text, document)
        for document in documents
    )
]
if len(matching_roots) != 1:
    raise ValueError("... reference is missing or ambiguous")
```

`CorporateActionRevisionLedger` 用 `status + supersedes_document_ids` 回放有效集合。
修订链事件沿用原公告 ID 作为稳定 `action_id`，不会因更正了除权日而变成另一事件。

## 为什么还要历史回填

用户查询的窗口可能只覆盖终止公告，原实施公告在窗口前。此时适配器仍使用同一个
CNINFO 官方完整分页接口，最多向前回填 365 天；仍找不到唯一原公告就失败关闭，
不会按“最近一份公告”猜测。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_cninfo_corporate_actions.py -q`；
2. 把测试中的原公告 ID 从 `1234` 改成 `123`，观察精确边界如何避免前缀误链；
3. 删除“更正后完整实施公告”，观察来源拒绝只解析更正通知；
4. 思考：为什么终止公告应返回空事件，而不是返回 revision 更高的旧条款？

---

**上一篇：[45｜差异化分派](45-differential-distribution-basis.md)**

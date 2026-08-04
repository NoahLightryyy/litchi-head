# 📄 官方 PDF 解析

## `official SSE distribution date row is missing or conflicting`

### 先判断是“重复”还是“真冲突”

上交所公告可能在“重要内容提示”和正文重复同一张相关日期表，PyMuPDF 会把单元格
拆成多行。不要用匹配次数判断唯一性：先把每次匹配转换为 `(record_date, ex_date)`，
相同值用集合幂等归并；集合为空或包含多个不同日期对才失败。

对应回归夹具：`tests/fixtures/cninfo/600000_1224119803_relevant.txt`。

## 修订通知明明引用原公告却报 `reference is missing or ambiguous`

PDF 抽取可能在完整标题内部插入空格/换行。允许删除 Unicode 空白后比较完整标题，
但不能改成关键词包含；公告 ID 仍使用字母数字边界精确匹配。若归一后命中多个实施
公告，继续失败关闭。

交易所真实完整修订正文可能使用“权益分派实施公告（修订版）”，不能只识别
“（更正后）”。解析行为变化后同步升级 `CNINFO_CORPORATE_ACTION_PARSER_VERSION`。

对应真实链：`688503` 的 `1225365375 → 1225378572 → 1225378571`。

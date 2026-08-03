# 45｜差异化分派：股东收到的钱，不一定是除权公式里的钱

> 差异化分派必须同时保存实际派发金额和按总股本折算的虚拟金额，否则复权会用错钱。

## 两个金额为什么不同

回购专户股份不参与分红时，股东实际每股可收到 `distribution_cash_per_share`；
交易所计算除权参考价时，要把总现金摊回全部股本，使用
`adjustment_cash_per_share`。普通分派两者相同，差异化分派必须同时保存
`total_shares` 与 `participating_shares`，缺一个就失败关闭。

项目代码见 `src/data/kline_adjustment.py` 的 `OfficialCorporateActionEvent`，解析入口
见 `src/data/providers/cninfo_actions.py`。

## 修订不是覆盖文件

`CorporateActionRevisionLedger` 把每份官方文档保存成不可变修订，并用
`supersedes_document_ids` 明确替代关系。终止或取消后有效文档集合为空，下游不能
生成公司行动事件。

## 自己试试

1. 运行 `python -m pytest tests/test_data/test_corporate_action_contract.py -q`；
2. 删除差异化事件的 `participating_shares`，观察模型拒绝；
3. 把终止修订改成 `corrected`，比较有效文档集合；
4. 思考：若用实际 `0.20` 代替虚拟 `0.1981`，长期复权误差会如何累计？

---

**上一篇：[44｜影子回填](44-shadow-backfill-and-trusted-baseline.md)**

**下一篇：[46｜公告修订归链](46-corporate-action-revision-linking.md)**

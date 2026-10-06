# 板块资料图类型（2026-10-06）

`chain_evidence`新增`map_kind=industry_chain|market_structure`，默认industry_chain，旧目录保持兼容。
market_structure仅允许market_entity节点，上市连线使用listing_relationship；不得和supplies或industry_sequence混用。

BK0499 AH股新增3节点、2关系核验目录，依据上交所2019-07-26与港交所2001-05-17的基本概念说明，非当前交易资格清单。
前端按map_kind显示“市场结构图”和“上市关系”，显式展示scope；不再将AH股当作统一产业链。
沿用POST chain-analysis的引用约束、错误码、超时及重试；提示词区分市场结构与产业环节。

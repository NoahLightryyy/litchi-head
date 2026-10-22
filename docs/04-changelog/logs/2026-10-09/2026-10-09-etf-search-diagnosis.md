# ETF搜索缺失定位

用户问搜索ETF为何无结果。代码确认backend/routers/discovery.py的SearchHit仅
stock/industry/concept，search只并发stock_catalog与board_catalog；前端Hit和跳转
也无ETF类型。不是关键词大小写问题，ETF本来未接入。截图还有股票目录未取得，
是独立上游故障，恢复该股票目录仍不会新增ETF覆盖。
未改业务/契约/数据源，未把ETF当普通个股。登记SEARCH-ETF-001待评估并更新债务路由。
下一步需确定ETF目录与详情范围再冻结契约。只读诊断无代码测试或新学习卡要求。

## 用户批准ETF与资金榜同时规划执行

整理两条原子交付计划ETF_AND_FUND_RANKING_PLAN.md；实网新浪ETF分类有分页截断，
page10确认沪深身份，page20空；需实施完整分页校验。资金同花顺页面初次含字段，
复测没有表格，时间/主力口径未验证，不能作为可靠替代源。来源决策等待用户确认，
未修改产品/契约，未提交推送。补现有知识卡59的分页和口径设计说明。

# 板块基本面研究契约 · v1 · 2026-10-01

本文件取代本分支上一版只复用 financials/valuation/indicators 的说明。先冻结并提交后端，前端按此消费。

## GET /api/stocks/{code}/fundamental-research

六位证券代码；直接返回 FundamentalResearch（无data包裹），schema_version=1。非法代码HTTP422；上游错误HTTP200结构化状态，不把空表解释为无财报。

- stock_code；status=available/partial/stale/unavailable；report_date=已返回最新合并利润表报告期或null。
- fetched_at=本次成功采集时间（UTC），不是披露时间；source=sina_consolidated_statements；verification=single_source。
- statements：计算所用报表，kind=lrb/fzb/llb，report_date，published_at（供应商报告的披露日期，可null），source_url，currency=CNY，scope=合并期末，amounts（原字段ID到可空金额）。不跨报告期拼接资产负债表。
- metrics：revenue/gross_margin/parent_profit/revenue_growth/parent_profit_growth/return_on_ending_equity/operating_cash_flow/debt_ratio/revenue_ttm/parent_profit_ttm/pe/pb/ps。每项value可null，unit、basis必有，reason解释缺值。真实0、负数保留。
- warnings和retryable明确部分失败。毛利率=(营业收入−营业成本)/营业收入；归母增长与合并净利润增长分别定义；期末权益回报率不是加权ROE；现金流显示总额，不推算每股。
- TTM=当前累计+上年全年−上年同期，年度直接取全年；缺任一期返回null，数据来自当前供应商版本，未提供历史时点重述链，不用于无前视回测。
- PE应为总市值/归母净利润TTM，PB为总市值/归母权益，PS为总市值/营收TTM。当前缺少带有效行情时间和股本范围的市值，三项null并附原因；不沿用半年EPS直接相除。

新浪三表并发，连接3秒/读取8秒，最多16期，合并人民币范围；解析非有限值、重复事实、坏日期失败有日志。每代码单飞，最多缓存256代码；成功15分钟，有部分请求失败60秒；刷新失败最多回显24小时内旧快照且标stale、保留原fetched_at，超过24小时unavailable。不作收益评级、无LLM调用。

## 兼容修正

financials 中 gross_margin、operating_revenue 允许null。AKShare新浪分析表没有毛利率时不补0；主营业务利润不再映射营业收入。旧valuation没有行情时点与股本证据，停用旧缓存/错误YTD比率，返回data:null及meta.reason。原结构其他字段暂保留，未完成全面缺值迁移，不应混用于新研究表。

indicators接口仅返回行业指标定义，不等于实测研究证据。选中公司不代表行业全部样本，完整行业AI服务仍未实现。

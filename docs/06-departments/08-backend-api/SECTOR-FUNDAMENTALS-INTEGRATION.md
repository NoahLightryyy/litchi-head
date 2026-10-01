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

## 两家公司原文抽样核验（2026-10-01）

| 项目（2026-06-30，元） | 翰宇药业300199 | 恒瑞医药600276 |
|---|---:|---:|
| 营业收入 | 688,286,621.30 | 15,455,583,728.11 |
| 营业成本 | 255,260,254.71 | 2,113,343,029.35 |
| 归母净利润 | 236,700,162.04 | 4,465,439,428.10 |
| 经营现金流净额 | 305,459,354.85 | 1,987,003,872.34 |
| 毛利率（据原文计算） | 62.91366898% | 86.32634609% |
| 归母净利润同比 | 62.72% | 0.34% |
| 原文加权平均ROE | 32.33% | 8.04% |
| 本接口期末权益回报率（非加权ROE） | 27.84% | 6.93% |

- [翰宇药业半年报原文](https://static.cninfo.com.cn/finalpage/2026-08-21/1225487665.PDF)：物理/印刷第9页主要会计数据；第21页收入/成本。来源披露日2026-08-21，PDF来源日期与新浪一致。
- [恒瑞医药半年报原文](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0819/2026081901589_c.pdf)：物理第7页（印刷第6页）主要会计数据；物理第57页（印刷第56页）收入/成本。港交所封面公告日2026-08-19；新浪A股报表元数据披露日2026-08-20。两者分别保留，不将香港发布日期冒充内地披露时间；内地披露日目前仍为供应商记录，尚未独立核验。

只核对以上样本和本期/同期披露；不是所有公司、所有字段自动多源核验。TTM用新浪三期计算，未逐一核对2025年报原文。测试fixture为当日供应商响应的有限字段截取，生产不读取fixture。原PDF只保存在忽略的logs，追溯用URL和下列SHA256。
- 300199 PDF SHA256：`c78f97d43aa1b0ec2ce1ba944de7870619299d90127009dfc32765531ccc475a`
- 600276 PDF SHA256：`9afafa94c439ab186a8d5f82ba83c383d5df84aa8fa02236de8d573a4eea0a42`

披露记录注意：供应商2025-06-30对比期的publish_date也可能是2026-08-21（当前披露版本），并非该报告期的首次公告日。界面使用“来源所示披露日”，不据此声称历史首次可得时间；首次披露和修订链仍属TD-089。

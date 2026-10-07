# 交易日周期排行榜契约 · 2026-10-07

GET /api/discovery/rankings?metric=change|main_net|gross_in&period=latest|previous|3|5|10|20|60&refresh=false

RankingResult：metric/period/status(ready|partial|unavailable)/data/start_date/end_date/
fetched_at/source/scope/unit(percent|CNY)/cached/reason。每行code/name/value/price(nullable)/quoted_at。
统计日按上海时区官方交易日历；latest为最近交易日，previous为其前一个交易日；
多日包含结束日，日期必须与来源记录吻合。早盘9:15前用上一交易日。日期不是抓取日期。

东方财富原生涨幅支持1/3/5/10/60日；主力净流入支持1/3/5/10日，主力口径大单+超大单。
直接由所选字段降序取沪深前50候选，并标注源范围；不拿当前20只重算历史排行榜。
股票总流入字段尚无可核验来源，gross_in返回unavailable，不用净额/成交额替代。
20日、长周期资金历史暂未接通，unavailable明确缺口。previous只读同指标准确日期的
已保存latest收盘快照，无历史时不可用，不用最新榜冒充昨日。旧gainers接口保留兼容。

网络故障尝试既有东方财富延迟端点（非独立验证）；最新单日涨幅允许新浪旧榜降级，
标注不同候选范围。其他周期不可跨指标/周期fallback。SQLite按指标/周期/截止日存收盘
快照；120秒内存缓存按指标和周期隔离。刷新失败可使用对应日期存档并标partial。
部分无效行排除并计数，空数据不填零。422为非法参数，来源故障200+unavailable。

这轮仅提供已存在区间与明确可用性，未宣称已补足全市场20/60日资金历史。

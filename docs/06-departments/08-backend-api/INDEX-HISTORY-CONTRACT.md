# 指数历史 v1

GET `/api/market/indices/{symbol}/history`，只接受 sh000001 / sz399001 / sz399006。
200: symbol、name、source=tencent、verification=single_source、price_unit=points、
volume_unit=source_native、fetched_at（带时区）、bars（date/open/high/low/close/volume）。
只读取明确市场身份的 day 序列，拒绝空值、非有限值、错误OHLC、重复/倒序/未来日期。
404 未支持的指数；502 上游/校验失败，可手动重试，不返回股票或示意替代数据。
腾讯现有行情来源，单次最多640根日线，实际起止取 bars；不承诺上市以来全部历史。
可含当日尚未结束日线。成交量保留来源原始单位，未确认前不标股/手、不换算。
周/月线由这批日线聚合，首尾可能不完整；指标随所选周期计算。

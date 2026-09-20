# RAW备用日线展示契约

2026-09-20用户批准腾讯不复权备用。GET /api/stocks/{code}/kline-raw-display，六位代码，否则422；复用TencentRawDailyKlineSource，90天查询窗，只含已结束交易日。Pydantic RawDailyDisplay/OpenAPI为唯一字段定义。source=tencent、price_basis=raw、verification=single_source固定，bars中Decimal价格序列化为字符串、amount可空；data_start/end真实来自返回数据。不进入AI证据或技术指标计算，不合成周/月线，不拼接前复权序列。

上游失败返回200状态信封（status=failed/unsupported/success_empty等），bars=[]、日期null及安全error_code；无自动重试，用户可以重新请求，单次上游8秒超时。状态不表示双源验证或完整历史覆盖。前端15秒截止、五分钟缓存成功结果，显示来源、日期和不复权标签。

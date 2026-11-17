# ETF 日线展示契约 v1

2026-11-04 当日展示修订冻结（响应字段不变）；Pydantic 模型见 `backend/etf_contract.py`，实现见 `backend/etf_kline.py`。
ETF 页面和 ETF 研究可复用 `async get_etf_kline(identity: EtfIdentity, days: int = 90, *, include_today: bool = False)`；
不调用股票财务、付费模型或已有股票证据晋级流程。

## 请求与身份

`GET /api/etfs/{code}/kline?days=90`。code 必须为六位数字，days 为 30—730 个日历日，默认90。
服务端从已有新浪 ETF 目录取得 `EtfIdentity`，使用目录里的 symbol（如 sh560780、sz159915），
不把调用者提供的名称或代码前缀当成基金身份。目录不存在返回404 `ETF_NOT_FOUND`，
目录读取失败或等待超过8秒返回503 `ETF_CATALOG_UNAVAILABLE`，错误结构沿用 ETF 详情路由；
输入不合法返回 FastAPI 422。身份确认后，历史行情总等待至多10秒，单源至多4秒，最多四组并发。

## 200 响应

- `schema_version: 1`、`identity: EtfIdentity`。
- `status: ready | empty | unavailable`；`source: tencent | sina | null`。
- `price_basis: raw`、`price_unit: CNY`、`price_tick: 0.001`、`volume_unit: fund_units`、
  `verification: single_source`。
- `fetched_at` 为带时区采集时间，不能代替行情日期。
- `requested_start`、`requested_end` 为所请求日历区间，展示路由结束日期为北京时间当日；内部研究默认仍截止昨日。
- `data_start`、`data_end` 为返回行情首末日期，无数据时均为 null。
- `bars` 按日期严格升序，每项 `{date, open, high, low, close, volume}`；
  date 为 YYYY-MM-DD，OHLC 为人民币数值，成交量为整数基金份额。
- `diagnostics` 按尝试顺序记录 `{source, status: success | empty | failed, error_code}`；
  错误码为 `request_timeout | upstream_request_failed | invalid_upstream_payload` 或 null。
- `limitations` 解释不复权、交易价格非净值、时间覆盖及单源状态。

腾讯优先，请求 day 原始不复权字段。展示路由显式 `include_today=True`：已返回今日则立即可用；
腾讯失败、空数据或仅到昨日时尝试已有新浪来源，选择末日较新的整套序列，同末日保留腾讯。
备用源失败或总截止到达时保留已取得序列，不因备用故障清空图表；不会拼接两源。
内部研究/入场计划使用默认 `include_today=False`，仍以第一个可用来源返回昨日及之前日线。
任一来源有有效数据即 ready，之前的失败只保留在 diagnostics，不令整个行情降级。
两源都成功返回空数据才是 empty；一错一空或都失败均 unavailable，不冒充已确认无行情。
历史接口不自行缓存；消费者可缓存成功结果，刷新失败应保留旧图并标明日期。

腾讯原始成交量以手为单位，乘100转为基金份额；新浪为份，不再乘100。
复用已有上游地址、身份解析与 RAW OHLC 校验，ETF 显式采用0.001元步长，
不修改 A 股默认0.01元步长。两源序列不拼接、不平均，缺成交额不编造。
展示路由包含上游返回的当日日线，不再强制截断到昨天；不从实时报价补造 OHLC/成交量。
前端可接受 `requested_end == fetched_at` 的北京时间日期，但仍拒绝未来日期。
当日蜡烛按采集时点标识：北京时间15:00前为未收盘（日线收盘字段代表当时最新价），
15:00及之后为收盘后采集，仍以上游返回为准；缓存不能随本机时间推进自动变成收盘数据。
周/月线聚合包含所获当天记录，尾部周期可能未完成。来源尚未提供今日时显示实际截止日，
休市/无当日记录不补零或复制昨日；保留刷新入口。研究与图表取数边界独立，不改变研究默认。
新上市 ETF 可返回已有的短序列，不能因为没有上市前行情拒绝整张图；起止日期如实显示。

## 验证

`tests/test_backend/test_etf_kline.py` 覆盖三位价格、基金份额单位、沪深身份、错误来源回退、
日期顺序和未来日期、展示当日纳入与研究默认排除、跨北京时间边界、较新备用源及失败保留、空与失败区分、请求范围、目录失败、总超时、股票精度不变。
实网只读探测：560780 的腾讯/新浪均返回2026-10-26 OHLC 0.781/0.790/0.747/0.749；
腾讯5168260手转516826000份，新浪516825982份（差18份在腾讯手级精度内）。
腾讯2024-05-10至2026-10-26返回597行，深圳159915同区间也返回597行。
这些探测证明当次调用可用，不承诺上游持续可用。

2026-11-04 定点只读探测：588110 腾讯日线包含2026-11-04，开0.386、高0.429、低0.382、收0.426，
原始2438380手转换为243838000份；缺失根因为请求与前端日期过滤，不是上游没有日线。

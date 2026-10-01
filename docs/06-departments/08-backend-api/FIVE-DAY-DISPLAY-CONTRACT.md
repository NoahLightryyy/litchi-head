# 五日分时展示契约 2026-10-01

GET /api/stocks/{code}/intraday-five-day-display，六位股票代码；Pydantic FiveDayDisplay冻结字段：symbol、source=tencent、price_basis=unverified_raw、verification=single_source、status=partial/empty/failed、fetched_at、days、points(timestamp带时区/close正有限)、incomplete_days、missing_days、error_code。成功仍partial（单源）；失败200+failed+空数组，非法代码422，无自动重试，手动重取。底层HTTP10秒/外层15秒、单锁等待1秒，30秒缓存上限32只；保留原抓取时间，不伪造报价时间。

复用已有腾讯day/query来源，仅另建展示投影；不改变single_source_shadow历史回填或AI证据门禁。校验交易日、身份、重复分钟、未来时间、有限正价格；只保留常规交易分钟，按时间排序最近最多五个来源交易日，少于五日/分钟缺失显式标注。连续图连接已返回端点，夜间休市与缺失日不插值；横轴保留日期分隔；不得从日线收盘价生成五日分时。2026-10-01实网300199返回9/23、24、28、29、30共1210点，无缺分钟/缺交易日。该数据用途仅图表展示。

前端交互：当日→五日→日K逐层缩小，反向放大；一次滚轮手势最多切一层，提供显式窗口按钮。日K保留既有前复权/不复权备用语义，不将分钟点聚合成假的OHLC。

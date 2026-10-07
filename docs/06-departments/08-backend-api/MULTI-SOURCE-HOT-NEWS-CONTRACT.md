# 首页多渠道快讯契约（2026-10-07）

GET `/api/market/hot-news` 保持 HotNewsEnvelope 字段不变。财新数据通、
新浪财经、东方财富并发采样，每渠道最多 100 条，总计最多 300 条，按发布时间倒序。
这是渠道采样，不是全网新闻或完整历史覆盖。来源可能转载同一报道，不构成独立交叉核验。

`meta.source_diagnostics` 使用现有结构，index_code 为 hot-news，source_id 为
caixin / sina / eastmoney。单渠道失败且仍有数据时返回 HTTP 200 partial，
failed_sources 和 limitations 标注缺口；两分钟缓存保留该诊断。全部失败时优先
返回已有过期缓存（stale），无缓存返回现有 503 HOT_NEWS_FAILED 或
HOT_NEWS_SCHEMA_INVALID。单渠道等待上限 12 秒，线程池最多 3 个工作线程。

date 缺失不补抓取时间。前端继续按标题合并、按真实发布时间筛选；渠道筛选应在
去重之前执行，以便查看同一标题在所选渠道的出处。新闻渠道数不等于独立证据数。

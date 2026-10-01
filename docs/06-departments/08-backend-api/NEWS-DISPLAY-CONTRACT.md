# XI-007 个股新闻展示契约 v1

2026-10-01冻结。Pydantic：backend/news_display.py；路由：backend/routers/news.py。

GET /api/stocks/{六位代码}/news-display?days=30。days仅7、30、90；按上海自然日含今日。默认30天；保留发布日期未知条目并显式标注，不宣称这些条目已落在该窗口。

响应为NewsDisplay本体（不包data）：schema_version=1、symbol、company_name可空、status、start_date/end_date、fetched_at、cached、items、sources、purpose=display_only。

- status：ready有效条目且当前两路采集无已知限制；partial有来源失败/截断/无效行/未知时间；empty两路完成但当前检索窗口未找到匹配；failed无法完成检索且无可展示条目。
- ready不表示全网完整、新闻已证实或多源交叉验证。当前来源：东方财富关键词搜索、巨潮资讯公告。未接通用网页搜索；新浪正式滚动证据保持原入口与策略。
- items：id、title、kind(announcement/report/mention)、published_at可空、time_precision(date/second/unknown)、association(official_code/title_match/excerpt_match)、provenance数组(source/publisher/url)。report指标题命中，不承诺全文审核；mention仅搜索摘要命中，不按行业推断关联。标题/时间归并重复条目，保留不同来源链接。没有生成式摘要、利好利空或投资评级。
- 新闻分钟/秒时间保留上游上海时区；公告按日期呈现，不制造具体时分。缺发布时间用null，抓取时间独立。无效/未来记录拒绝并标记局部限制。
- sources逐路给status(success/partial/empty/failed)、matched、scanned、total_candidates可空、error_code可空；候选数不是该股新闻数。错误码SOURCE_TIMEOUT/SOURCE_UNAVAILABLE/SEARCH_WINDOW_LIMITED/INVALID_ROWS_SKIPPED/PUBLICATION_TIME_MISSING，不返回底层异常。

HTTP200：ready/partial/empty。HTTP503：failed正文仍为NewsDisplay；服务繁忙/总截止为detail=NEWS_BUSY，Retry-After:5。422参数无效。前端需区分503正文，禁止默认为空。

每源10秒总预算，异步HTTP单次3秒、每源最多6页；聚合12秒总截止。已成功页面可以作为partial展示；当次失败不能抹掉另一源条目。最多4个不同key并发，重复symbol/days单飞；最多64个key、120秒短缓存（沿用旧新闻2分钟TTL），无自动重试。缓存fetched_at保留原值；失败不覆盖成功记录。未增加持久存储或生产定时任务。

前端先按类型筛选和关键词搜索，默认每页10条，显示当前抓取窗口内条目数，翻页不重新请求；窗口切换重新检索。局部失败须可查看来源状态；刷新失败可保留上一成功画面并说明失败，不冒充更新完成。

兼容：旧 /stocks/{code}/news 暂留给外部旧客户端，标记deprecated；新版个股页移除旧hook/API消费。/api/v1/evidence/news/aggregate和NEWS_EVIDENCE_POLICY原封保留；展示内容不会写入证据或辩论。旧路由删除需独立确认外部消费者退役。

验证：9项本契约测试及既有来源测试合计32项通过；前端消费者4项通过，含上海凌晨的日期精度验证。法国网络300199实测3.2秒、35条新闻候选经匹配分组+3条公告；独立3027浏览器显示38项，分类、原始日期、尾页、筛选及后端中断保留/恢复已验收。此为单次可达证据，不保证长期可用；3001集成仍待主窗口。

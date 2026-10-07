# 搜索与涨幅榜（2026-10-07）

GET /api/discovery/search?q=…：SearchResult(data,failed_sources,total)，每项code/name/kind
（stock/industry/concept）。空词不请求上游；股票目录和东财板块目录独立检索，最多100结果，
优先精确匹配，失败目录单独标记。stock跳/stock/code，板块跳/sector/code。

GET /api/discovery/gainers：GainersResult(data,source,scope,fetched_at,cached,failed_count,error)。
每项code/name/price/change_pct/quoted_at。新浪沪深A股涨幅前20候选逐个核验日期，未核验不补零。
不是全市场热度榜、不含完整北交所市场。排序仅为这些候选有效报价的涨幅降序。
缓存120秒，失败可保留旧数据并error=true；quoted_at是真实报价时间，不能用fetched_at替代。

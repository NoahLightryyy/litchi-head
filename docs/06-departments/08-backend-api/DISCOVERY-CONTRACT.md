# 搜索与涨幅榜（2026-10-07）

GET /api/discovery/search?q=…：SearchResult(data,failed_sources,total)，每项code/name/kind
（stock/industry/concept/etf）。空词不请求上游；股票、东财板块、ETF目录独立检索，最多100结果，
优先精确匹配，失败目录单独标记。stock跳/stock/code，板块跳/sector/code，ETF跳/etf/code。

GET /api/discovery/gainers：GainersResult(data,source,scope,fetched_at,cached,failed_count,error)。
每项code/name/price/change_pct/quoted_at。新浪沪深A股涨幅前20候选逐个核验日期，未核验不补零。
不是全市场热度榜、不含完整北交所市场。排序仅为这些候选有效报价的涨幅降序。
缓存120秒，失败可保留旧数据并error=true；quoted_at是真实报价时间，不能用fetched_at替代。

## 2026-11-04 ETF组合搜索（响应结构不变）

- 先做NFKC全半角归一、大小写归一；排序为精确代码、精确名称、连续包含、ETF关键词组合，
  同档按kind/code稳定排序。仍按kind/code去重，total是全部匹配数，data最多100条。
- ETF名称的主题与管理人不要求连续或同序，例如“半导体广发”“广发半导体”
  “半导体广发基金的ETF”均可匹配真实目录中的560780“半导体设备ETF广发”。
- ETF/基金/基金公司/基金管理与语法助词“的”只作检索辅助，不改变目录身份。
  所有实质词须在同一候选名称中命中；中文片段至少两字、字符不能重复透支，
  数字/英文词需完整匹配。不是单字乱序、编辑距离、主题同义词或模型猜测。
- 普通股票/板块保留连续名称与代码搜索；目录失败标记与错误响应不变。
- 仅“基金”或“ETF”可浏览匹配目录；未新增数据源或远程语义搜索。

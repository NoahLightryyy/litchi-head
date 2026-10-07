# 多渠道历史新闻库（2026-10-07）

GET `/api/news-archive?days=7&channel=&q=&page=1&as_of=`。
六渠道本地SQLite按稳定文章ID幂等保存；每次轮询取最新页，再按持久游标补最多3页历史，
并发3源、每请求10秒超时、每批结束后5分钟再运行。历史目标最长3年，受来源可访问范围限制。
不删除已有记录。仅应用运行时采集，离线期间不保证连续覆盖。

响应 ArchivePage：data（id/channel/title/date/source/url/content）、total/page/page_size、
start_at/end_at、coverage及limitations。page_size=100，后续页传回end_at为as_of固定上界。
coverage每渠道包含入库count、最早/最新发布时间、last_success、history_status、error，
complete始终false：已观察范围并不证明历史完整。running/pending/failed/stalled/exhausted/window_limit
分别表示补抓中/待开始/请求失败/重复页停滞/接口结束/达到本轮3年边界。
失败保留已有记录，不把空列表或抓取时间冒充发布时间。来源失败不影响其他来源。

辩论分别检索最近7天/93天/1095天已入库相关公司报道，按短中长期区分研究背景，
不改变用户已确认的预测周期或交易准入规则。模型可提出补证关键词，再从库中检索一轮，
保留未命中/缺口事实，最终仍有不足时明确insufficient。

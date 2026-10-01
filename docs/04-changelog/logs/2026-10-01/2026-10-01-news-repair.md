# 2026-10-01 XI-007 个股新闻修复

用户要求开始修复。沿用独立worktree news-search-coordination / codex/news-search-coordination，在规划提交82ab4f1之后实现；未更改主窗口源码或重启8000/3001。浏览器实际采集时间为北京时间2026-10-02凌晨。

## 实现与契约顺序

1. 数据部门只读盘点回执确认现有CninfoDirectAnnouncementSource是通用公告源，纠正初始计划中的错误。法国网络东财搜索与巨潮可达，新浪全局流首屏未命中300199。行情失败不应阻塞新闻身份获取。
2. 后端3cd0644先提交：backend/news_display.py、routers/news.py及main.py注册，新NewsDisplay v1与来源/错误状态冻结。异步有界两源查询、主体核验、去重、原始日期、null时间、并发/单飞/120秒缓存。旧新闻路由deprecated但未删除；正式新闻证据和辩论不改。
3. 前端随后消费：NewsFeed按代码独立查询，7/30/90天、相关新闻/公告/提及分类、关键词过滤已取得内容、10条分页、原文独立链接；刷新失败保留上次结果。严格消费者校验，删除旧hook/API/type；Next代理目标可配置以便独立预览。

## 验证

- Python：tests/test_backend/test_news_display.py + tests/test_data/test_news_evidence_sources.py + tests/test_data/test_cninfo_direct_provider.py，32 passed。
- Ruff全库通过；pyright src/ backend/零错误。
- 前端消费者4项通过，包含错股/危险链接/重复/nan/未来日期、公告日期精度及上海凌晨、分类/分页。
- pnpm lint与生产构建通过。
- 真实France网络查询300199：约3.2秒、38项。3027浏览器显示7条相关新闻、3条公告、28条摘要提及；公告日期不是抓取时刻。
- 浏览器分类及尾页4/4共8条、无匹配关键词提示通过。仅停止独立8027后端：刷新失败提示可见、旧38条和原检索时间保留；重启独立后端后刷新恢复。正式3001未触碰。
- 截图本机logs/news-browser-ready.png。预览http://localhost:3027/stock/300199，API8027；两个进程只服务本隔离工作树。

## 状态与协作

数据会话完成盘点，本侧实现API/前端及实现者验收；后端会话另有retro任务，已通知避免重叠；主前端窗口负责后续集成，不在其脏树中操作。没有独立QA/风控签收，不冒称完成。

XI-007尚待3001集成验证；TD-081保持开放。未接通用全网搜索、未读取全部原文、没有持久新闻展示缓存或新生成式摘要；单次38项不等于完整覆盖或长期稳定。默认展示层不自动成为投资决策证据。学习卡58与部门交接、计划、旧引用同步更新。无推送、无合并。

# 新浪备用榜单契约（2026-10-01）

用户授权其他来源补字段。审计发现新浪涨跌概览与资金服务同ID涨跌幅不一致，禁止交叉覆盖；资金服务原生返回行情与净流入，独立分类口径显示。

GET /api/market/sectors?source=sina&sort=net_flow。默认source=eastmoney不变。SectorsEnvelope添加 source=sina；id=sina:new_*或sina:gn_*；fund_flow=null（主力未知），新增net_flow为新浪净流入亿元；as_of=null（逐板块报价时间未知），新增service_updated_at为MoneyFlow.ssi_get_extend(id=2)时间。服务全局时间与逐条报价时间不可互换。source=sina必须meta.status=partial，带SINA_BOARD_BASIS、FUND_FLOW_UNAVAILABLE、SOURCE_SERVICE_TIME_ONLY限制。支持net_flow/change_pct排序；fund_flow请求返回upstream_order，绝不偷换主力排序。失败503/MARKET_SECTORS_FAILED；不自动重试。

MoneyFlow.ssl_bkzj_bk采用源码声明：avg_changeratio为比例乘100；netamount原单位元（官网表展示万元乘1e-4），API除1e8为亿元。cate_type 0行业/1概念，完整count分页、唯一代码、有限数值和前后服务时间稳定检查；最多2分类并发、沿用8秒预算/30秒短缓存，不用于AI/交易。官网依据https://money.finance.sina.com.cn/moneyflow/及其脚本https://n.sinaimg.cn/finance/cnstock/pc/zjlx.z.js?ver=1.1。

2026-10-06 用户要求主力净流入与净流入同时保留：首页及行业研究改为两个来源独立请求与展示，取消只在东财503时触发新浪的整榜替代策略。每源独立查询缓存、排序、刷新、取消和错误状态；东财历史快照不阻止新浪加载。响应来源必须匹配请求，拒绝跨源混入；保留各自失败诊断。新浪板块链接到站内 /sector/sina/{code}，来源外链仅供核验；不生成东财/sector/BK详情，也不按名称建立关系映射。净流入单列正确口径，仍显示主力缺失与全局服务时间限制。无独立第二源交叉校验。

实网Provider 229行（48行业/181概念），3.3秒；service_updated_at=2026-09-30T15:01:48+08:00。第三方未来可变，当前测试不保证长期可用。持久化仅原东财store，新新浪源目前内存缓存；断源无缓存时503，继续TD-081持久扩展待办。

## 站内研究补充契约（2026-10-01）

GET /api/market/sina/sector/{code}/stocks?page=1，code限定new_*或gn_*，page 1..500，固定20条、net_flow降序。Pydantic SinaMembersEnvelope.data为source=sina、board_code、page、page_size=20、total、stocks、service_updated_at、cached。stock含code六位、name、price元、change_pct百分数、net_flow亿元。MoneyFlow.ssl_bkzj_ssggzj与ssc_bkzj_ssggzj采用bankuai=0/code或1/code，未使用名称映射。服务时间前后校验、8秒预算、30秒缓存（最多64页）、非有限数值/缺页拒绝。空页meta.empty，有数据meta.partial，均带SINA_MEMBER_BASIS。503/SINA_MEMBERS_FAILED允许手动重试，无自动重试；422非法参数。失败只影响成分股模块，板块概览单独请求既有sectors接口。全局服务时间不保证成员与榜单逐条行情同步，不将成员合计冒充板块统计。/brief当前仅指数摘要，不是LLM输出。

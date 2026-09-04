# 首页展示与健康恢复集成 — 2026-09-04

## 用户口径与范围

用户本任务明确要求“只要有一个可以就行了，三项验证只是标注在旁边，把数据拿出来就行”。
首页每指数有一个身份、价格、时间有效的来源就展示；多源验证和缺源/冲突作为旁注。
正式 AI/风控/交易的证据门禁未修改。三指数是三个不同标的，互相不能填补价格。
板块行业/概念是分类，不是独立供应商；两路实际都是东方财富，双失败不能生成榜单。

## 冻结契约

- 健康：HTTP 200，`DataSourceHealthResponse.status=ok|degraded` 不变。
  `DataSourceEndpointHealth.current_status=healthy|failed|empty` 必填。
  `total_calls/success/empty/failures/failure_rate` 和 summary 的总量是历史，进程内保留。
  `last_error/last_error_code` 表示当前故障，成功清空；空数据的 code 为 null。
  安全文案分别为“数据源请求失败”“来源数据冲突”“数据源返回空数据”。
- 指数健康按来源三项整批发布，任何失败/冲突则 failed，无失败但有空结果则 empty，
  全成功才 healthy。冲突码优先，其余失败码按字典序确定，避免完成顺序改变诊断。
  请求开始分配批次序号；老批迟到只累加历史，不能覆盖更新完成批。快照与发布共用锁。
  未完成请求保留最后完成观察；没有自动到期、主动探测或重试，健康不是实时可达保证。
- 指数：有效单源 HTTP 200 partial，保留 INDEX_SINGLE_SOURCE。双源价/时冲突也为
  HTTP 200 partial，保留 INDEX_PRICE_CONFLICT / INDEX_TIMESTAMP_CONFLICT 及
  conflicted 逐源诊断，`source_count=1`、`display_source` 表示展示所用 upstream。
  选较新时间，平局以 upstream_id 字典序最大值确定；不平均，不称验证通过，不写共识缓存。
  双源共识的 display_source=null、source_count=2；单源为所选 upstream。
  全部失败且无可用缓存仍是 HTTP 503 MARKET_INDICES_FAILED。
  MARKET_INDICES_CONFLICTED 保留兼容错误码；有效来源间的价时冲突不再触发 503。
  双失败的 30 秒已核验 stale 缓存、五态以及客户端原有轮询/重试保持不变。
- 板块：沿用 20211fe 的共享 15 秒预算、固定 2 线程、有界等待和详情失败契约；
  单路有数据返回 partial，双路异常为 503 MARKET_SECTORS_FAILED。没有换源/新增源。

## 前端必须消费的改动

本任务未修改 `C:/Users/ASUS/Desktop/litchi-head-frontend` 或当前预览服务。
以下更改由前端集成任务在自己的分支完成：

1. `frontend/lib/backend-health.ts`：逐项严格校验 current_status 的三个值。
   healthy -> pass；failed -> fail；empty -> warn（或现有警告状态），保留安全 last_error。
   顶层按 status 与 summary.failing_endpoints / empty_endpoints 判断。
   删除 `rawCheck.failures > 0` 和 `summary.total_failures > 0` 的当前故障判断，
   不要在新字段缺失时退回历史判断，应返回诊断不可用。
2. `frontend/lib/types/market.ts` 与 `market-contract.ts`：接受并校验
   `display_source: string|null`。已有 partial 数组解析可接受冲突时的有效报价；
   不放宽 success 时 source_count>=2、价格/时间合法性和 stale 缓存校验。
3. 指数卡逐项显示“单源/双源验证/来源冲突”、时间和 display_source；
   INDEX_PRICE_CONFLICT / INDEX_TIMESTAMP_CONFLICT 旁注，不用健康告警隐藏 data。
   `market-notice.ts` 对 conflicted 来源应写“冲突”而非笼统“请求失败”。
4. 补消费者用例：历史 failures>0 但 current_status=healthy；失败后空结果；未知状态；
   三指数共存 mixed source；全指数冲突但 HTTP200 partial 有数据且标注来源。
   最后接入现有预览做浏览器复验；本任务只有独立端口的 HTTP 烟测，没有替换预览。

## 实网上游证据与未解决限制

运行环境 Python 3.12.14 / AKShare 1.18.94，独立 18082 端口，测试服务已停止。

| 场景 | 结果 |
|:---|:---|
| indices 两次 | HTTP200 partial，0.14s / 0.12s；三项均新浪单源 |
| 上证 | 3930.1164；2026-09-04T15:35:31+08:00 |
| 深证 | 13516.969；2026-09-04T15:00:03+08:00 |
| 创业板 | 3286.546；2026-09-04T15:00:03+08:00 |
| 健康 | 新浪 healthy、东方财富 failed；summary 1 healthy / 1 failing |
| sectors?sort=fund_flow | 14.58s，HTTP503 MARKET_SECTORS_FAILED；industry/concept 均失败 |

东方财富原 `https://push2.eastmoney.com/api/qt/stock/get` 的 httpx 环境代理开/关、
加 Referer、相同服务编号主机及参数变体都出现响应前断连 RemoteProtocolError。
这排除了“只有 HTTPX 环境代理配置”作为唯一解释；没有证据定位是远端还是中间设备断开。
没有更改系统网络设置，也没有采用延迟节点替代实时接口。

AKShare 板块适配器使用 requests，自动读取 Windows 注册表代理 127.0.0.1:7897，
即使没有 proxy 环境变量也会走它。行业/概念实测分别约 5.19s/14.14s 报 ProxyError。
使用同参数直连 requests/httpx 又出现 RemoteDisconnected/RemoteProtocolError，
所以简单关闭代理不能声称已修复。少数简化 clist 请求曾 HTTP200（industry 496 / concept
504），随后相同构造也断连，不能用偶发成功作为稳定修复。SDK 分页自带等待和重试，
外层仍受既有有界预算保护。暂未找到可复现、通过校验的请求构造修复。

TD-082 的代码修复已交付，待前端消费/浏览器联合关闭；TD-081 的时延修复完成但
板块真实数据仍不可用。上游不可用仍需恢复原连接，或用户另行批准更换/新增来源。

## 集成到 174e476

本分支从 20211fecbff3bd91095711beaf13d847781a7e9d 开始；174e476 是它的祖先。
最终准确冻结 SHA 以任务交付消息为准。不推送，不动共享 main。
在集成任务保存自己尚未提交的日志/债务后，按顺序 cherry-pick：

```text
git cherry-pick 20211fecbff3bd91095711beaf13d847781a7e9d
git cherry-pick <本任务最终交付的健康恢复提交SHA>
```

或者在独立集成分支合并 `codex/backend-health-recovery`。TD-082 与当日预览日志来自
前端未提交变更，冲突时合并记录，保留本次真实烟测和前端自身工作，不能覆盖脏树。
合入后完成上述前端消费修改并执行强制闸门，再由原预览任务更新它管理的服务。

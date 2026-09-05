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

本分支从 20211fecbff3bd91095711beaf13d847781a7e9d 开始；174e476 与其从 bdc5ba5 分叉，不能直接快进。
最终准确冻结 SHA 以任务交付消息为准。不推送，不动共享 main。
在集成任务保存自己尚未提交的日志/债务后，按顺序 cherry-pick：

```text
git cherry-pick 20211fecbff3bd91095711beaf13d847781a7e9d
git cherry-pick <本任务最终交付的健康恢复提交SHA>
```

或者在独立集成分支合并 `codex/backend-health-recovery`。TD-082 与当日预览日志来自
前端未提交变更，冲突时合并记录，保留本次真实烟测和前端自身工作，不能覆盖脏树。
合入后完成上述前端消费修改并执行强制闸门，再由原预览任务更新它管理的服务。

## 前端预览集成验收（2026-09-04）

`codex/frontend-preview-recovery` 已合入两个冻结提交，完成上述前端消费与 37 项测试。当前 3000/8000 预览来自此隔离工作树；生产构建页面与实时 DOM 确认新浪不再误报，卡片标记单源与新浪。板块仍为真实上游失败，约15秒返回503。快照节点候选需用户确认可能延迟的时间口径后再接入。


## 第二轮：板块快照候选（待用户确认，尚未接入路由）

父任务反馈预览已集成前轮修复，板块仍 15.061s / 503；本轮继续排查。
AKShare 1.18.94 的行业列表调用 17.push2；概念依次调用 79.push2、17.push2、push2。
每个 HTTP 请求最多重试三次，每次请求 timeout=15s，并有指数退避及随机等待。
成功后每个分页另有 0.5–1.5s 等待；概念列表还存在没有业务 TTL 的 lru_cache。
因此概念第一页面最坏就有 9 次 HTTP 尝试，外层协程取消不会终止 SDK 线程。
既有 BoundedSyncRunner 限制残留线程数量，但无法让已断连的端点恢复数据。

官方页面脚本 `https://quote.eastmoney.com/center/static/build/index.js` 当前含游客
pushguest 的 clist 路由。本机直接请求旧接口/游客接口及 curl_cffi Chrome 模式均断连。
浏览器官方页导航超时，未取得页面成功证据；没有登录、读取账户资料或改变任何代理。

同一东方财富的 `https://push2delay.eastmoney.com/api/qt/clist/get` 已多次完整成功。
这是同一供应商的快照候选，不增加独立来源数量。节点名称及上游响应不能证明零延迟，
因此必须旁注“东方财富快照（可能延迟）”及时间，不称实时验证通过。
AKShare 项目问题追踪也有相同旧主机断连/快照节点可用的报告：
[issue 7230](https://github.com/akfamily/akshare/issues/7230)；该报告不构成延迟保证。

已实现独立候选 `src/data/providers/eastmoney_boards.py`，没有被 backend 路由导入：

- 原行业/概念过滤条件分别保持 `m:90 t:2 f:!50` / `m:90 t:3 f:!50`；
  fltt=2 保持数值单位，f62 为真实净流入，不能从涨幅估算；
- Pydantic 冻结 BoardQuoteSnapshot / BoardSnapshot；code 必须 BK+4位、市场必须90、
  名称非空、时间戳有效，涨幅与资金流须有限值；资金流缺失保留 null；
- 分页 pn/pz=100，按代码稳定排序，检查全量总数、逐页长度和跨页唯一ID；
  页损坏/总量变化/重复ID/非板块身份均拒绝整类数据，不伪装完整榜单；
- 单类总预算8秒（含锁等待），单页最多3秒，无SDK重试和分页 sleep；
- 每分类一把锁合并同时到来的请求；仅完整非空结果缓存30秒，缓存返回 cached=true，
  保留上游 as_of 与首次 fetched_at。过期后失败不得续命旧数据；
- `possibly_delayed=true` 和 `source=eastmoney` 固定保留，不能把快照当第三个验证来源。

候选实测（还不是 /api/market/sectors 线上恢复）：

| 请求 | 数据量 | 耗时 | 事实 |
|:---|:---|:---|:---|
| 初始分页完整采集 | 行业496 / 概念504 | 1.41s / 0.72s | 两分类ID无交叉，均市场90 |
| 新实例冷请求，双类并发 | 行业496 / 概念504 | 总0.250s | 本地缓存未命中 |
| 紧接热请求 | 同上 | <0.001s | 命中30秒进程缓存，不访问上游 |
| 六个并发热请求 | 每个返回完整对应分类 | 各<0.001s | cached=true |

本次所有板块上游时间均为 `2026-09-04T15:39:32+08:00`；这是上游数据时间，
不是接收时间，不宣称盘中零延迟。示例行业 BK1627 综合Ⅲ：+0.65%、净流入 -123314856；
概念 BK1753 光刻胶：-2.52%、净流入 -1529156176。没有造数或把缺失值当0。

父任务明确要求等待用户确认延迟口径。本轮只提交候选适配器、回归和证据，
不切换现有板块路由、不修改前端、不动3000/8000。批准后才接入市场路由，
增加 as_of/来源/可能延迟旁注，处理 nullable 资金流，做独立端口的完整API冷/热烟测。
拒绝则保留现有接口，不把待确认候选说成已经上线。


### 分类审计补充：不是1000个平行行业

[可复现原始报告](board-snapshot-evidence-2026-09-04.json)保存11页的请求参数、HTTP响应
SHA-256、每页count/total/所有BK代码、官方目录哈希、全量代码集合比较及名称比较。
重跑（不修改路由）：

```text
python -m scripts.diagnose_board_snapshots --output board-snapshot-report.json
```

官方目录来自 [sidemenu_new.json](https://quote.eastmoney.com/center/api/sidemenu_new.json)。
官方页面脚本明示 type=1 地域、type=2 行业、type=3 概念；行业 flag=1/2/3 对应一/二/三级。
其 industry_board 总口径为 `m:90+t:2+f:!50`，分级分别用
`m:90+s:2+f:!50`、`m:90+s:4+f:!50`、`m:90+s:8+f:!50`。
候选保持原AKShare的总行业口径，不擅自只筛一级，也不能把三级与一级称为同层行业。

| 对象 | 官方目录 | 实际报价 | 集合/名称核验 |
|:---|:---|:---|:---|
| 行业 type2 | 497 | 496 | 全部属于行业且名称一致；无额外代码 |
| 一级行业 | 31 | 31 | 覆盖完整 |
| 二级行业 | 128 | 128 | 覆盖完整 |
| 三级行业 | 338 | 337 | 缺 BK1362 其他多元金融 |
| 概念 type3 | 504 | 504 | 代码集合与名称完全一致 |
| 地域 type1 | 31 | 0 | 未混入榜单 |

每个行情的 f13=90、f12符合BK身份；仅凭这两项只能证明是板块，
本次另用官方 type/flag 全量核验分类。行业/概念交集为0，页内及跨页无重复；
行业分页100/100/100/100/96，概念100/100/100/100/100/4。

样例：

| 分类/层级 | ID | 官方名称 |
|:---|:---|:---|
| 行业三级 | BK1627 | 综合Ⅲ |
| 行业三级 | BK1626 | 稀土 |
| 行业三级 | BK1625 | 钨 |
| 行业三级 | BK1624 | 其他小金属 |
| 行业三级 | BK1623 | 钼 |
| 概念 | BK1753 | 光刻胶 |
| 概念 | BK1752 | 2026中报预减 |
| 概念 | BK1751 | 2026中报首亏 |
| 概念 | BK1750 | 2026中报扭亏 |
| 概念 | BK1749 | 2026中报预增 |

BK1362 在官方目录中存在，但快照 stock/get 的 `secid=90.BK1362` 返回 `rc=100,data=null`。
去掉 f:!50 后行业 clist 的 total 仍496；因此不能断言是该过滤条件造成缺失。
已确认目录/可报价集合存在1项差异，具体停用或缺报价原因尚无权威证明，禁止补0或声称
覆盖官方全部497行业。上述“完整分页”只指当前查询返回的496项，不代表官方目录全覆盖。

后续接入需先确定展示口径，冻结分类/层级字段和 BK1362 缺口限制，再给前端消费；
不能只交1000行匿名平行板块。当前候选 BoardSnapshot.kind 区分两类，尚未冻结
HTTP分类/层级字段，也没有改变API原排序参数或默认顺序。等待用户时间与分类口径确认。


## 第三轮：用户继续后正式接入（2026-09-05）

用户在已解释同源快照可能延迟后明确“继续”；父任务确认采用并负责后续预览集成。
`/api/market/sectors` 已从旧AKShare列表调用切至审计快照适配器，仅影响首页列表；
板块详情、正式AI、风控和交易门禁均未改变。原并发、有界执行器和失败信封保留。

每项新增 `category`、`as_of`、`source`、`snapshot_may_be_delayed`；层级字段本轮不增加，
因为当前展示仍为一/二/三级混合总口径。接口以三个结构化限制分别声明快照可能延迟、
行业层级混合和BK1362目录缺报价。原 `sort`、`sort_applied`、资金流null及单类失败partial
语义不变；完整快照有真实资金流时仍执行请求排序。

独立18084端口真实HTTP烟测：

| 请求 | HTTP/状态 | 条目 | 耗时 | 缓存 |
|:---|:---|:---|:---|:---|
| 冷请求 fund_flow | 200 / partial | 496行业+504概念 | 0.266s | false |
| 热请求 fund_flow | 200 / partial | 同上 | 0.031s | true |

两次均 `sort_applied=fund_flow`、全部 `source=eastmoney`、
`snapshot_may_be_delayed=true`、`as_of=2026-09-04T15:39:32+08:00`；BK1362未返回。
冷/热前三名一致：AI应用、传媒、AIGC概念。只停止本任务18083服务，未操作3000/8000。

前端接线要求：类型与严格解析器加入四字段；条目按category分组或明确标签；
在榜单附近展示 `as_of`、可能延迟及三条limitations。现有渐进10条展开可直接消费1000项，
不要一次渲染全部。前端不得因partial丢弃data，也不得从名称推断category/行业层级。

单位冻结补充：Provider 的f62保留元，HTTP `fund_flow`统一除以1e8后返回亿元。
前端按亿元直接格式化，禁止二次换算。任一快照条目为null都触发FUND_FLOW_UNAVAILABLE并停止资金流排序。

生产请求保留原上游顺序字段：行业fid=f3、概念fid=f12；HTTP的fund_flow/change_pct排序行为不变。

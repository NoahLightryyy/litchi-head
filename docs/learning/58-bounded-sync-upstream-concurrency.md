# 58 同步上游并发：协程取消不等于线程停止

## 一句话

> 两个独立同步上游应在同一截止时间内并发等待，但超时取消只能停止等待者，不能强杀正在运行的 Python 线程。

---

## 为什么需要它？

### 问题场景

板块列表原来先等行业 15 秒，再等概念 15 秒。两路都异常时，独立超时串成约 30 秒；
板块详情则让同步上游的 `TimeoutError` 直接泄漏成未结构化 HTTP 500。

### 它的解法

列表两路同时启动，由一次 `asyncio.wait(..., timeout=15)` 决定聚合截止；详情把类型识别、
成分股和板块行情限制在同一个总预算。同步调用放入专用固定 2 线程执行器：取消前尚未
运行的任务可以撤销，已经运行的调用虽然不能强杀，也不会因重复 HTTP 请求无限增加线程。

---

## 项目里的真实代码

打开 `backend/routers/market.py`：

```python
done, pending = await asyncio.wait(tasks.values(), timeout=timeout)
for task in pending:
    task.cancel()

for call_id, task in tasks.items():
    if task not in done:
        failures[call_id] = "timeout"
```

字典插入顺序很重要：并发完成顺序不确定，但 API 的 `data` 和 `failed_sources` 顺序不能
因此漂移。`backend/async_utils.py:BoundedSyncRunner` 负责把取消后残留限制在固定线程数。

---

## 和直接 `asyncio.to_thread()` 有什么不同？

| 对比 | 串行 `to_thread` | 共享截止 + 有界执行器 |
|:-----|:-----------------|:----------------------|
| 双路最坏等待 | 15s + 15s | 约 15s |
| 单路成功保留 | 可以 | 可以 |
| 返回顺序 | 稳定 | 显式稳定归并 |
| 超时后的同步线程 | 默认池中继续运行 | 最多占用专用 2 线程 |

---

## 面试会怎么问

> **Q：取消 `asyncio.to_thread()` 的 Task，后台线程会立刻停止吗？**
>
> A：不会。取消只让协程不再等待结果；Python 没有安全的通用线程强杀机制。应让底层
> I/O 自带超时，并用有界执行器、整体截止时间和稳定失败契约控制残留工作的影响面。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_backend/test_market.py` 的共享截止测试。
2. 观察第一次双超时后立即重试时，两个阻塞 mock 的调用次数仍各为 1。
3. 运行 `python -m pytest tests/test_backend/test_market.py -q`。
4. 思考题：底层 HTTP 库已有连接/读取超时，为什么仍需要外层聚合截止？

---

**上一篇：[57｜可访问的数据视图](57-accessible-stateful-data-view.md)**

## 2026-09-28：大板块的分页也必须有界并发

`src/data/providers/eastmoney_boards.py` 的成分股先取第一页确认总数，再用最多8个线程采集其余页。
现有成员锁限制每个Provider仅一个批次；取消排队任务后等待正在执行的请求退出，随后关闭共享HTTP客户端，避免关闭仍被线程使用的连接。
所有页共用8秒预算，每次I/O最多3秒。超时后的线程收尾仍可能延长同步函数退出，外层HTTP总截止继续生效。
按代码f12稳定分页，结果按页码归并；数量变化、缺页、重复代码、超时都拒绝发布和缓存。
真实BK0596由39页串行超时改善为3.96秒/3874条，但目录502仍会阻塞整个详情：局部采集成功不能当成端到端成功。
自己试试：运行 `python -m pytest tests/test_data/test_eastmoney_boards.py -q`，观察Barrier测试如何证明8个页面同时执行。

## 将身份依赖与全量榜单分离

详情不必因整个榜单请求失败而丢失可独立核验的对象：`fetch_detail`使用官方目录确认身份，再按代码取同源单报价。必须比较两处名称和代码，不能从成分股反推板块涨跌幅。单报价也不可用时，现有契约仍失败关闭；若要返回部分详情，先设计nullable和局部失败契约，再让前端消费。

## 2026-09-29：部分成功必须贯穿类型与界面

板块身份有效不等于板块报价有效。BoardDetailSnapshot把quote显式建模为可空，API仅在身份和成分股链路成功后保留partial数据；详情change_pct允许null而榜单及成分股保持原数值类型。消费者要求partial和BOARD_QUOTE_UNAVAILABLE同时存在，界面用暂无数据，不能把缺值当0%。总览接口503也不等于所有子接口必然失败；反过来，一条子接口测试通过不代表整页可用。

## 协作也需要完成条件

可靠性任务拆为采集/快照（数据）、调度/恢复（基础设施）、状态契约（API）、展示（前端）、故障证据（QA）。消息送达不等于接单，代码测试通过不等于实网可用。每次交接提供输入版本、SHA、测试和阻塞，见DR专项计划。

## 最新成功数据与最近请求不是一回事

`src/data/board_store.py`将成功payload/hash和last_attempt/failures分开：失败仅增加失败信息；事务提交才替换成功快照。重开数据库时重新校验hash、类型和身份。迟到成功可以增加已有成功的版本，但不能消除时间更晚的失败诊断。
`board_runtime.warm_boards`用shield保护正在运行的I/O，取消时等待有界工作收尾，再退出服务，避免孤儿线程继续写数据。后台采集不意味着缓存自动满足实时性；读取陈旧数据的展示与风控策略仍须单独冻结。
自己试试：运行tests/test_data/test_board_store.py，查看断源后重开、损坏校验和关闭等待测试。

首页恢复示例：backend/routers/market.py 的 get_sectors 只在展示边界读取持久快照；stale 与原始 as_of 一起保留。缓存恢复不能放在共享 Provider.fetch 内，否则其他调用方可能把历史数据当实时证据。首次无缓存和损坏仍失败，见 tests/test_backend/test_board_display_restore.py。

2026-10-01实网验证补充：HTTP200只说明端点响应，必须继续解析字段、查分页和时间。新浪板块可达而新浪报价超时，不能按供应商品牌整体判断；同花顺第一页有表但第二页401，不能发布“完整快照”。跨源ID、资金口径、来源时间要分别核验；6秒阶段超时不等于6秒总预算。

### 补字段不等于补事实
本项目src/data/providers/sina_boards.py对分页前后服务时间做稳定性检查，但该时间只证明服务更新标记没变，不证明每条报价同时产生。backend/routers/market.py明确把它放在service_updated_at，as_of仍null；netamount进入net_flow，主力fund_flow仍null。frontend/lib/sector-feed.ts只对明确上游失败切换分类源，不能把所有异常都吞成备用成功。自己试试：运行tests/test_data/test_sina_boards.py查看缺页、重复、nan、错分类、跨刷新时间的拒绝路径，再运行frontend/tests/sector-feed.test.mts观察取消与后端断连为什么不触发换源。


### 来源链接不应替代产品导航
`frontend/lib/sector-navigation.ts`以来源命名空间生成内部URL；新浪new_*/gn_*不强行转换成BK。`src/data/providers/sina_members.py`使用官方bankuai=分类/代码并分页，逐页校验数值和服务标记，但不把分页之和当作整板块事实。`frontend/app/sector/sina/[code]/page.tsx`将概览与成员错误隔离。确定性统计与LLM输出应使用不同标签：当前/brief只汇总指数，显示“指数摘要”。
自己试试：运行frontend/tests/sector-navigation.test.mts，确认同名跨源板块不混排；请求 `/api/market/sina/sector/new_swzz/stocks?page=8` 并观察20条上限和余数；比较服务时间字段与行情as_of，解释为什么前者不能填进后者。

### 2026-10-01：检索能力与页面接通是两件事

个股旧新闻路由调用DataCollector，而news_runtime维护双源完整性证据。展示可用单源条目需要独立且明确的状态契约，不能为了让页面有内容去放宽正式证据门禁。空实现也不是备用源。来源发布时间、抓取时间和缓存覆盖范围分别描述不同事实。
自己试试（3分钟）：对照backend/routers/stocks.py的get_news与backend/routers/evidence.py的aggregate_news，画出各自调用路径；在src/data/news_runtime.py找出滚动覆盖不足的状态，解释为什么不能简单换一个前端URL。实现跟踪见[XI-007](../06-departments/00-cross-cutting/NEWS-RETRIEVAL-PLAN.md)。

### 展示检索的总截止与时间精度

`backend/news_display.py`为展示层使用异步HTTP和每源总截止：逐次3秒超时无法限制多页总时长，必须再套10秒总预算；取消协程关闭异步I/O，避免同步工作线程在请求结束后持续占用。两源并发、同key单飞，失败不覆盖已有成功缓存；正式证据适配及门禁不改变。

`frontend/lib/news-display.ts`将公告日期和新闻时刻分开。日期不能直接按UTC零点与北京时间凌晨比较，否则今天的公告会被错误当作未来。页面同时展示原始发布日期和独立检索时间；`NewsFeed`刷新失败保留已有条目并明确未更新。标题关联与摘要提及分组，不把所有候选当作公司事实。

自己试试（3分钟）：运行`tests/test_backend/test_news_display.py`中的来源截止与缓存测试，再运行`frontend/tests/news-display.test.mts`；将fetched_at改成北京时间00:30，比较同日公告日期与次日日期的校验差别。在独立预览关闭自己的后端，点击刷新，确认旧内容及原检索时间仍保留。
## 2026-10-01：前置查询不应依赖全市场下载

`backend/stock_identity.py`直接复用现有单股适配器取名称；缓存只保存身份，
不能把成功名称查询当成行情交叉验证。信号量限制超时后仍在运行的同步请求，
路由超时仅停止等待，不会杀掉底层线程。

`backend/routers/debate.py`先检查模型配置，再准备股票身份，再运行证据门禁和
推理。配置缺失属于需要修复环境的故障，盲目重试无效；身份查询超时属于
依赖暂不可用，不应归为未知程序错误。凭据检查仅返回是否配置，禁止返回密钥。

凭据加载与SDK初始化是两个边界：settings读到了Windows凭据，不代表SDK能从
环境变量读到它。`src/utils/llm.py`显式传入SecretStr；回归测试清除环境变量并
以测试凭据构造真实SDK，验证不依赖shell泄漏密钥。模型列表200也不证明生成成功，
模型名称、思考模式及结构化调用仍须分别验收。

自己试试：运行tests/test_backend/test_stock_identity.py与test_debate.py，
观察饱和时零上游调用、缺配置时零身份/模型调用、超时503的区别。
最后在已配置模型的环境验收真实结果；mock成功和明确失败提示都不能证明推理完成。

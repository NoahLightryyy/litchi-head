# ADR-013：多源证据完整性与 LLM 前失败关闭

| 字段 | 值 |
|:--|:--|
| 日期 | 2026-07-28 |
| 状态 | 🟢 决策已批准，分批实施中 |
| 影响范围 | data / debate / backend / frontend / storage |

## 背景

真实辩论门禁中，实时行情、新闻和行业采集同时失败，但系统仍执行 16 次 LLM
调用并返回结构完整的结果。用户无法从结果页判断输入证据已断链。旧 `DataSource`
还使用 `[]` / `None` 同时表示真实空结果、接口不支持和网络失败，业务层无法做
可靠的完整性决策。

项目需要优先使用免费来源控制成本，同时必须保留未来增加、替换免费或付费接口的
能力。多个接口也可能共享同一个真实上游，因此“适配器数量”不能直接当作独立
证据数量。

## 决策

### 1. 核心证据不允许自动降级

实时行情、K 线、新闻和行业等当前业务链必需证据必须完整。任一类别未达到策略
门槛时，在启动昂贵 LLM 链前失败关闭；该次任务的 LLM 调用数必须为零。

### 2. 来源身份分为两层

每个适配器必须声明：

- `source_id`：项目中的具体接入实现；
- `upstream_id`：真实提供事实的机构；
- `capabilities`：明确支持的证据类别；
- `discovery_only`：是否仅用于发现线索。

完整性按去重后的 `upstream_id` 计算。多个适配器包装同一家媒体仍然只算一个
独立来源。发现型来源不参与证据门槛。

### 3. 查询结果采用六态契约

所有新来源返回：

- `SUCCESS_DATA`
- `SUCCESS_EMPTY`
- `FAILED`
- `UNSUPPORTED`
- `STALE`
- `CONFLICTED`

`SUCCESS_EMPTY` 只表示上游成功完成查询并明确返回零条。网络失败、解析失败、
权限不足和包装层异常绝不能伪装为空结果。

### 4. 业务层只依赖统一接口

具体来源通过 `EvidenceSourceRegistry` 注册，由 `DataEvidenceService` 并发调度、
格式化和执行完整性策略，再输出统一 `EvidenceEnvelope`。新增或替换来源只增加
适配器与配置，不修改辩论引擎和 Agent 业务逻辑。

### 5. 低成本优先，但完整性标准不降低

首期优先评估 CNINFO、东方财富、新浪/财联社、GDELT 和自建 RSSHub。RSSHub 仅作
发现源。Tushare 等付费接口保留扩展位，是否购买由真实覆盖率和失败率决定。

## 明确不做

- 不把同一上游的多个包装器算成多源；
- 不用异常文本猜测“真实零数据”；
- 不因免费来源失败而让 LLM 自动基于残缺证据继续；
- 不让具体来源名称泄漏到辩论引擎和 Agent；
- 不在来源语义未通过真实烟测前接入正式失败关闭链。

## 当前实施证据

- `src/data/evidence.py`：来源身份、能力、六态结果、注册与完整性评估；
- `tests/test_data/test_evidence_sources.py`：11 项契约测试；
- `src/data/providers/cninfo.py`：首个 CNINFO 公告适配器基础；
- `tests/test_data/test_cninfo_provider.py`：10 项 AKShare 适配器测试；
- `tests/test_data/test_cninfo_direct_provider.py`：8 项公开端点直连三态测试；
- 真实烟测：平安银行 2026-06-01～2026-07-28 成功取得 3 条公告；
- 真实空门禁：平安银行 2026-07-27～2026-07-28 读取
  `totalAnnouncement=0` 并返回 `SUCCESS_EMPTY`；
- 直连适配器使用 `source_id="cninfo-direct"`，AKShare 适配器继续使用
  `source_id="akshare-cninfo"`，两者均声明 `upstream_id="cninfo"`，不会被误算为
  两个独立来源；
- TD-071 已关闭。
- `src/data/evidence_service.py`：并发调用同类通道，把请求范围、来源结果、统一条目
  和完整性评估打包为 `EvidenceEnvelope`；
- `tests/test_data/test_evidence_service.py`：7 项汇总契约测试；
- 同一 `upstream_id` 的多个适配器保留全部诊断结果，但只向业务信封输出一份条目；
- 来源抛出的未处理异常转换为可见 `FAILED / source_unhandled_exception`；
- 真实 CNINFO 空窗口已通过服务打包为
  `complete=True / SUCCESS_EMPTY / upstreams=["cninfo"]`。
- `src/data/providers/news.py`：东方财富个股搜索与新浪财经快讯两个独立新闻上游；
- `POST /api/v1/evidence/news/aggregate`：按股票和带时区时间窗并发采集，返回统一
  `EvidenceEnvelope`；
- 新闻条目跨节点只传标题、时间、发布媒体、链接、股票关联依据和内容哈希，默认不传
  原始正文；
- 业务条目按股票代码与规范化标题跨上游去重，两个来源的原始结果仍完整保留在
  `source_results`；
- 新浪公开快讯历史不足以覆盖请求起始时间时返回
  `STALE / time_window_not_fully_covered`，不会伪装成 `SUCCESS_EMPTY`；
- 2026-07-29 真实三天窗口门禁：东方财富取得 4 条；新浪因可访问历史不足标为
  `STALE`；最终 `complete=False`，证明完整性策略能够拒绝假双源。
- `src/data/news_store.py`：SQLite WAL 保存新浪元数据与连续采集覆盖，默认保留
  3 天，采集间隔超过 10 分钟即重置覆盖起点；
- `src/data/news_runtime.py`：集中持有 3 天窗口和必需上游策略，辩论层不硬编码
  具体来源；东方财富实时查询与新浪滚动缓存并发进入同一信封；
- 正式辩论图在 `collect_data` 后按完整性条件分支。不完整时直接结束并抛出
  `EvidenceIncompleteError`；API 返回 503、缺失上游和重试秒数；
- 专项门禁已证明新闻证据不完整时分析师与大师 LLM 调用数均为零。
- 股票主数据名称无法解析时同样在编排器前返回 503，避免只按证券代码查询新浪；
- 新浪采集达到分页上限但未读完整体时拒绝推进覆盖；乱序旧批次不得倒退成功水位；
- 轮询配置在服务开始接流量前校验，任务意外结束会把健康状态降为 `degraded`。
- `src/data/quote_runtime.py` 已将东方财富和新浪实时行情接入同一信封：成交量统一
  为股，连续竞价（9:30–11:30、13:00–14:57）采用 10 秒新鲜度、3 秒时间配对和
  0.01 元价格容差；午休、收盘集合竞价和收盘后不启动新辩论；
- `/api/v1/evidence/quotes/aggregate` 暴露逐源行情状态；正式辩论对缺源、陈旧、
  错时和价格冲突均在首个 LLM 前失败关闭。
- 正式编排器默认构造也自动接入行情门禁；新浪响应代码必须与请求匹配，北交所
  `4/8/920` 号段统一走 `bj`；聚合 API 默认每 IP 6 次/分钟。
- `src/data/providers/intraday.py` 将东方财富分钟 OHLC 与腾讯分钟收盘/累计量作为
  两个独立上游；两者原始成交量均从“手”归一化为“股”，不得因两个错误单位彼此
  一致就误认为语义正确；
- `src/data/intraday_runtime.py` 只对已结束分钟逐点核验：收盘价差不得超过
  0.01 元，累计量差不得超过真实沪深北样本校准的 500 股传输容差，已结束分钟
  集合必须一致；当前分钟保留为 `PROVISIONAL`；
- `/api/v1/evidence/intraday/battlefield` 一次返回规范分钟曲线、L1 战况快照和
  精简逐源诊断。L1 只报告 VWAP、开盘区间与量价事实，
  `attribution_supported=false`，不得输出“主力/量化/机构身份”；
- 分时端点采用上游的“分钟结束标签”：当前自然分钟为已结束条，下一分钟标签为
  正在形成的临时条。真实沪、深、北代表代码联调均通过。

## 后续门禁

1. 积累至少 20 个交易日的同分钟累计量基线后再启用 Relative Volume；
2. 将 K 线和行业证据迁移到同一完整性门禁；
3. PostgreSQL 完成外部编号、规范链接、内容哈希和修订幂等；
4. 前端展示缺失来源、时间范围、失败原因和重试建议；
5. 财联社在版权与跨节点传输边界确认后再启用。

## 决策确认

用户于 2026-07-28 确认：

- 数据源必须存在多家来源并汇总为统一格式；
- 最新信息与数据库比对，已存在的不重复入库；
- 实时行情、K 线、新闻和行业证据均不能自动降级；
- PostgreSQL 可以替代 SQLite；
- 当前不在付费接口投入过多，但接口必须保留多样性和可替换性。

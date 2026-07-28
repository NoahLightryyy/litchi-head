# 数据生命周期、容量与 Redis + SQL 调研

> 日期：2026-07-28
> 状态：架构方向与生命周期默认值已于 2026-07-28 获用户确认，技术迁移尚未开始
> 结论：以 SQL 为唯一事实源，以 Redis 为可重建的缓存/协调层，以 Parquet
> 为批量行情目录；是否立即引入 PostgreSQL + Redis，需通过后续端到端门禁。

## 1. 调研问题

本轮回答三个问题：

1. 哪些数据保存多久，容量如何增长？
2. 当前系统与候选存储能承受什么负载？
3. Redis、SQL、批量行情文件和 Agent 链如何分工，才能保证接口严密和故障可恢复？

本轮不迁移数据库，不修改真实业务数据，不把合成引擎数据当成生产承诺。

## 2. 当前存储事实

| 数据 | 当前实现 | 生命周期 | 风险 |
|:--|:--|:--|:--|
| 行情、K 线、新闻、财务 | `DataCache` 内存 TTL | 30 秒至 1 天；重启丢失 | 无容量上限、并发 miss 可击穿数据源 |
| episodic / reflective 记忆 | JSONL 追加 | 无清理规则 | 查询全文件扫描，文件永久增长 |
| working / semantic 记忆 | JSON 对象覆写 | 新值覆盖旧值 | 非原子文件替换，跨进程无锁 |
| 复盘记录 | 单个 `records.json` | 无清理规则 | 每次操作读写整个文件，并发可能丢更新 |
| 辩论 session / result | 进程内 `dict` | 进程生命周期 | 重启丢失、无淘汰、无恢复 |
| 静态知识库 | Markdown/JSON/NPY | 跟随项目版本 | 不是业务数据库 |

2026-07-28 盘点时，仓库 `data/` 共 33 个文件、约 3.26 MiB，几乎全部属于
静态知识库；尚无可用于推算真实业务增长率的长期记忆或复盘样本。

## 3. 生命周期默认基线（已确认）

| 数据类别 | 热存储 | 建议保留 | 归档/删除 |
|:--|:--|:--|:--|
| 最新行情 | Redis | 15～30 秒 | 过期即重取 |
| 决策时行情快照 | SQL | 长期 | 与决策一同归档 |
| 日 K 线 | Parquet/SQL 分区 | 15～20 年 | 按年归档 |
| 分钟 K 线 | Parquet | 热数据 1 年 | 3～5 年后按政策删除 |
| Tick / Level-2 | 暂不全量保存 | 无 | 仅按明确场景采样 |
| 财报及修订版本 | SQL | 永久 | 不覆盖旧版本 |
| 新闻正文 | 对象/文件存储 | 90～180 天 | 受数据授权约束 |
| 新闻元数据与决策摘要 | SQL | 2～5 年 | 可按年归档 |
| Agent 辩论、证据、置信度 | SQL | 长期 | 用户可删除 |
| 最终决策与实际结果 | SQL | 永久 | 审计与回测事实 |
| 任务进度、限流、锁 | Redis | 分钟至 24 小时 | 自动 TTL |
| 普通运行日志 | 文件/日志系统 | 30 天 | 滚动删除 |
| 错误与审计日志 | SQL/日志系统 | 至少 180 天 | 脱敏归档 |

用户已于 2026-07-28 验收以上保留期，现作为产品默认基线。实施时仍须执行
数据源授权、隐私和磁盘容量检查；若法规或数据供应商条款更严格，以更严格者为准。

## 4. 可重复本地基线

工具：

```powershell
python scripts/storage_baseline.py `
  --records 1000 `
  --payload-bytes 4096 `
  --lookups 100
```

测试口径：

- Windows + Docker Desktop；
- Python 3.13.12；
- 合成 Agent 决策记录，单条至少 4096 bytes；
- JSONL 模拟追加式记忆；
- JSON Object 模拟 `RetroStore` 的逐条全文件覆写；
- SQLite 使用 WAL、`synchronous=FULL`、100 条批量事务和主键索引；
- 顺序执行各后端，避免磁盘竞争。

### 4.1 100 条

| 后端 | 写入 ops/s | 查询 p50 ms | 查询 p95 ms | 占用 |
|:--|--:|--:|--:|--:|
| JSONL | 42,968 | 0.794 | 1.053 | 410 KB |
| JSON Object | 160 | 0.611 | 0.881 | 412 KB |
| SQLite WAL | 31,511 | 0.0049 | 0.0082 | 479 KB |

### 4.2 1,000 条

| 后端 | 写入 ops/s | 查询 p50 ms | 查询 p95 ms | 占用 |
|:--|--:|--:|--:|--:|
| JSONL | 51,259 | 8.686 | 9.548 | 4.10 MB |
| JSON Object | 52.9 | 6.909 | 7.471 | 4.12 MB |
| SQLite WAL | 19,448 | 0.0110 | 0.0142 | 4.68 MB |

观察：

1. JSONL 追加很快，但查询从 100 条到 1,000 条约增长 9 倍，符合全文件扫描特征。
2. JSON Object 写入从 160 ops/s 降到 52.9 ops/s，逐条全文件覆写已经出现明显增长成本。
3. SQLite 主键查询在 1,000 条时仍约 0.014 ms p95；空间比原始 JSON 多约 14%，换来事务、索引和幂等约束。
4. 这些数据不能外推成生产 QPS；真实 ORM、网络、磁盘、并发和备份都会改变结果。

### 4.3 PostgreSQL 17 临时容器

隔离容器、无持久卷：

- `pgbench` 规模 1、10 clients、4 threads、20 秒：
  - 1,437.9 TPS；
  - 平均延迟 6.952 ms；
  - 28,766 transactions；
  - 0 failed。
- 写入 10,000 条不可压缩约 4 KB JSONB 决策：
  - 执行约 764 ms；
  - 表与索引约 54 MB；
  - 单条主键查询约 0.086 ms。

首次使用重复字符的 4 KB 样本被 PostgreSQL TOAST 强压缩，容量结果失真，已弃用；
最终容量结果来自 `pgcrypto` 随机载荷。

### 4.4 Redis 7 临时容器

隔离容器、256 MB `maxmemory`、`noeviction`、无持久化，4 KB payload，
100,000 requests、50 clients：

| 操作 | requests/s | 平均 ms | p95 ms | p99 ms |
|:--|--:|--:|--:|--:|
| SET | 221,239 | 0.131 | 0.215 | 0.551 |
| GET | 237,530 | 0.118 | 0.183 | 0.455 |

这是 Redis 引擎内的短时合成吞吐，不能代表 FastAPI、序列化、网络数据源和
LangGraph 的端到端能力。

## 5. 同行产品参考

### Freqtrade

Freqtrade 默认用 SQLite 保存交易和持仓，使进程重启后仍能恢复；通过 SQLAlchemy
允许切换 PostgreSQL/MariaDB。它的启示是：个人或单实例产品可以从 SQLite 起步，
但存储接口不能绑定单一数据库。

来源：[Freqtrade Advanced setup](https://www.freqtrade.io/en/stable/advanced-setup/)

### TradingAgents

TradingAgents 把完成后的决策追加到记忆日志，并用按 ticker 拆分的 SQLite
checkpoint 保存 LangGraph 节点状态；成功后清理 checkpoint。它区分了“长期决策
记忆”和“崩溃恢复检查点”，值得直接借鉴。

来源：[TradingAgents GitHub](https://github.com/tauricresearch/tradingagents)

### NautilusTrader

NautilusTrader 的做法最接近我们的目标：

- 内存缓存有明确容量，例如每个 bar type/tick 默认最多 10,000 条；
- Redis/PostgreSQL 是可插拔缓存数据库；
- 大批量行情进入 Parquet Data Catalog；
- durable event store 是事实权威，cache 是可重建投影；
- 自定义数据使用统一 envelope，而不是让用户 payload 字段决定路由。

来源：

- [NautilusTrader Cache](https://nautilustrader.io/docs/latest/concepts/cache/)
- [NautilusTrader Data/Parquet](https://nautilustrader.io/docs/latest/concepts/data/)
- [NautilusTrader Event Sourcing](https://nautilustrader.io/docs/latest/concepts/event_sourcing/)
- [NautilusTrader Custom Data](https://nautilustrader.io/docs/latest/concepts/custom_data/)

### 可借鉴、不可照搬

| 同行做法 | litchi-head 采用方式 |
|:--|:--|
| SQLite 保存单实例交易事实 | 近期候选，先替换 JSON/内存状态 |
| PostgreSQL 作为可升级 SQL 后端 | 目标事实源，是否立即部署由门禁决定 |
| Redis 作为缓存/message bus | 只保存可重建状态，不保存唯一决策副本 |
| 每 ticker SQLite checkpoint | 改为每 session durable checkpoint，可恢复后清理 |
| 有界缓存 | 所有行情缓存必须同时有 TTL 与容量 |
| Parquet 市场目录 | 分钟 K 线和回测批量数据不进入普通事务表 |
| Event store 是权威 | 决策、回调、实际结果形成可重放审计链 |
| 统一自定义数据 envelope | API/Agent 数据统一 `type/schema_version/source/payload` |

## 6. 候选方案

| 方案 | 一键部署 | 并发/恢复 | 长期扩展 | 当前判断 |
|:--|:--:|:--:|:--:|:--|
| SQLite WAL + Parquet | 最简单 | 单写者，单机可靠 | 中等 | 近期最小方案 |
| PostgreSQL + Parquet | 中等 | 强事务、并发好 | 高 | 可作为第一阶段目标 |
| PostgreSQL + Redis + Parquet | 最复杂 | 缓存、队列、恢复最好 | 最高 | 目标架构，需端到端证据 |
| Redis + SQLite | 两套服务但 SQL 仍单写 | 收益不成比例 | 中等 | 不推荐作为长期形态 |

## 7. 推荐架构边界

1. SQL 是用户、任务、决策、证据、复盘、结果和审计的唯一事实源。
2. Redis 只负责最新行情缓存、请求合并、限流、并发令牌、任务通知和临时进度。
3. Redis 故障时系统可以变慢或暂停重任务，但不能丢失已确认决策。
4. SQL 故障时禁止返回“已完成”，避免产生无法审计的静默成功。
5. 批量 K 线、tick 和回测数据进入按市场/周期/日期分区的 Parquet Catalog。
6. 任务采用 SQL job/outbox + Redis 通知；Worker 先提交 SQL，再 ACK 消息。
7. 所有 Worker 必须幂等，`session_id` 和阶段执行键受唯一约束保护。
8. Cache 与 Queue 不能共享可淘汰策略；初期若只有一个 Redis，优先 `noeviction`。

## 8. 下一批门禁

在批准技术迁移前还需完成：

1. ⬜ 采集真实一场完整辩论的序列化大小、节点数和耗时分布。
2. 🟡 已证明 SQLite/PostgreSQL 能恢复已提交的 completed session；
   LangGraph 节点级中断续跑仍待实现。
3. 模拟 1/3/5 场并发辩论并测量 LLM 并发、费用和失败传播。
4. 模拟 20/50/100 个并发行情请求并验证 single-flight。
5. 模拟 Redis 关闭、SQL 关闭、磁盘满和损坏记录。
6. 验证备份能在另一目录恢复并通过一致性校验。
7. 验证双击启动体验是否能可靠管理新增服务。

只有这些门禁通过后，才能给出正式的并发承诺和数据库容量承诺。

### 8.1 Batch B session 恢复证据（2026-07-28）

本轮新增 `DebateSessionRecord` 版本化信封、SQLite WAL 原型和
`scripts/debate_recovery_gate.py`。信封以 `session_id` 为主键，保存状态、
进度、完整 `DebateResult`、schema version 与 SHA-256；终态不可改写，
状态和进度只能单调前进，损坏记录必须显式报错。

同一份基于当前完整 `DebateResult` 契约的五大师代表性快照：

| 后端 | 原始 canonical JSON | 存储占用 | 重启/重开 | 哈希 |
|:--|--:|--:|:--:|:--:|
| SQLite WAL + FULL | 9,778 bytes | 24,576 bytes | ✅ | ✅ |
| PostgreSQL 17 JSONB + 原文 | 9,778 bytes | JSONB 列 1,603 bytes；表含索引 48 KB | ✅ | ✅ |

SQLite 单次写入约 8.11 ms，关闭连接后重新打开读取约 1.95 ms。PostgreSQL
使用无持久卷临时容器，在提交后重启容器并重新查询，原文 SHA-256 一致。

边界：

- 这是完整契约的代表性样本，不是真实 LLM 生产输出；
- 仓库目前没有可复用的真实历史辩论，不能虚构真实容量结论；
- 当前证明的是“已提交 completed session 可恢复”，不是 LangGraph 节点级续跑；
- 原型尚未接管 `backend/routers/debate.py` 的进程内 session 字典。

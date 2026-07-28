# ADR-012：SQL 事实源 + Redis 协调层 + Parquet 行情目录

| 字段 | 值 |
|:--|:--|
| 日期 | 2026-07-28 |
| 状态 | 🟡 提议，待 Batch A 验收 |
| 影响范围 | data / memory / debate / callback / backend / deployment |

## 背景

当前行情使用无容量上限的内存 TTL，Agent 记忆使用 JSON/JSONL，复盘记录每次
覆写单个 JSON，辩论 session 仅存在进程内存。系统没有正式的数据保留期、容量
承诺、 durable queue 或跨前后端强契约。

合成基线表明，JSONL 适合追加但查询随文件线性增长，单 JSON 逐条覆写随记录量
快速退化；SQLite/PostgreSQL 的主键查询和事务写入更适合作为业务事实存储。

## 决策

目标架构采用三层存储：

1. **SQL 事实源**
   - 保存任务、决策、证据、Agent 输出、复盘、实际结果、信任度和审计事件；
   - 以事务、唯一约束、外键、迁移和备份保证完整性；
   - 具体从 SQLite WAL 还是 PostgreSQL 起步，由下一批恢复/部署门禁决定。
2. **Redis 协调层**
   - 保存可重建的行情缓存、请求合并锁、限流、并发令牌、任务通知和临时进度；
   - 不作为任何实盘决策、财务事实或审计记录的唯一副本；
   - Redis 不可用时允许降级或暂停，不能静默丢失事实。
3. **Parquet 行情目录**
   - 保存大批量 K 线、tick、回测和可重复计算的数据；
   - 按市场、品种、周期、日期分区；
   - 不把高容量时序数据强塞进普通业务事务表。

任务一致性采用 SQL job/outbox + Redis 通知：Worker 先提交 SQL，再确认消息；所有
执行以 `session_id + stage` 唯一键实现幂等。

## 明确不做

- 不把 Redis 当作唯一数据库。
- 不在当前 Batch 直接部署 PostgreSQL 或 Redis。
- 不全量保存 Level-2/tick 数据。
- 不在没有真实负载和恢复证据前承诺 QPS、并发场次或保存年限。
- 不让缓存与 durable queue 共享会自动淘汰任务的策略。

## 后果

### 正面

- 重启后可恢复辩论和复盘链；
- 缓存失效不会破坏事实数据；
- 历史行情与业务事务分离，容量可独立扩展；
- 后续可从 SQLite 迁移 PostgreSQL，而不改 Agent 业务接口；
- 为接口版本、数据来源和决策审计提供稳定落点。

### 成本

- 引入 schema migration、备份恢复和服务健康检查；
- PostgreSQL + Redis 会增加双击启动与父母使用场景的部署复杂度；
- SQL 与 Redis 之间必须处理重复消息、缓存失效和短暂不一致；
- Parquet 目录需要分区、校验和版本迁移规范。

## 验收条件

本 ADR 只有在以下证据通过后转为“已采纳”：

1. 真实辩论快照容量基线；
2. session 中断恢复测试；
3. Redis/SQL 故障注入；
4. 行情并发 single-flight 压测；
5. 一键启动与备份恢复演练；
6. 用户确认生命周期默认值。

完整证据见：
[数据生命周期、容量与 Redis + SQL 调研](../02-requirements/STORAGE_LIFECYCLE_RESEARCH.md)。

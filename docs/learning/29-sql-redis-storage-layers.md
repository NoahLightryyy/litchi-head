# 29 SQL 事实源与 Redis 可重建投影

## 一句话

> SQL 回答“什么事实绝不能丢”，Redis 回答“怎样更快地取得或协调这些事实”；
> Redis 缓存可以重建，实盘决策记录不可以。

---

## 为什么需要它？

### 问题场景

如果把一场 Agent 辩论结果只放在 Redis：

```text
辩论完成 → Redis 写 completed → 前端显示成功
                         ↓
                   Redis 重启/淘汰
                         ↓
             决策、证据和置信度无法复盘
```

Redis 很快，但它支持 TTL、内存淘汰和多种持久化权衡。把它当唯一事实源，会让
系统在缓存重启、内存打满或配置错误时丢失实盘审计链。

相反，所有请求都直接打 SQL 或行情数据源，又会产生热点查询、缓存击穿和重任务
排队困难。

### 它的解法

采用三层职责：

```text
SQL       = 任务、决策、证据、复盘、实际结果（唯一事实源）
Redis     = 缓存、限流、锁、通知、临时进度（可重建投影）
Parquet   = 大批量 K 线、tick、回测数据（列式历史目录）
```

写入顺序不能反过来：

```text
Worker 处理任务
  → SQL 事务提交最终结果
  → 更新/失效 Redis 缓存
  → ACK Redis 消息
```

如果 Worker 在 SQL 提交后、ACK 前崩溃，消息可能再次投递，因此 SQL 必须以
`session_id + stage` 唯一约束保证幂等。

---

## 项目里的真实代码

打开 `scripts/storage_baseline.py`：

```python
connection.execute("PRAGMA journal_mode=WAL")
connection.execute(
    """
    CREATE TABLE IF NOT EXISTS decisions (
        session_id TEXT PRIMARY KEY,
        stock_code TEXT NOT NULL,
        decision_date TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        payload_json TEXT NOT NULL
    )
    """
)
```

这里的 `session_id` 主键不只是为了查得快，也是为了阻止同一辩论任务因重试而
生成两份最终事实。

再看三个基准入口：

```python
runners = (
    benchmark_jsonl,
    benchmark_json_object,
    benchmark_sqlite,
)
```

它把当前两种文件模式与候选 SQL 模式放在同一份合成口径下比较。结果显示：

- JSONL 追加快，但查询随文件增长；
- JSON Object 逐条覆写会越来越慢；
- SQL 索引有额外空间成本，却提供事务、幂等和稳定查询。

---

## 和“Redis 也能持久化”有什么不同？

| 对比 | Redis 持久化 | SQL 事实源 |
|:--|:--|:--|
| 主要目标 | 高速访问、协调 | 完整性、关系、审计 |
| 数据淘汰 | 支持 TTL/内存策略 | 由业务生命周期明确删除 |
| 约束 | 依赖应用设计 | 主键、唯一键、外键、事务 |
| 复杂查询 | 有限 | SQL、索引、分区 |
| 本项目定位 | 可重建投影 | 唯一事实源 |

Redis 的 RDB/AOF 可以帮助恢复 Redis 本身，但不会替代业务层的关系约束、迁移、
审计和幂等设计。

---

## 面试会怎么问

> **Q：为什么不把 PostgreSQL 写完后直接更新 Redis？**
>
> A：数据库提交和 Redis 更新不是同一个事务，中间崩溃会产生不一致。可以采用
> cache-aside，让读请求在 miss 时从 SQL 重建；任务通知则采用 transactional
> outbox，由 SQL 事务写 job/outbox，再异步发布到 Redis。Worker 以唯一键幂等，
> 先提交 SQL，最后 ACK。

---

## 自己试试（5 分钟）

1. 运行：

   ```powershell
   python scripts/storage_baseline.py --records 100 --payload-bytes 4096
   ```

2. 再把记录数改成 1000。
3. 对比 JSONL 查询 p95、JSON Object 写入 ops/s 与 SQLite 查询 p95。
4. 思考：如果 Redis 里 `debate:progress:*` 全部消失，SQL 中至少需要哪些字段才能恢复？

---

**上一篇：[结构化多层市场简报](28-structured-market-brief.md)**

**下一篇：待续**

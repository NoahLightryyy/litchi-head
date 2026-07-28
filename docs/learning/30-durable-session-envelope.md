# 30 可恢复 Session 信封

## 一句话

> Session 恢复不是“把一个 dict 写进数据库”，而是用版本、状态机、幂等键和完整性校验保证重启后读到的仍是同一个可信决策。

---

## 为什么需要它？

### 问题场景

当前后端把辩论 session 放在进程内字典：

```python
_debate_sessions: dict[str, dict[str, Any]] = {}
```

服务一重启，status 和 result 都消失。更隐蔽的问题是重复请求和迟到写入：

```text
新请求把 session 更新到 running 60%
旧 Worker 迟到，把它写回 queued 0%
```

即使数据库没有丢数据，业务状态仍然倒退了。

### 它的解法

项目用 `DebateSessionRecord` 作为持久化信封。它不只保存结果，还明确保存：

- `session_id`：数据库唯一键和幂等键；
- `schema_version`：未来迁移时知道如何解释旧数据；
- `status + progress`：只允许单调状态转换；
- `DebateResult`：完整 Pydantic 业务契约；
- `error`：失败必须对用户可见；
- SHA-256：发现意外损坏，不能把损坏当成“未找到”。

---

## 项目里的真实代码

打开 `src/debate/session_store.py`：

```python
class DebateSessionRecord(BaseModel):
    session_id: str = Field(min_length=1)
    stock_code: str = Field(min_length=1)
    status: SessionStatus
    progress: int = Field(ge=0, le=100)
    result: DebateResult | None = None
    error: str | None = None
    schema_version: int = Field(default=1, ge=1)
```

completed session 必须有完整结果：

```python
if self.status == "completed":
    if self.result is None or self.progress != 100:
        raise ValueError("completed session requires result and progress=100")
```

存储层同时保护状态转换：

```python
_ALLOWED_TRANSITIONS = {
    "queued": frozenset({"queued", "running", "failed"}),
    "running": frozenset({"running", "completed", "failed"}),
}
```

因此 `running → queued`、进度倒退、终态改写都会显式失败。

SQLite 原型使用：

```python
connection.execute("PRAGMA journal_mode=WAL")
connection.execute("PRAGMA synchronous=FULL")
connection.execute("BEGIN IMMEDIATE")
```

WAL 改善读写并发；`FULL` 优先保证断电后的提交可靠性；`BEGIN IMMEDIATE`
让写竞争尽早暴露，而不是执行到一半才失败。

---

## “重启恢复”和“节点续跑”有什么不同？

| 能力 | 本轮已证明 | 仍待实现 |
|:-----|:----------:|:---------:|
| completed 结果重启后可读 | ✅ | |
| 原始 JSON 哈希一致 | ✅ | |
| 终态幂等、不可改写 | ✅ | |
| running 状态不倒退 | ✅ | |
| 从 LangGraph 中断节点继续 | | ⬜ |
| durable queue 重领任务 | | ⬜ |
| Redis/SQL 故障切换 | | ⬜ |

不要把“数据库里能读回结果”写成“整个 Agent 工作流可以断点续跑”。后者还需要
LangGraph checkpointer、节点幂等和任务租约。

---

## 面试会怎么问

> **Q：为什么有数据库主键还不够，仍要业务状态机？**
>
> A：主键只能防止同一 ID 出现两行，不能防止迟到写入覆盖新状态。状态转换和
> progress 必须在事务中检查，终态需要不可变，才能保证重试与并发下的业务幂等。

> **Q：为什么同时保存 JSON 原文和 JSONB？**
>
> A：JSONB 适合索引和查询，但会规范化键顺序和空白；原文适合做稳定摘要与审计。
> PostgreSQL 可以同时保留 canonical 原文和 JSONB 投影，两者职责不同。

---

## 自己试试（5 分钟）

1. 准备一份 `DebateResult` JSON 导出。
2. 运行：

   ```powershell
   python scripts/debate_recovery_gate.py result.json `
     --database data/benchmarks/debate-recovery.db
   ```

3. 查看 canonical bytes、写入耗时、重开读取和哈希结果。
4. 把 JSON 中必需字段删掉再运行，确认工具显式失败。
5. 思考：如果要从 `master_round` 继续，除 session 信封外还要保存哪些节点状态？

---

**上一篇：[SQL 事实源与 Redis 可重建投影](29-sql-redis-storage-layers.md)**

**下一篇：待续**

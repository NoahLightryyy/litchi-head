# 31 LangGraph 持久检查点：让节点完成后可以断电续跑

## 一句话

> Checkpoint 把每个 LangGraph 超级步的状态和下一步位置按 `thread_id` 落盘，重启后传入空输入即可从未完成节点继续，而不是把整场昂贵辩论重跑一遍。

---

## 为什么需要它？

### 问题场景

一场真实五分析师、五大师、五互评辩论实测需要约 176 秒和 16 次 LLM 调用。
如果进程在最后一个节点前退出，只保存最终 `DebateResult` 无法恢复“正在运行”
的任务；重新发起会重复数据采集、LLM 费用和可能有副作用的写入。

```text
collect ✅ → master ✅ → review ✅ → aggregate 执行前进程退出
没有 checkpoint：只能从 collect 重跑
有 checkpoint：从 aggregate 前的已提交状态继续
```

### 它的解法

LangGraph 编译时注入 checkpointer，并为每次运行提供稳定的 `thread_id`。每个图
步骤完成后，框架保存状态、下一节点和相关元数据。恢复时重新构建同一拓扑的图，
连接持久数据库，再调用 `invoke(None, config)`。

`None` 很关键：它表示继续已有线程，而不是提交一份新输入重新开跑。

---

## 项目里的真实代码

打开 `scripts/langgraph_checkpoint_gate.py`：

```python
config = {"configurable": {"thread_id": thread_id}}

interrupted_graph = builder.compile(
    checkpointer=SqliteSaver(first_connection),
    interrupt_after=["collect"],
)
interrupted_graph.invoke({"completed_nodes": []}, config)
first_connection.close()

resumed_graph = builder.compile(
    checkpointer=SqliteSaver(second_connection),
)
resumed = resumed_graph.invoke(None, config)
```

门禁故意在 `collect` 后停下并关闭第一个连接，再用第二个连接恢复。最终验证：

- 中断状态：`["collect"]`
- 恢复状态：`["collect", "analyze"]`
- `collect` 执行一次
- `analyze` 执行一次

这比“同一进程里暂停再继续”更接近真正的后端重启。

---

## 和最终结果存储有什么不同？

| 对比 | Durable session 信封 | LangGraph checkpoint |
|:-----|:---------------------|:---------------------|
| 保存对象 | 业务状态、最终结果、错误、审计字段 | 图状态、节点位置和恢复元数据 |
| 主要用途 | 查询任务、展示结果、长期审计 | 运行中断后从下一节点继续 |
| 生命周期 | 受业务保留策略管理 | 通常更短，可在任务终结后压缩或清理 |
| 能否互相替代 | 不能 | 不能 |

生产方案通常两者都要：session 是业务事实，checkpoint 是执行恢复机制。

---

## 实盘系统还要补什么？

这个原型只证明框架语义，正式接入前仍要处理：

1. 正式异步图应使用 `AsyncSqliteSaver` 或生产 PostgreSQL checkpointer；
2. 发通知、扣额度、写外部系统等副作用必须有幂等键；
3. 图代码或状态 schema 升级后，要定义旧 checkpoint 的兼容和迁移策略；
4. 必须给任务配置全局并发、超时、取消、重试和 checkpoint 清理；
5. `thread_id` 必须由服务端生成并授权，不能让用户读取他人的线程。

---

## 面试会怎么问

> **Q：有数据库保存最终结果，为什么还需要 LangGraph checkpointer？**
>
> A：最终结果只能恢复已经结束的业务事实，不能表示运行中图执行到了哪个节点。
> Checkpointer 保存每个超级步的状态和执行位置，使进程故障后不重复已完成的昂贵
> 节点。生产上二者职责分离：业务表负责事实和审计，checkpoint 负责执行恢复。

---

## 自己试试（5 分钟）

1. 运行 `python -m pytest tests/test_scripts/test_langgraph_checkpoint_gate.py -q`。
2. 打开测试，把 `thread-a` 和 `thread-b` 改成同一个 `thread_id`，观察为什么第二次
   不再代表独立任务。
3. 在 `collect` 中加入一个计数文件或唯一键，思考重试时怎样防止副作用重复。
4. 思考题：正式辩论状态字段变化后，旧 checkpoint 应拒绝、迁移，还是从头重跑？

---

**上一篇：[可恢复 Session 信封](30-durable-session-envelope.md)**

**下一篇：[多源证据契约](32-multi-source-evidence-contract.md)**

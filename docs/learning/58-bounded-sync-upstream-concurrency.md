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

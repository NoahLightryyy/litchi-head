# 56｜线程安全不是“用了 GIL 就行”

## 一句话

> GIL 只能保证 Python 字节码不会真正并行执行，不能保证“总数 + 分类计数 + 延迟”这一组
> 复合更新对并发快照是原子的。

---

## 为什么需要它？

### 问题场景

首页指数会在线程池中同时请求多个来源。一次 `record_call()` 要依次更新总调用数、成功/
空/失败分类、最后成功时间和延迟窗口。旧实现没有锁，`snapshot()` 可能在总数已经加一、
分类计数尚未加一时进入，于是短暂得到：

```text
total_calls = 11
success + empty + failures = 10
```

这不是“偶尔显示慢一点”，而是监控自己给出了内部矛盾的证据。GIL 不会把多个容器上的
多步操作自动合并成事务。

### 它的解法

项目让记录和快照共享同一把 `RLock`。写入期间快照等待；快照构造期间写入也等待，因此
任何对外响应只能看到一次调用之前或之后的完整状态。

选择可重入锁不是为了递归，而是允许未来在持锁方法内安全调用同一对象的内部辅助方法，
避免锁协议被重构意外破坏。

---

## 项目里的真实代码

打开 `src/data/collector.py`：

```python
def record_call(...):
    with self._lock:
        self._total[endpoint] += 1
        # 同一临界区内更新分类、时间和延迟

def snapshot(self) -> dict[str, object]:
    with self._lock:
        return self._snapshot_locked()
```

测试 `test_snapshot_waits_for_an_in_progress_record` 会故意把记录暂停在总数更新之后，证明
快照必须等待整次记录完成。另一个压力测试并发写入成功、空和失败各 2000 次，同时持续
读取快照，最终核对 6000 次调用的分类守恒。

---

## 和“每个计数器单独加锁”有什么不同？

| 对比 | 每字段独立保护 | 本方案共享临界区 |
|:-----|:---------------|:----------------|
| 单个整数是否安全 | 是 | 是 |
| 多字段是否互相一致 | 不保证 | 保证 |
| 快照能否读到半次记录 | 可能 | 不能 |
| 对外诊断是否可解释 | 容易矛盾 | 同一时点一致 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_data/test_data_collector.py::TestHealthStats -q`；
2. 打开 `test_snapshot_waits_for_an_in_progress_record`，看它怎样用事件暂停一次写入；
3. 临时移除 `snapshot()` 的锁，再运行该测试，观察 RED；
4. 思考：如果只锁 `_total`，为什么其他分类和延迟仍可能与总数不一致？

---

**上一篇：[55｜多源汇总不是把两个数字取平均](55-multi-source-index-reconciliation.md)**

**下一篇：** 待续

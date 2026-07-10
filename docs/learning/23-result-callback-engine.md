# 23 结果回调引擎 — 让结果自动触发系统学习

## 一句话

> 结果回调引擎就是系统的“反射弧”：市场结果、用户操作、回测完成后，不靠人手调用各模块，而是统一派发事件，让对应策略自动更新。

---

## 为什么需要它？

### 问题场景

没有统一回调引擎时，每个模块都要自己等结果、自己判断何时更新。今天 TrustTracker 要记录胜率，明天风控要调仓位，后天用户行为要写入记忆，最后会变成一堆散落的 `if result_arrived: do_something()`。

实盘系统里这很危险：AI 连续判断错某类股票，如果没有统一事件把“错了”传给信任度、置信度和风控模块，系统就会重复同样的错误。

### 它的解法

RC-001 新增 `ResultCallbackEngine`：业务侧只需要 dispatch 一个事件，注册过的回调会按优先级执行。单个回调失败不会拖垮整条主流程，冷却和自动禁用可以防止坏回调反复制造噪音。

后续 RC-002/003/004 只需要注册业务回调，例如“实际盈亏到了 → TrustTracker 记录结果”“用户点击买入 → 用户行为写入 MemoryStore”“回测完成 → 风控覆盖值更新”。

---

## 项目里的真实代码

打开 `src/callback/engine.py`：

```python
async def dispatch(
    self,
    event_type: CallbackEventType | CallbackEvent,
    context: dict[str, Any] | None = None,
    source: str = "",
) -> list[CallbackRecord]:
    event = self._build_event(event_type, context=context, source=source)
    await self._load_persisted_configs()

    records: list[CallbackRecord] = []
    for entry in self.registry.get_for_event(event.event_type):
        if self._is_in_cooldown(entry.config, event.timestamp):
            record = self._cooldown_record(entry.name, event)
        else:
            record = await self._run_callback(entry.name, entry.fn, entry.config, event)
        records.append(record)
        await self.storage.save_record(record)
        await self.storage.save_config(entry.config)

    await self.storage.flush_records()
    return records
```

这段代码有三个关键点：

1. 先把 `event_type + context` 统一成 `CallbackEvent`，每个事件带 `event_id`。
2. 用注册表筛出监听该事件的回调，按优先级执行。
3. 不管执行、冷却还是失败，都写 `CallbackRecord`，方便之后审计“系统到底学没学”。

---

## 和直接函数调用有什么不同？

| 对比 | 直接调用 | ResultCallbackEngine |
|:-----|:---------|:---------------------|
| 调用关系 | 业务代码知道每个下游模块 | 业务代码只 dispatch 事件 |
| 失败影响 | 一个异常可能打断主流程 | 单个回调失败只生成失败记录 |
| 审计 | 需要每处自己写日志 | 统一 `CallbackRecord` |
| 扩展 | 新模块要改调用方 | 新模块注册回调即可 |

---

## 面试会怎么问

> **Q: 为什么不在交易完成后直接调用 TrustTracker？**
>
> A: 因为结果不只影响 TrustTracker。它还可能影响用户画像、风控参数、置信度校准和策略路由。事件分发能把“结果到了”这件事和“哪些模块要响应”解耦，后续新增回调不需要改交易主流程。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_callback/test_engine.py`
2. 找到 `test_callback_failure_is_recorded_and_does_not_block_later_callbacks`
3. 把失败回调和成功回调的注册顺序换一下，思考：为什么不管谁先失败，另一个都应该有机会执行？
4. 再看 `test_callback_auto_disables_after_error_threshold`：这就是实盘里防止坏回调一直报错刷屏的保险丝。

---

**上一篇：[辩论偏斜度计算 — BiasReport](22-debate-bias-report.md)** ← 链接

**下一篇：待补** ← 链接

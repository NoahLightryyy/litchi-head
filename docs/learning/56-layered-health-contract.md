# 56 健康检查分层：连得上不等于有数据

## 一句话

> 进程连通、数据源请求成功和业务数据可用是三个不同事实，不能用一个绿色状态代替。

## 为什么需要它？

前端曾请求不存在的 `/api/health/diagnose`：基础健康接口成功，详细诊断却 404，页面因此
长期显示“诊断信息暂不可用”。即使改用真实接口，后端也必须把空业务结果与成功分开统计。

解法是分层：先用 `/api/health` 判断服务是否在线，再校验 `/api/health/data-source` 的真实
响应契约并转换为 UI 状态。解析失败时降级显示，绝不猜测。

## 项目里的真实代码

打开 `src/data/collector.py`：`begin_batch()` 在上游请求前分配序号，
`record_batch()` 持锁一次性记录三指数结果，再按失败、空数据、成功的优先级归并当前健康。
晚到旧批仍计入历史，但不能覆盖更新批的当前状态；`snapshot()` 持同一锁读取一致快照。

前端消费目标（`frontend/lib/backend-health.ts` 待集成任务落实）：

```typescript
const degraded = value.status !== "ok" || summary.failing_endpoints > 0
  || summary.empty_endpoints > 0;
// 单项只读 current_status；禁止用 failures / total_failures 的历史值判断当前故障。
```

失败后恢复不能删除历史，也不能让历史累计值永久维持红灯。一个来源承担多个指数时，
后两个成功更不能抹掉第一个失败。测试见 `tests/test_data/test_health_recovery.py` 和
`tests/test_data/test_index_quote_runtime.py`。当前状态是最后一次完成的观察，不是实时可达保证。

## 自己试试（5 分钟）

1. 访问 `/api/health`，确认它只证明后端进程在线。
2. 访问 `/api/health/data-source`，把 `failing_endpoints` 临时改为 1 写进单元测试。
3. 运行 `pytest tests/test_data/test_health_recovery.py -q`，观察失败后恢复仍保留 failures。
4. 思考题：HTTP 200 但 `data: []` 应该算传输成功还是业务可用？

---

**上一篇：[55｜多源汇总不是把两个数字取平均](55-multi-source-index-reconciliation.md)**

**下一篇：[57｜同步上游并发：协程取消不等于线程停止](57-bounded-sync-upstream-concurrency.md)**

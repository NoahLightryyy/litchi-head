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

**下一篇：[57｜可访问的数据视图](57-accessible-stateful-data-view.md)**

## 前端恢复消费（2026-09-04）

`frontend/lib/backend-health.ts` 严格消费 current_status；历史 failures 保留也不会让 healthy 继续告警。未知状态返回诊断不可用。消费者测试覆盖恢复、空结果和混合来源。指数卡消费 display_source，冲突提示与请求失败分开，不遮挡有效单源数据。



## 延伸：快照缓存不等于实时数据

候选 `src/data/providers/eastmoney_boards.py` 将 `as_of`（上游数据时间）、
`fetched_at`（完整采集时间）、`cached`（本次是否复用本地缓存）分别保存。
可能延迟的东方财富快照始终标记 `possibly_delayed=true`；缓存命中更快不代表报价更新。
只有页数/总量/唯一代码检查通过的完整数据才进入30秒缓存，过期后网络失败不返回旧缓存。

自己试试：运行 `pytest tests/test_data/test_eastmoney_boards.py -q`，对照缓存边界测试的
29.9秒和30秒，观察缓存命中与失败传播的差别。该快照已于2026-09-05获准接入首页列表；接口始终同时给出上游时间和可能延迟限制。

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

前端来源故障判断（`frontend/lib/backend-health.ts`；业务可用性归类见下方备用源补充）：

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

2026-09-06 的详情修复补充了另一个边界：只有行业与概念目录都成功且均无目标代码，
才能回答404“未找到”；任一目录失败时证据不完整，必须返回503。详情成分股同样只有
完整分页才发布，未知价格不补0，避免把“没拿到”伪装成真实零值。

## 备用源失败与业务可用（2026-10-22）

并联备用源不是必须全部健康的依赖。`frontend/lib/backend-health.ts` 将有完整健康指数源的纯指数故障归为 healthy_with_warnings；check 内保留失败事实，UI 折叠诊断。`canCollapseIndexDiagnostics` 另按本次响应检查三指数完整性、缓存、冲突和刷新状态。自己试试：运行 frontend 的 backend-health 与 market-notice 测试，将最后一个 healthy 改为 failed，观察恢复告警。


## 搜索目录与混合故障恢复（2026-10-27）

“有一个可用就先用”需要在数据管道实现，而不只是把红字藏起来。

- `src/data/providers/stock_catalog.py` 把原 AKShare 聚合函数内部已有的沪市主板、深市、科创板、北交所请求独立执行。一个交易所失败时，其他交易所的真实名称/代码继续可搜；完整性随 `StockCatalogSnapshot` 传到消费者。
- `src/data/collector.py::get_stock_catalog()` 只把完整成功目录放入一小时缓存。空结果/部分结果使用独立15秒退避缓存，避免失败被长期固化，也避免连点搜索请求轰炸。旧空成功缓存直接失效。
- 每个交易所最多一个在途任务、总共最多四个；等待预算8秒，超时先返回已取得的部分。等待结束不等于强杀网络线程，晚到结果下一次合并；不可取消的SDK调用仍需运输层超时治理。
- `frontend/lib/backend-health.ts::partitionDiagnostics()` 在“股票目录失败 + 两个指数源失败 + 一个完整指数源成功”时，只计一个未恢复业务问题，两个备用源故障仍在折叠诊断里。价格冲突不能当作可忽略的备用故障。
- `frontend/components/shared/stock-discovery.tsx` 的搜索按钮不只记历史：相同关键词会真正 `refetch()`。新关键词交给 debounce，正在请求时不重复发送。部分目录无匹配只说明这批资料未找到，不证明股票不存在。

**自己试试（5分钟）**：运行 `pytest tests/test_data/test_stock_catalog.py -q`，查看慢沪市与正常深市组合；再运行 `cd frontend && npm test` 的 discovery-retry/backend-status 用例，核对同词重试和混合异常数量。实网恢复例为京泉华002885，测试不依赖该股票的行情涨跌。

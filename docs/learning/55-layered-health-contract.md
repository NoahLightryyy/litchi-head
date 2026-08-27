# 55 健康检查分层：连得上不等于有数据

## 一句话

> 进程连通、数据源请求成功和业务数据可用是三个不同事实，不能用一个绿色状态代替。

## 为什么需要它？

前端曾请求不存在的 `/api/health/diagnose`：基础健康接口成功，详细诊断却 404，页面因此
长期显示“诊断信息暂不可用”。即使改用真实接口，后端也必须把空业务结果与成功分开统计。

解法是分层：先用 `/api/health` 判断服务是否在线，再校验 `/api/health/data-source` 的真实
响应契约并转换为 UI 状态。解析失败时降级显示，绝不猜测。

## 项目里的真实代码

打开 `frontend/lib/backend-health.ts`：

```typescript
const degraded =
  value.status !== "ok" ||
  summary.total_failures > 0 ||
  summary.failing_endpoints > 0;
```

`normalizeDataSourceDiagnostics()` 还会拒绝缺少汇总字段、失败计数类型错误等未知响应，避免
后端契约漂移后前端继续显示绿色。

## 自己试试（5 分钟）

1. 访问 `/api/health`，确认它只证明后端进程在线。
2. 访问 `/api/health/data-source`，把 `failing_endpoints` 临时改为 1 写进单元测试。
3. 运行 `pnpm --dir frontend test`，观察状态转换为 `degraded`。
4. 思考题：HTTP 200 但 `data: []` 应该算传输成功还是业务可用？

---

**上一篇：[HTTP 200 不等于数据成功](54-truthful-market-api-status.md)**

# 54｜HTTP 200 不等于数据成功

## 一句话

> API 调用没有抛异常，只能证明程序跑完了；业务数据是否完整、为空、陈旧或失败，必须用
> 稳定状态和错误信封单独表达。

---

## 为什么需要它？

### 问题场景

指数来源找不到目标时构造 `0.00`，新闻字段漂移时保留空标题，或者上游返回空列表仍被
健康统计记为成功，都会制造“页面有响应，所以数据正常”的错觉。对实盘辅助系统而言，
假成功比明显报错更危险：用户可能把缺失事实当成真实市场状态。

### 它的解法

首页市场接口把业务结果分为五态：完整数据为 `success`；仍可展示但有缺口为 `partial`；
上游正常却无可用记录为 `empty`；来源失败但有过期缓存为 `stale`；无可用缓存或字段结构
损坏为 `failed`。前四态使用 HTTP 200 并携带诊断，`failed` 使用 HTTP 503。状态描述
“结果能否消费”，HTTP 描述“请求是否需要失败关闭”，两者不能混为一个布尔值。

---

## 项目里的真实代码

打开 `backend/routers/market.py`：

```python
MarketDataStatus = Literal["success", "partial", "empty", "stale", "failed"]

class MarketMeta(BaseModel):
    status: MarketDataStatus
    cached: bool
    missing_codes: list[str] = []
    failed_sources: list[str] = []
    limitations: list[MarketLimitation] = []
```

`src/data/index_quote_runtime.py` 并发汇总两路指数专用接口；身份、价格或时间冲突时拒绝
对应条目，只允许单源明确降级，且只有双源共识结果才能进入短时缓存。路由把这些事实
转换为 `partial/stale/failed`，不会造一个价格为零的指数。

打开 `src/data/collector.py`：

```python
if error:
    self._failures[endpoint] += 1
elif empty:
    self._empty[endpoint] += 1
else:
    self._success[endpoint] += 1
```

因此空业务结果会让 `/api/health/data-source` 显示 `degraded`，不会污染成功率。

打开 `frontend/lib/market-contract.ts`：前端不会因为 TypeScript 类型声明就盲信网络响应，
而是在运行时检查状态、缓存标记、缺口说明和实际数据是否一致。例如指数价格必须大于零，
必须携带有时区的数据时间与来源数量；`empty` 必须真的没有可消费数据；`stale` 必须明确
来自缓存；板块资金流未知时必须为 `null` 且不能声称已按资金流排序。校验失败进入错误态，
不会把未知或旧版信封渲染成行情。

诚实失败也包括“不要让骨架屏无限等”。首页板块请求在 18 秒后进入明确的可重试失败态，
不自动再发一次同样的长请求；一旦取得真实列表，首屏只展示前 10 条，其余按需展开。
这是展示层的信息密度控制，不会拿静态榜单或旧顺序冒充本次请求结果。

---

## 和“所有空数据都报错”有什么不同？

| 场景 | 全部报错 | 五态契约 |
|:-----|:---------|:---------|
| 来源正常但休市/无记录 | 误报系统故障 | `empty`，页面显示真实空态 |
| 一个板块源失败、另一个可用 | 丢弃可用数据 | `partial`，披露失败来源 |
| 来源失败但有旧缓存 | 页面完全不可用 | `stale`，明确标注过期 |
| 字段损坏且无缓存 | 可能继续返回空字段 | 503 `failed`，失败关闭 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_backend/test_market.py -q`；
2. 找到指数全缺失、板块单源超时、热点新闻字段损坏和陈旧缓存四组测试；
3. 临时把 `_pick_index()` 改回零值占位，观察 Pydantic 的 `price > 0` 和契约测试失败；
4. 运行健康测试，确认一次空结果不会增加 `success`。
5. 运行 `pnpm --dir frontend test`，观察前端消费者拒绝零值指数和矛盾信封。

---

**上一篇：[52｜证据不完整时怎样继续推理而不伪装完整](52-evidence-limited-reasoning.md)**

**下一篇：[55｜多源汇总不是把两个数字取平均](55-multi-source-index-reconciliation.md)**

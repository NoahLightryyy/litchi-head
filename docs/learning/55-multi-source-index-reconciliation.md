# 55｜多源汇总不是把两个数字取平均

## 一句话

> 多源行情的价值不是“多拿几份数据”，而是保留来源身份、验证时间和价格是否一致，并在
> 单源、冲突和全失败时给下游不同的可消费结论。

---

## 为什么需要它？

### 问题场景

股票代码 `000001` 是平安银行，但指数代码 `000001` 是上证指数；如果沿用股票市场路由，
新浪会请求 `sz000001`，东方财富会请求 `0.000001`，两路都可能返回“看似合法但身份错误”
的数据。即使代码正确，把两家价格直接平均也会掩盖时间错位、字段漂移或真实冲突。

### 它的解法

项目为三大指数维护独立映射：上证 `1.000001/sh000001`，深证
`0.399001/sz399001`，创业板 `0.399006/sz399006`。六个请求并发执行，每个结果保留
`source_id/upstream_id/status/latency/as_of/error_code`。

两源价格差不超过 0.01 点且时间差不超过 3 秒才形成完整共识；单源可用时保留真实数据并
标注 `INDEX_SINGLE_SOURCE`；2026-09-04 起首页冲突也展示一个有效来源并旁注冲突，
不声称验证通过；双源失败只能使用 30 秒内曾通过双源校验的
缓存。缓存不是第三个来源，也不能覆盖当前冲突。

---

## 项目里的真实代码

打开 `src/data/index_quote_runtime.py`：

```python
if max(prices) - min(prices) > INDEX_PRICE_TOLERANCE + 1e-9:
    return IndexQuoteService._display_quote(successful, name), [IndexLimitation(
        code="INDEX_PRICE_CONFLICT",
        index_code=code,
        message=f"{name} 双源价格差超过 0.01 点",
    )], True
```

这里选择时间最新的有效单源（同时间按 upstream_id 字典序最大值确定），并返回
`source_count=1` 与 `display_source`，不会平均、不会写入双源缓存。即使三项都存在
价时冲突，仍以 HTTP 200 `partial` 展示并旁注；正式 AI 决策门禁不受首页显示策略影响。

打开 `src/data/collector.py`：健康快照只暴露固定安全文案和稳定错误码。原始 ProxyError、
URL 与查询参数由调用点日志保存，不进入前端横幅。

---

## 和顺序 fallback 有什么不同？

| 对比 | 主备 fallback | 双源汇总 |
|:-----|:--------------|:---------|
| 正常时调用 | 只调主源 | 两源并发 |
| 能否发现主源错误值 | 不能 | 可以比较价时与身份 |
| 单源失败 | 切备用但不披露完整性 | 返回 `partial` 和逐源诊断 |
| 两源冲突 | 通常选主源 | 有效单源展示，旁注冲突 |
| 健康观察 | 一个聚合状态 | 按 upstream 独立统计 |

---

## 自己试试（5 分钟）

1. 运行 `pytest tests/test_data/test_index_quote_runtime.py -q`；
2. 找到 `test_one_index_conflict_is_displayed_with_explicit_limitation`；
3. 把新浪价格从 `3943.55` 改为 `3943.54`，观察它从冲突变成完整共识；
4. 再把两源都改成失败，确认仅 30 秒内的已核验缓存能返回 `stale`。

---

**上一篇：[54｜HTTP 200 不等于数据成功](54-truthful-market-api-status.md)**

**下一篇：[56｜健康检查分层：连得上不等于有数据](56-layered-health-contract.md)**

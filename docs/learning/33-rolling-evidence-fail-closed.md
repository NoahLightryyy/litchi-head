# 33 滚动证据与 Fail-Closed 门禁

## 一句话

> 短历史信息流要先持续落盘形成可证明的时间覆盖，证据不完整时必须在昂贵的 AI
> 链路开始前拒绝执行。

---

## 为什么需要它？

### 问题场景

新浪公开快讯只能翻到有限历史。一次请求成功、甚至返回零条，都不能证明最近三天
确实没有相关新闻；如果仍让 LLM 继续，系统会产出外观完整但输入残缺的结论。

### 它的解法

应用每 5 分钟保存一次元数据，并在 SQLite 中记录连续采集起点和最后成功时间。
间隔超过 10 分钟就重置覆盖；只有连续覆盖完整 3 天，新浪才算成功上游。

正式辩论的 `collect_data` 节点检查统一 `EvidenceEnvelope`。不完整时走 `END`，
随后抛出领域错误，由 API 映射为 503，因此分析师和大师节点都不会运行。

---

## 项目里的真实代码

打开 `src/data/news_store.py`：

```python
continuous_since = oldest_item
if existing is not None:
    previous_success = datetime.fromisoformat(str(existing["last_success_at"]))
    if collected_utc - previous_success <= self._max_collection_gap:
        continuous_since = datetime.fromisoformat(
            str(existing["continuous_since"])
        )
```

打开 `src/debate/orchestrator.py`：

```python
graph.add_conditional_edges(
    "collect_data",
    _route_after_collection,
    {"continue": "analyst_round", "stop": END},
)
```

关键点不是“有缓存”，而是缓存能够证明时间窗连续；门禁发生在任何 LLM 节点之前。
同样，分页达到上限不等于读完：未证明信息流耗尽时，本轮不能推进覆盖水位。

---

## 和普通 TTL 缓存有什么不同？

| 对比 | TTL 缓存 | 滚动证据存储 |
|:-----|:---------|:-------------|
| 目标 | 减少重复请求 | 证明历史窗口被连续观察 |
| 重启 | 常可丢失 | SQLite WAL 持久恢复 |
| 断档 | 通常不关心 | 超阈值立即重置覆盖 |
| 空结果 | 可能直接返回 | 只有完整覆盖后才是可信空 |

---

## 面试会怎么问

> **Q: 为什么上游 HTTP 200 不能直接视为数据完整？**
>
> A: HTTP 200 只证明当前请求成功，不证明上游开放历史覆盖了业务时间窗。需要同时
> 记录来源身份、查询范围、连续覆盖和新鲜度，才能区分可信空结果与历史不足。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_data/test_news_rolling_store.py`
2. 将允许采集间隔从 10 分钟改为 2 分钟，运行该文件
3. 思考：应用停机 15 分钟后，为什么不能保留原来的三天覆盖起点？
4. 再思考：如果 5 分钟内新增新闻超过分页上限，为什么 HTTP 全部成功仍要失败？

---

**上一篇：[多源证据契约：两个接口不一定是两个来源](32-multi-source-evidence-contract.md)**

# 32 多源证据契约：两个接口不一定是两个来源

## 一句话

> 多源可靠性的计数单位是“真实上游”，不是 Python 库、函数或适配器；采集失败也绝不能伪装成成功的空结果。

---

## 为什么需要它？

### 问题场景

项目可以同时调用 AKShare 的东方财富函数和自己编写的东方财富 HTTP 适配器。
从代码上看是两个接口，但它们依赖同一个网站：

```text
akshare-eastmoney ─┐
                   ├─→ 东方财富不可用时一起失败
direct-eastmoney ──┘
```

如果按适配器数量计算，系统会错误地认为已经获得“两源交叉验证”。另一个危险是旧
Provider 用 `[]` 同时表示“真的没有新闻”和“网络请求失败”，业务层无法知道证据
链是否断裂。

### 它的解法

每个适配器声明两个身份：

- `source_id`：项目里的接入实现，例如 `akshare-eastmoney`；
- `upstream_id`：真实提供数据的机构，例如 `eastmoney`。

完整性评估只去重统计 `upstream_id`。同时，一次查询必须返回明确状态：
有数据、成功空、失败、不支持、过期或冲突。

---

## 项目里的真实代码

打开 `src/data/evidence.py`：

```python
class SourceDescriptor(BaseModel):
    source_id: str
    upstream_id: str
    display_name: str
    capabilities: set[EvidenceCapability]
    discovery_only: bool = False


class SourceStatus(str, Enum):
    SUCCESS_DATA = "success_data"
    SUCCESS_EMPTY = "success_empty"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    CONFLICTED = "conflicted"
```

评估器只把 `SUCCESS_DATA` 和 `SUCCESS_EMPTY` 算作成功查询，再用集合对真实上游
去重：

```python
if result.status in successful_statuses:
    successful_upstream_ids.add(result.upstream_id)
```

`SUCCESS_EMPTY` 的含义非常严格：上游确实响应并明确返回零条。连接超时、解析失败
或权限不足必须是 `FAILED`，并携带用户和日志都能看到的错误信息。

---

## 和传统 Fallback 有什么不同？

| 对比 | 传统 Fallback | 多源证据契约 |
|:-----|:--------------|:-------------|
| 目标 | 主源失败后尽量返回数据 | 判断整类证据是否达到业务门槛 |
| 成功标准 | 某个接口返回值 | 足够数量的独立真实上游成功 |
| 空列表 | 常与失败混在一起 | 只允许表示明确的成功空结果 |
| 发现型 RSS | 可能被当成普通来源 | `discovery_only`，不计入门槛 |
| 最终行为 | 容易静默降级 | 不完整时失败关闭 |

单个来源可以被替换，但整个证据类别不能因此悄悄缺失。

---

## 面试会怎么问

> **Q：系统接了三个新闻 API，为什么还不能说有三源交叉验证？**
>
> A：API 数量不等于上游独立性。三个 API 可能都转发同一家媒体或同一聚合商，
> 具有共同故障和共同偏差。应记录真实上游身份，按独立上游去重计数，并显式区分
> 成功空结果、采集失败和过期数据。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_data/test_evidence_sources.py`。
2. 找到两个 `upstream_id="eastmoney"` 的来源，运行对应测试。
3. 把第二个上游改成 `sina`，观察完整性判断为什么改变。
4. 思考题：如果一个聚合接口同时返回十家媒体，独立性应该按聚合商还是原始媒体算？

---

**上一篇：[LangGraph 持久检查点](31-langgraph-durable-checkpoint.md)**

**下一篇：待续**

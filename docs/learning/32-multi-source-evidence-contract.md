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

### 同一上游的两个真实适配器

打开 `src/data/providers/cninfo.py`：

```python
descriptor = SourceDescriptor(
    source_id="cninfo-direct",
    upstream_id="cninfo",
    display_name="巨潮资讯公告（直连）",
    capabilities={EvidenceCapability.ANNOUNCEMENT},
)
```

项目同时保留 `cninfo-direct` 和 `akshare-cninfo`。两个 `source_id` 表示两种接入
实现，但公告事实都来自巨潮资讯，所以 `upstream_id` 都是 `cninfo`，交叉验证只能
算一个来源。

直连适配器直接读取公开响应中的 `totalAnnouncement`：

- `totalAnnouncement > 0` 且完整取回同数量公告 → `SUCCESS_DATA`；
- `totalAnnouncement == 0` 且公告列表为空 → `SUCCESS_EMPTY`；
- 数量矛盾、字段损坏或网络失败 → `FAILED`。

2026-07-29 的真实门禁中，平安银行长窗口取得 3 条公告，短窗口明确读取到 0 条，
解决了 AKShare 在空表上选列抛错的问题。

### 汇总层如何传给业务节点

适配器不会直接把各自格式传给辩论引擎。`DataEvidenceService` 会把多个通道统一
汇总：

```text
CNINFO / 东方财富 / 新浪等通道
        ↓ 各自标准化为 SourceResult
DataEvidenceService
        ↓ 按 capability 分组 + upstream_id 去重 + EvidencePolicy 评估
统一证据信封（条目 + 查询范围 + 通道状态 + 完整性结果）
        ↓
辩论 / 后端 / 其他业务节点
```

这样业务节点只认识统一证据信封，不认识具体网站或 Python 库。更换通道只影响
适配器和配置，不会把来源细节扩散到业务代码。

项目中的信封定义在 `src/data/evidence.py`：

```python
class EvidenceEnvelope(BaseModel):
    request: EvidenceRequest
    policy: EvidencePolicy
    source_results: list[SourceResult[Any]]
    items: list[Any]
    assessment: EvidenceAssessment
    complete: bool
    collected_at: datetime
```

`source_results` 保留每个通道的完整诊断；`items` 是给业务节点使用的条目。同一个
`upstream_id` 即使有多个适配器，诊断结果都会保留，但 `items` 只输出第一份成功
数据，避免同一上游被重复包装后重复进入业务链。

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
4. 再打开 `tests/test_data/test_cninfo_direct_provider.py`，观察
   `totalAnnouncement=0` 如何成为明确空结果。
5. 对比 `cninfo-direct` 和 `akshare-cninfo` 的 `upstream_id`，确认它们为何只能算
   一个来源。
6. 思考题：如果一个聚合接口同时返回十家媒体，独立性应该按聚合商还是原始媒体算？

---

**上一篇：[LangGraph 持久检查点](31-langgraph-durable-checkpoint.md)**

**下一篇：待续**

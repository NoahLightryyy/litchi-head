# 01 Pydantic BaseModel 与模块契约

## 一句话

> Pydantic 的 `BaseModel` 是我们项目里**所有模块之间传递数据的统一格式**。就像快递箱子——不管里面装什么，箱子规格统一，拆开就知道怎么处理。

---

## 为什么需要它？

### 问题场景

想象你项目里有 4 个模块：
```
数据采集 → 分析Agent → 辩论引擎 → 前端展示
```

如果每个模块自己定义数据格式：
- 数据采集返回 `dict`：`{"code": "000001", "price": 10.5}`
- 分析 Agent 返回 `tuple`：`("000001", 10.5, 0.8)`
- 辩论引擎接受 JSON 字符串：`'{"stock":"000001"}'`

→ **三个模块要互相知道对方的格式才能对接**，改一个全部要改。

### Pydantic 的解法

定义一个**统一的契约**（Pydantic model），所有模块按这个契约说话：

```python
from pydantic import BaseModel
from datetime import datetime

class StockQuote(BaseModel):
    code: str
    price: float
    change_pct: float
    timestamp: datetime
```

无论哪个模块产出或消费股票数据，都用这个 `StockQuote`。**契约不变，模块之间就解耦了。**

---

## 和 Python 自带 `dataclass` 有什么不同？

| 对比 | `dataclass` | `BaseModel` |
|:-----|:-----------|:------------|
| 类型校验 | ❌ 不校验 | ✅ 自动校验 |
| 类型转换 | ❌ 不转换 | ✅ `"10.5"` 自动转 `10.5` |
| 序列化 JSON | 要手写 | ✅ `.model_dump()` 一步搞定 |
| 嵌套验证 | ❌ 没有 | ✅ `AgentMessage.content = EvidenceItem` 自动递归校验 |

### 看代码你就懂了

```python
from dataclasses import dataclass

@dataclass
class OldWay:
    price: float

d = OldWay(price="abc")  # ❌ 不会报错！你要等运行时炸
```

```python
from pydantic import BaseModel

class NewWay(BaseModel):
    price: float

d = NewWay(price="abc")  # ✅ 马上报错：Input should be a valid float
```

---

## 项目里怎么用的？

打开 `src/core/protocol.py`，核心的几个 Model：

```python
class EvidenceItem(BaseModel):
    """一条证据/论据"""
    content: str
    source: str
    confidence: float  # 置信度 0-1，会自动校验范围

class AgentMessage(BaseModel):
    """Agent 之间传递的消息"""
    sender: str
    content: EvidenceItem  # 嵌套！另一个 BaseModel
    round_number: int
```

关键点：
- `confidence: float` — 如果传入 `"high"` 会报错，因为不是 float
- `round_number: int` — 如果传入 `1.5` 会自动转成 `1`（int 截断）
- `content: EvidenceItem` — 嵌套校验，传入 `{"content": "x", "source": "y"}` 会自动构建

---

## ADR-001 的核心规定

> 项目约定：
> - **模块间传递** → 必须用 `BaseModel`
> - **模块内部使用** → 可以用 `dataclass` 或 `dict`
> - **不允许**：用原始 `dict` 跨模块传数据

这就是为什么你在 `src/` 里看到的所有函数签名都是 `def foo(data: StockQuote) -> AnalysisResult`，而不是 `def foo(data: dict) -> dict`。

---

## 自己试试（5 分钟）

1. 打开 `src/core/protocol.py`，找到 `AgentMessage` 类
2. 试试在 Python 里运行：
   ```python
   from src.core.protocol import AgentMessage
   msg = AgentMessage(sender="alice", content="hello")
   # 注意：content 是 EvidenceItem 类型，不是字符串
   # 猜猜会不会报错？试试看
   ```
3. 再试试正确的用法：
   ```python
   msg = AgentMessage(
       sender="alice",
       content=EvidenceItem(content="茅台PE偏高", source="分析", confidence=0.85)
   )
   print(msg.model_dump_json())  # 转成 JSON
   ```

---

**下一篇：[LangGraph StateGraph 编排](02-langgraph-stategraph.md)** — 多个 Agent 怎么串联起来工作

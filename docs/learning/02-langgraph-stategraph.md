# 02 LangGraph StateGraph 编排

## 一句话

> LangGraph 的 `StateGraph` 是**把一系列步骤像流水线一样串联起来的工具**。你定义"有哪些步骤"和"步骤之间怎么走"，它负责调度。

---

## 没有 StateGraph 之前

假设你想让 3 个 Agent 依次分析一只股票：

```python
# 手动编排 —— 写死顺序
result_a = agent_a("000001")
result_b = agent_b("000001", result_a)  # 等 a 完才能跑
result_c = agent_c("000001", result_b)  # 等 b 完才能跑
```

问题是：
- 如果在 a 和 b 之间插一个新步骤？**改代码**
- 如果 c 想跳过 b 直接用 a 的结果？**改代码**
- 状态（每个 Agent 的输出）怎么存？**自己搞个 dict**

---

## StateGraph 的解法

把流程定义成一张**有向图**：

```
                   ┌─── Agent B
   开始 → Agent A ─┤              ──→ 综合 → 结束
                   └─── Agent C
```

- 每个 Agent 是一个 **node**（节点）
- 箭头是 **edge**（边）
- 所有数据存在一个 **state**（状态对象）里，每个节点读写共享状态

---

## 项目里的真实代码

打开 `src/agents/master_agent.py`，核心骨架：

```python
from langgraph.graph import StateGraph

# 1. 定义状态 —— 整个流程共享的数据
class DebateState(BaseModel):
    stock_code: str
    analyses: list[str] = []    # 分析师分析结果
    reviews: list[str] = []     # 交叉审阅结果
    final_decision: str = ""    # 最终决策

# 2. 定义节点函数 —— 每个步骤做什么
def analyst_a(state: DebateState) -> dict:
    analysis = llm.analyze(state.stock_code)
    return {"analyses": [analysis]}  # 只返回要更新的字段

def analyst_b(state: DebateState) -> dict:
    analysis = llm.analyze(state.stock_code)
    return {"analyses": [analysis]}

# 3. 构建图
builder = StateGraph(DebateState)
builder.add_node("analyst_a", analyst_a)
builder.add_node("analyst_b", analyst_b)
builder.add_node("review", review_all)

# 4. 连接边
builder.add_edge("analyst_a", "review")   # a 做完到 review
builder.add_edge("analyst_b", "review")   # b 做完也到 review
builder.set_entry_point("analyst_a")       # 起点
builder.set_finish_point("review")         # 终点

# 5. 编译并运行
graph = builder.compile()
result = graph.invoke(DebateState(stock_code="000001"))
```

### 关键点

1. **每个节点是一个纯函数**：`(旧状态) -> (要更新的字段)`。不修改旧状态，返回新数据
2. **状态是共享的**：`analyst_a` 往 `analyses` 里加了一条，`review` 能看到所有分析师的结果
3. **边决定执行顺序**：可以串行（先 A 后 B），也可以并行（A 和 B 同时跑）

---

## 更复杂的：条件边

不是所有流程都是线性的。比如：

```python
# 根据分析结果决定后续
def router(state: DebateState) -> str:
    if len(state.analyses) < 3:
        return "need_more_analysis"  # 分析师不够，再找
    else:
        return "ready_to_review"     # 够了，开始评审

builder.add_conditional_edges(
    "analyst_a",          # 从 analyst_a 出来
    router,               # 路由函数
    {
        "need_more_analysis": "analyst_b",   # 走 analyst_b
        "ready_to_review": "review",         # 走 review
    }
)
```

---

## 为什么用 LangGraph 而不是自己写 if-else？

| 自己手写 | LangGraph |
|:---------|:----------|
| 流程改不了，硬编码 | 图结构可以动态修改 |
| 状态管理靠自己 | 自动管理状态 |
| 并行要手动 threading | 原生支持并行 node |
| 没有可视化 | `.get_graph().draw_mermaid_png()` 画流程图 |

---

## 自己试试（5 分钟）

1. 打开 `src/agents/master_agent.py`，找到 `build_graph` 函数（或类似的图构建函数）
2. 认出这几个部分：
   - [ ] 状态类 `DebateState` 长什么样
   - [ ] 有哪些 node
   - [ ] entry point 是哪个节点
   - [ ] 最终终点是哪个节点
3. 试着在脑袋里画一下这个流程图

---

**上一篇：[Pydantic BaseModel 与模块契约](01-pydantic-basemodel.md)** ← 先读那个

**下一篇：[LLM 统一封装层](03-llm-unified-layer.md)** — 为什么所有 AI 调用必须经过同一个文件

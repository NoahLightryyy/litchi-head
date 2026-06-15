# Agent 编排模块 — 架构决策

## ADR-002: LangGraph 作为 Agent 编排框架

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-03 |
| **状态** | ✅ 已采纳 |
| **影响范围** | `src/core/`, `src/debate/` |

**上下文**：
需要框架来编排多个 Agent 的工作流，支持串行/并行/条件分支和状态共享。

**决策**：
使用 LangGraph 的 `StateGraph` 作为编排引擎。

**理由**：
1. 图结构天然适配 Agent 工作流（节点=Agent，边=消息传递）
2. LangChain 生态原生支持
3. 内置并行节点和条件路由
4. 社区活跃

**舍弃方案**：
| 方案 | 舍弃理由 |
|------|---------|
| AutoGen（微软） | 多 Agent 对话强但状态管理不够灵活 |
| CrewAI | 更上层封装但可控性不如 LangGraph |
| 自定义状态机 | 灵活但重复造轮子 |
| Temporal / Airflow | 太重，适合后端服务不适合 Agent 编排 |

---

## ADR-009: MCP 工具扩展架构

| 字段 | 值 |
|------|-----|
| **日期** | 2026-06-07 |
| **状态** | ✅ 已采纳 |
| **影响范围** | `src/agents/base.py`, 所有 Agent 实现 |

**上下文**：
未来各 Agent 需要接入外部工具（新闻搜索、行情查询、金融知识库等）。

**决策**：
1. `BaseAgent` 新增 `get_tools()` 扩展点（Phase 0 返回空列表）
2. MCP 接入通过编排器的 ToolNode 实现
3. Phase 1+ 子类重写 `get_tools()` 声明所需工具

**核心接口**：
```python
class BaseAgent(ABC):
    def get_tools(self) -> list[Any]:
        """Phase 0 默认返回空列表。Phase 1+ 重写。"""
        return []
```

**后果**：
- ✅ Phase 0 Agent 纯净无外部依赖
- ✅ 未来接入 MCP 时只需重写 `get_tools()`
- ⚠️ 增加 1 个空方法（接口预留的代价）

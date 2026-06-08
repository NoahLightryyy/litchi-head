"""辩论引擎 —— 多 Agent 投资辩论

4 组大师分组辩论 + 交叉质疑 + 投票聚合。

Phase 1 实现步骤：
    1. 辩论编排器 LangGraph StateGraph
    2. 4 组大师分组辩论逻辑
    3. 交叉质疑机制
    4. 投票加权汇总
"""


class DebateEngine:
    """辩论编排器（骨架，Phase 1 实现）"""

    def __init__(self) -> None:
        raise NotImplementedError("DebateEngine 将在 Phase 1 实现")


__all__ = ["DebateEngine"]

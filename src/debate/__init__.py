"""辩论引擎 —— 多 Agent 投资辩论编排

辩论编排器（DebateOrchestrator）使用 LangGraph StateGraph 驱动多大师分析流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. master_round — 顺序运行每位投资大师
  3. aggregate — 加权投票汇总 + 共识生成

用法：
    orch = DebateOrchestrator()
    result = await orch.run(DebateInput(stock_code="000001"))
    print(result.to_summary_dict())
"""

from src.debate.models import (
    AgentAnalysis,
    DebateInput,
    DebateResult,
    PeerReviewRound,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.orchestrator import DebateOrchestrator

__all__ = [
    "AgentAnalysis",
    "DebateInput",
    "DebateOrchestrator",
    "DebateResult",
    "PeerReviewRound",
    "RebuttalAnalysis",
    "VoteSummary",
]

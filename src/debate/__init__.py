"""辩论引擎 —— 多 Agent 投资辩论编排

辩论编排器（DebateOrchestrator）使用 LangGraph StateGraph 驱动多层次分析流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. analyst_round — 4 位专业分析师（基本面/技术面/情绪面/宏观面）
  3. master_round — 大师策略师基于分析师报告综合判断
  4. review_round — 交叉审阅 + 反驳
  5. review_report — 独立评审
  6. aggregate — 加权投票汇总 + 共识生成

用法：
    orch = DebateOrchestrator()
    result = await orch.run(DebateInput(stock_code="000001"))
    print(result.to_summary_dict())
"""

from src.debate.analysts import AnalystPersona, get_default_analysts
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    DebateInput,
    DebateResult,
    IndependentReview,
    PeerReviewRound,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.orchestrator import DebateOrchestrator

__all__ = [
    "AgentAnalysis",
    "AnalystPersona",
    "AnalystReport",
    "DebateInput",
    "DebateOrchestrator",
    "DebateResult",
    "IndependentReview",
    "PeerReviewRound",
    "RebuttalAnalysis",
    "VoteSummary",
    "get_default_analysts",
]

"""辩论引擎 —— 多 Agent 投资辩论编排

辩论编排器（DebateOrchestrator）使用 LangGraph StateGraph 驱动多层次分析流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. analyst_round — 4 位专业分析师（基本面/技术面/情绪面/宏观面）
  3. master_round — 大师策略师基于分析师报告综合判断
  4. review_round — 交叉审阅（赞同+补充+异议三段式）
  5. review_report — 独立评审
  6. aggregate — 加权投票汇总 + 共识生成

记忆增强：
  · M1 历史决策注入 — query ("episodic", "debate") → 注入 prompt
  · M2 反思闭环 — query ("reflective", "debate") → 注入 prompt
     事后反思 API: orch.reflect_on_decision(stock_code, outcome)
  · M3 信任度评分 — TrustTracker 追踪每位 Agent 的历史准确率/校准/趋势
     用法: TrustTracker(store).get_trust_report("master.buffett")

用法：
    from src.debate.orchestrator import DebateOrchestrator
    orch = DebateOrchestrator()
    result = await orch.run(DebateInput(stock_code="000001"))
    print(result.to_summary_dict())

    # 事后反思
    from src.debate.reflection import ActualOutcome
    reflection = await orch.reflect_on_decision(
        stock_code="000001",
        outcome=ActualOutcome(
            stock_code="000001",
            price_change_pct=+3.5,
            actual_direction="Bullish",
        ),
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from src.debate.reflection import (
    ActualOutcome,
    ReflectionRecord,
)
from src.debate.trust import (
    AgentOutcome,
    AgentTrustMetrics,
    TrustReport,
    TrustTracker,
    compute_weight_factor,
)

if TYPE_CHECKING:
    from src.debate.orchestrator import DebateOrchestrator


def __getattr__(name: str):
    """惰性导入 DebateOrchestrator（避免 torch crash 环境问题）"""
    if name == "DebateOrchestrator":
        import importlib
        return importlib.import_module("src.debate.orchestrator").DebateOrchestrator
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

__all__ = [
    "ActualOutcome",
    "AgentAnalysis",
    "AgentOutcome",
    "AgentTrustMetrics",
    "AnalystPersona",
    "AnalystReport",
    "DebateInput",
    "DebateOrchestrator",
    "DebateResult",
    "IndependentReview",
    "PeerReviewRound",
    "RebuttalAnalysis",
    "ReflectionRecord",
    "TrustReport",
    "TrustTracker",
    "VoteSummary",
    "compute_weight_factor",
    "get_default_analysts",
]

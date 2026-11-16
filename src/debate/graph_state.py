"""辩论图的共享状态与证据限制辅助函数（自 orchestrator.py 拆出，逻辑未改）。"""

from __future__ import annotations

import logging
from typing import TypedDict

from src.data.evidence import (
    EvidenceEnvelope,
    SourceStatus,
)
from src.debate.models import (
    AgentAnalysis,
)

logger = logging.getLogger("src.debate.orchestrator")

# ── 模块级常量 ─────────────────────────────────────────────

_MAX_HISTORY_FETCH = 20  # 查询历史决策的最大条数
_DEFAULT_QUOTE_EVIDENCE_SERVICE = object()
_BLOCKING_EVIDENCE_CODES = {
    "quote_cardinality_invalid",
    "quote_identity_conflict",
    "quote_price_conflict",
    "quote_suspect",
    "quote_timestamp_conflict",
    "quote_timestamp_in_future",
    "quote_timestamp_missing",
}


def _must_block_reasoning(envelope: EvidenceEnvelope) -> bool:
    """Block only corrupted or internally conflicting evidence, not mere gaps."""
    return any(
        result.status is SourceStatus.CONFLICTED
        or result.error_code in _BLOCKING_EVIDENCE_CODES
        for result in envelope.source_results
    )


def _evidence_limitation(envelope: EvidenceEnvelope) -> dict[str, object]:
    assessment = envelope.assessment
    missing = set(assessment.missing_required_upstream_ids)
    source_statuses: dict[str, str] = {}
    for result in envelope.source_results:
        if result.status not in {SourceStatus.SUCCESS_DATA, SourceStatus.SUCCESS_EMPTY}:
            missing.add(result.upstream_id)
            source_statuses[result.source_id] = result.status.value
    return {
        "status": "limited",
        "capability": envelope.request.capability.value,
        "missing_upstream_ids": sorted(missing),
        "missing_independent_upstreams": assessment.missing_independent_upstreams,
        "source_statuses": dict(sorted(source_statuses.items())),
        "error_codes": sorted({r.error_code for r in envelope.source_results if r.error_code}),
        "collected_at": envelope.collected_at,
    }


def _format_evidence_limitation_notice(
    limitations: list[dict[str, object]],
) -> str:
    capabilities = ", ".join(str(item["capability"]) for item in limitations)
    missing_ids: set[str] = set()
    for item in limitations:
        raw_missing = item.get("missing_upstream_ids", [])
        if isinstance(raw_missing, list):
            missing_ids.update(str(upstream_id) for upstream_id in raw_missing)
    missing = sorted(missing_ids)
    missing_text = ", ".join(missing) if missing else "独立来源数量不足"
    kline_notice = (
        "K 线四层证据不可用；"
        if any(item.get("capability") == "kline_business" for item in limitations)
        else ""
    )
    research_notes = "\n".join(str(item["research_note"]) for item in limitations
                               if item.get("research_note"))
    return (
        f"{research_notes}\n"
        f"⚠️ 证据不完整：{kline_notice}{capabilities}；"
        f"缺失或不可用上游：{missing_text}。\n"
        "以下推理仅基于当前可用信息，结论必须连同本证据限制标注一起使用。"
    )


def _trim_market_data(market_data: dict) -> dict:
    """裁剪 market_data，只保留下游节点需要的简要字段（DP-007 信息隔离）

    analyst_round 之后（含）的表决链路只需要 market_data 中的文本摘要，
    原始行情/K线/新闻/财务数据数组不再需要，可以裁剪以减小 state 体积。

    Args:
        market_data: 原始 market_data dict

    Returns:
        裁剪后的 market_data，仅含 brief / industry / chain_position
    """
    return {
        "brief": market_data.get("brief", ""),
        "industry": market_data.get("industry", ""),
        "chain_position": market_data.get("chain_position", ""),
    }

# ── LangGraph State ──────────────────────────────────────────────


class DebateState(TypedDict):
    """辩论流程的共享状态

    字段说明：
        session_id:     会话标识
        debate_input:   DebateInput 的序列化 dict
        current_round:  当前辩论轮次
        analyses:       所有大师分析，{agent_name: AgentAnalysis}
        market_data:    采集的市场数据缓存
        vote_summary:   投票汇总（由 aggregate 节点写入）
        review_round:   第二轮交叉审阅结果（由 review_round 节点写入）
        review_report:  独立评审报告（由 review_report 节点写入）
        errors:         错误记录
        history_context: 历史决策上下文文本（注入到大师 prompt）
        analyst_reports: 分析师报告（由 analyst_round 节点写入）
    """

    session_id: str
    debate_input: dict
    current_round: int
    analyses: dict[str, AgentAnalysis]
    market_data: dict
    vote_summary: dict  # 序列化的 VoteSummary
    review_round: dict  # 序列化的 PeerReviewRound
    review_report: dict  # 序列化的 IndependentReview
    errors: list[str]
    history_context: str  # 历史决策上下文（注入到大师 prompt）
    reflection_context: str  # M2 反思上下文（注入到大师 prompt）
    analyst_reports: dict  # dict[str, AnalystReport], 分析师层产出
    risk_round: dict  # 序列化的 RiskRoundResult（R1 风控层）
    trader_round: dict  # 序列化的 TraderRoundResult（T1 交易员层）
    trade_recommendation: dict  # 序列化的 TradeRecommendation（R1 PM 裁决）
    trust_weight_factors: dict  # M4: agent_name → compute_weight_factor()
    calibration_map: dict  # R4: agent_name → calibration_curve list
    mirror_report: dict  # DP-006: 序列化的 MirrorReport
    evidence_envelope: dict  # 当前失败或最终证据信封；不完整时用于显式终止
    evidence_limitations: list[dict]  # 可继续推理的不完整证据标注
    evidence_references: list[dict]  # 完整证据的不可变版本引用
    evidence_failure_kind: str  # 阻断证据类型，用于恢复正确 Pydantic 联合成员

"""辩论数据契约 —— Pydantic 模型定义

辩论编排器使用的数据契约（遵循 ADR-001/008）：
1. DebateInput — 辩论输入（股票 + 问题）
2. AgentAnalysis — 单个大师的分析结果
3. VoteSummary — 投票汇总
4. DebateResult — 辩论最终输出
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class RebuttalAnalysis(BaseModel):
    """单个大师对同行观点的审阅与反驳

    在第二轮交叉审阅中，每位大师查看所有同行的分析后生成此结构。
    调用方在 adjusted_rating/adjusted_score/adjusted_confidence 为 None 时
    应使用原始 AgentAnalysis 中的对应值。

    Attributes:
        agent_name: 产生此反驳的 Agent 名称
        original_agreement: 对原分析的共识度 (0.0–1.0), 0.5 为中性
        rebuttal: 反驳或补充的核心观点文本
        adjusted_rating: 调整后评级（None 表示未调整）
        adjusted_score: 调整后评分（1-100, None 表示未调整）
        adjusted_confidence: 调整后置信度 (0.0–1.0, None 表示未调整)
        key_counterpoints: 反驳要点列表
        peer_influences: 受同行影响的说明
        latency_ms: 调用耗时（毫秒）
    """

    agent_name: str
    original_agreement: float = 0.5
    rebuttal: str = ""
    adjusted_rating: str | None = None
    adjusted_score: int | None = None
    adjusted_confidence: float | None = None
    key_counterpoints: list[str] = Field(default_factory=list)
    peer_influences: str = ""
    latency_ms: float = 0.0


class PeerReviewRound(BaseModel):
    """第二轮交叉审阅：所有大师对彼此分析的回应

    包含每位大师对同行观点的审阅记录。aggregate 节点可以根据此信息
    调整评分、评级和置信度。

    Attributes:
        rebuttals: 所有大师的反驳记录列表
        round_number: 当前轮次编号（默认为 2）
    """

    rebuttals: list[RebuttalAnalysis] = Field(default_factory=list)
    round_number: int = 2

    def __len__(self) -> int:
        return len(self.rebuttals)

    def get_for_agent(self, agent_name: str) -> RebuttalAnalysis | None:
        """按 agent_name 查找对应的反驳记录

        Args:
            agent_name: Agent 名称（如 "master.buffett"）

        Returns:
            匹配的 RebuttalAnalysis，未找到返回 None
        """
        for r in self.rebuttals:
            if r.agent_name == agent_name:
                return r
        return None


class DebateInput(BaseModel):
    """辩论输入

    定义一个辩论任务：对某只股票提出一个投资问题。
    由 DebateOrchestrator.run() 接收，驱动整个辩论流程。
    """

    stock_code: str
    stock_name: str = ""
    question: str = "请分析这只股票的投资价值"
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AgentAnalysis(BaseModel):
    """单个 Agent 的结构化分析结果

    由 MasterAgent.run() 的输出转换而来，保留所有关键信息用于后续投票聚合。
    无论分析成功或失败，均使用此结构（success=False 时含错误信息）。
    """

    agent_name: str
    skill_id: str
    skill_name: str
    rating: str
    score: int
    summary: str
    analysis: str
    key_evidence: list[str] = Field(default_factory=list)
    risk_warning: str | None = None
    confidence: float = 0.0
    success: bool = True
    error: str | None = None
    latency_ms: float = 0.0
    direction: str = "Neutral"  # D2: 强制方向判断（Bullish/Bearish/Neutral）


class VoteSummary(BaseModel):
    """投票汇总

    由 aggregate 节点计算，汇总所有成功大师的分析结果：
    - rating_distribution: 各评级统计（{评级: 数量}）
    - average_score: 所有评分的算术平均
    - weighted_score: 按 confidence 加权的平均分
    - consensus: 众数评级（最多人选的评级）
    - confidence: 共识置信度（基于一致性和专家信心）
    - adjustments_applied: 是否使用了第二轮反驳调整后的值
    - direction_distribution: 方向分布统计（D2: {Bullish/Bearish/Neutral: 数量}）
    """

    total_votes: int = 0
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    average_score: float = 0.0
    weighted_score: float = 0.0
    consensus: str = "中性"
    confidence: float = 0.0
    adjustments_applied: bool = False
    direction_distribution: dict[str, int] = Field(default_factory=dict)


class IndependentReview(BaseModel):
    """独立评审 Agent 的输出

    在 master_round（+ review_round）之后运行，以独立裁判视角评审所有大师
    的分析质量和一致性。输出结构化评估和聚合建议。

    Attributes:
        reviewer_style: 评审风格标识
        overall_quality: 辩论整体质量评分 (0.0-1.0)
        independent_rating: 独立评级（基于全部信息的判断）
        independent_score: 独立评分 (1-100)
        confidence: 对本评审的置信度 (0.0-1.0)
        consensus_support: 对当前共识的支持度 (0.0-1.0)
        quality_assessments: 对每位大师分析质量的评估
        weight_suggestions: 对每位大师的权重调整建议（乘数，0.0-2.0）
        identified_biases: 发现的集体偏见列表
        blind_spots: 所有分析中缺失的关键视角
        key_risks_synthesis: 关键风险综合
        consistency_observation: 分析间一致性的观察
        aggregation_recommendation: 对聚合方式的建议
        latency_ms: 调用耗时（毫秒）
    """

    reviewer_style: str = "independent_reviewer"
    overall_quality: float = 0.0
    independent_rating: str = "中性"
    independent_score: int = 0
    confidence: float = 0.0
    consensus_support: float = 0.5
    quality_assessments: dict[str, str] = Field(default_factory=dict)
    weight_suggestions: dict[str, float] = Field(default_factory=dict)
    identified_biases: list[str] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)
    key_risks_synthesis: str = ""
    consistency_observation: str = ""
    aggregation_recommendation: str = ""
    latency_ms: float = 0.0


class DebateResult(BaseModel):
    """辩论最终结果

    一次完整的辩论输出，包含：
    - 输入信息回溯（股票、问题）
    - 所有大师的分析
    - 投票汇总
    - 第二轮交叉审阅（可选，D1 功能）
    - 独立评审报告（可选，D3 功能）
    - 总耗时
    """

    session_id: str
    stock_code: str
    stock_name: str
    question: str
    analyses: list[AgentAnalysis] = Field(default_factory=list)
    vote_summary: VoteSummary = Field(default_factory=VoteSummary)
    review_round: PeerReviewRound | None = None
    review_report: IndependentReview | None = None
    total_latency_ms: float = 0.0

    def to_summary_dict(self) -> dict[str, Any]:
        """生成面向展示层的摘要字典"""
        vs = self.vote_summary
        result = {
            "股票代码": self.stock_code,
            "股票名称": self.stock_name,
            "问题": self.question,
            "参与大师数": len(self.analyses),
            "共识": vs.consensus,
            "平均评分": round(vs.average_score, 1),
            "加权评分": round(vs.weighted_score, 1),
            "置信度": round(vs.confidence, 2),
            "评级分布": vs.rating_distribution,
            "方向分布": vs.direction_distribution,
            "总耗时(ms)": round(self.total_latency_ms, 0),
        }
        if self.review_round is not None:
            result["交叉审阅"] = len(self.review_round) > 0
        if self.review_report is not None:
            rr = self.review_report
            result["独立评审"] = True
            result["评审质量"] = rr.overall_quality
            result["评审评级"] = rr.independent_rating
            result["评审评分"] = rr.independent_score
            if rr.identified_biases:
                result["发现偏差"] = rr.identified_biases
            if rr.blind_spots:
                result["盲区提示"] = rr.blind_spots
        return result


__all__ = [
    "AgentAnalysis",
    "DebateInput",
    "DebateResult",
    "IndependentReview",
    "PeerReviewRound",
    "RebuttalAnalysis",
    "VoteSummary",
]

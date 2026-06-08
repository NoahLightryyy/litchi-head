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


class VoteSummary(BaseModel):
    """投票汇总

    由 aggregate 节点计算，汇总所有成功大师的分析结果：
    - rating_distribution: 各评级统计（{评级: 数量}）
    - average_score: 所有评分的算术平均
    - weighted_score: 按 confidence 加权的平均分
    - consensus: 众数评级（最多人选的评级）
    - confidence: 共识置信度（基于一致性和专家信心）
    """

    total_votes: int = 0
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    average_score: float = 0.0
    weighted_score: float = 0.0
    consensus: str = "中性"
    confidence: float = 0.0


class DebateResult(BaseModel):
    """辩论最终结果

    一次完整的辩论输出，包含：
    - 输入信息回溯（股票、问题）
    - 所有大师的分析
    - 投票汇总
    - 总耗时
    """

    session_id: str
    stock_code: str
    stock_name: str
    question: str
    analyses: list[AgentAnalysis] = Field(default_factory=list)
    vote_summary: VoteSummary = Field(default_factory=VoteSummary)
    total_latency_ms: float = 0.0

    def to_summary_dict(self) -> dict[str, Any]:
        """生成面向展示层的摘要字典"""
        vs = self.vote_summary
        return {
            "股票代码": self.stock_code,
            "股票名称": self.stock_name,
            "问题": self.question,
            "参与大师数": len(self.analyses),
            "共识": vs.consensus,
            "平均评分": round(vs.average_score, 1),
            "加权评分": round(vs.weighted_score, 1),
            "置信度": round(vs.confidence, 2),
            "评级分布": vs.rating_distribution,
            "总耗时(ms)": round(self.total_latency_ms, 0),
        }


__all__ = [
    "AgentAnalysis",
    "DebateInput",
    "DebateResult",
    "VoteSummary",
]

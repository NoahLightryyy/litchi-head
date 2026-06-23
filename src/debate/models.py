"""辩论数据契约 —— Pydantic 模型定义

辩论编排器使用的数据契约（遵循 ADR-001/008）：
1. DebateInput — 辩论输入（股票 + 问题）
2. AgentAnalysis — 单个大师的分析结果
3. VoteSummary — 投票汇总
4. DebateResult — 辩论最终输出
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class RebuttalAnalysis(BaseModel):
    """单个大师对同行观点的审阅与回应（赞同+补充+异议三段式）

    在第二轮交叉审阅中，每位大师查看所有同行的分析后生成此结构。
    采用"赞同+补充+异议"三段式结构，替代原有的单一反驳字段。

    调用方在 adjusted_rating/adjusted_score/adjusted_confidence 为 None 时
    应使用原始 AgentAnalysis 中的对应值。

    Attributes:
        agent_name: 产生此回应的 Agent 名称
        original_agreement: 对原分析的共识度 (0.0–1.0), 0.5 为中性
        agreement: 赞同 — 认可同行的哪些观点
        supplement: 补充 — 额外信息、数据或分析角度
        objection: 异议 — 不认同哪些观点及理由
        adjusted_rating: 调整后评级（None 表示未调整）
        adjusted_score: 调整后评分（1-100, None 表示未调整）
        adjusted_confidence: 调整后置信度 (0.0–1.0, None 表示未调整)
        key_counterpoints: 关键要点列表
        peer_influences: 受同行影响的说明
        latency_ms: 调用耗时（毫秒）
    """

    agent_name: str
    original_agreement: float = 0.5
    agreement: str = ""
    supplement: str = ""
    objection: str = ""
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


# ═══════════════════════════════════════════════════
# BiasReport — DP-003 偏斜公示（2026-06-23 新增）
# ═══════════════════════════════════════════════════


class BiasReport(BaseModel):
    """辩论产出偏斜度报告

    在 D4 聚合阶段从 direction_distribution 计算得出，
    反映群体情绪的偏斜方向和观点集中程度。
    纯计算，不增加 LLM 调用。

    Attributes:
        bullish_count: 看涨观点数
        bearish_count: 看跌观点数
        neutral_count: 中性/观望观点数
        total_count: 总观点数
        bullish_ratio: 看涨占比 (0.0-1.0)
        bearish_ratio: 看跌占比 (0.0-1.0)
        neutral_ratio: 中性占比 (0.0-1.0)
        overall_bias: 总体偏斜度 (-1 到 +1)
            (bullish - bearish) / total
            +1=全体看涨, -1=全体看跌, 0=均衡或全中性
        consensus_strength: 共识强度 (0.0-1.0)
            max(bullish, bearish, neutral) / total
            高=观点集中, 低=分歧大
        consensus_type: 共识类型
            "Bullish" | "Bearish" | "Neutral" | "Divided"
        historical_avg_bias: 历史平均偏斜度（占位，待持久化实现）
    """

    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_count: int = 0
    bullish_ratio: float = 0.0
    bearish_ratio: float = 0.0
    neutral_ratio: float = 0.0
    overall_bias: float = 0.0
    consensus_strength: float = 0.0
    consensus_type: Literal["Bullish", "Bearish", "Neutral", "Divided"] = "Neutral"
    historical_avg_bias: float = 0.0


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
    - review_score: 独立评审的评分（D4: 来自 IndependentReview）
    - review_rating: 独立评审的评级（D4）
    - review_quality: 独立评审的整体质量评分（D4）
    - weight_adjustments: 独立评审建议的权重调整记录（D4）
    - review_notes: 评审说明摘要（D4: consistency + risk + recommendation）
    - consensus_support: 独立评审对当前共识的支持度（D4: 0.0-1.0）
    - trust_weight_factors: 信任度权重因子（M4: M3 compute_weight_factor 计算结果）
    """

    total_votes: int = 0
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    average_score: float = 0.0
    weighted_score: float = 0.0
    consensus: str = "中性"
    confidence: float = 0.0
    adjustments_applied: bool = False
    direction_distribution: dict[str, int] = Field(default_factory=dict)
    # ── D4: 评审修正字段 ─────────────────────────────
    review_score: int = 0
    review_rating: str = ""
    review_quality: float = 0.0
    weight_adjustments: dict[str, float] = Field(default_factory=dict)
    review_notes: str = ""
    consensus_support: float = 0.5
    # ── M4: 信任度权重因子 ───────────────────────────
    trust_weight_factors: dict[str, float] = Field(default_factory=dict)

    # ── DP-003: 偏斜公示 ────────────────────────────
    bias_report: BiasReport = Field(default_factory=BiasReport)


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


class AnalystReport(BaseModel):
    """单个分析师的结构化分析报告

    由 analyst_round 节点中的分析师（AnalystPersona）生成，
    作为 strategy_round 中策略师（MasterSkill）的核心输入。

    与 AgentAnalysis 不同，AnalystReport 不包含投资评级，
    而是提供专业维度的分析数据和方向提示。

    Attributes:
        analyst_type: 分析师类型（fundamental / technical / sentiment / macro）
        key_findings: 3-5 条关键发现
        data_evidence: 支撑发现的具体数据点
        red_flags: 该维度识别的风险信号
        confidence: 分析师对本报告的置信度 (0.0-1.0)
        summary: 执行摘要
        score: 该维度的评分 (1-100)
        direction_hint: 该维度的方向提示 (Bullish/Bearish/Neutral)
        latency_ms: 调用耗时（毫秒）
    """

    analyst_type: str
    key_findings: list[str] = Field(default_factory=list)
    data_evidence: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    summary: str = ""
    score: int = 0
    direction_hint: str = "Neutral"
    latency_ms: float = 0.0


class DebateResult(BaseModel):
    """辩论最终结果

    一次完整的辩论输出，包含：
    - 输入信息回溯（股票、问题）
    - 所有大师的分析
    - 投票汇总
    - 第二轮交叉审阅（可选，D1 功能）
    - 独立评审报告（可选，D3 功能）
    - 分析师报告（可选，分析师层产出）
    - 三层风控审核（可选，R1 功能）
    - PM 最终交易建议（可选，R1 功能）
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
    analyst_reports: dict[str, AnalystReport] | None = None
    risk_round: dict | None = None  # 序列化的 RiskRoundResult
    trader_round: dict | None = None  # 序列化的 TraderRoundResult (T1)
    trade_recommendation: dict | None = None  # 序列化的 TradeRecommendation
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
            # ── DP-003: 偏斜公示 ─────────────────────
            "偏斜报告": {
                "总体偏斜": vs.bias_report.overall_bias,
                "共识强度": vs.bias_report.consensus_strength,
                "共识类型": vs.bias_report.consensus_type,
                "看涨": vs.bias_report.bullish_count,
                "看跌": vs.bias_report.bearish_count,
                "观望": vs.bias_report.neutral_count,
            },
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
        # ── D4: 展示评审修正字段 ────────────────────
        if vs.review_score > 0:
            result["评审修正评分"] = vs.review_score
            result["评审修正评级"] = vs.review_rating
            result["评审修正质量"] = vs.review_quality
            result["评审共识支持度"] = vs.consensus_support
            if vs.weight_adjustments:
                result["权重调整"] = vs.weight_adjustments
            if vs.review_notes:
                result["评审说明"] = vs.review_notes
        # ── M4: 展示信任度权重因子 ──────────────────
        if vs.trust_weight_factors:
            result["信任度权重"] = vs.trust_weight_factors
        # ── 分析师报告 ─────────────────────────────
        if self.analyst_reports:
            result["分析师报告数"] = len(self.analyst_reports)
            analyst_scores = {
                atype: report.score
                for atype, report in self.analyst_reports.items()
            }
            result["分析师评分"] = analyst_scores
            directions = [
                r.direction_hint for r in self.analyst_reports.values()
            ]
            bullish = sum(1 for d in directions if d == "Bullish")
            bearish = sum(1 for d in directions if d == "Bearish")
            neutral = sum(1 for d in directions if d == "Neutral")
            result["分析师方向分布"] = {
                "Bullish": bullish, "Bearish": bearish, "Neutral": neutral,
            }
        # ── R1: 风控层 ─────────────────────────────
        if self.risk_round:
            rr = self.risk_round
            result["风控审核"] = True
            result["风控共识操作"] = rr.get("risk_consensus_action", "hold")
            result["平均风险评分"] = rr.get("avg_risk_score", 50)
            min_pct = rr.get("min_position_pct", 0)
            max_pct = rr.get("max_position_pct", 0)
            result["仓位范围"] = f"{min_pct:.0%} ~ {max_pct:.0%}"
            result["纪律违规总数"] = rr.get("total_discipline_violations", 0)
        if self.trade_recommendation:
            tr = self.trade_recommendation
            result["最终建议"] = tr.get("action", "hold").upper()
            result["建议仓位"] = f"{tr.get('position_size_pct', 0):.0%}"
            result["止损位"] = f"{tr.get('stop_loss_pct', 0):.0%}"
            result["止盈位"] = f"{tr.get('take_profit_pct', 0):.0%}"
            result["风险等级"] = tr.get("risk_level", "中等风险")
            result["纪律通过"] = tr.get("discipline_checks_passed", True)
            if tr.get("key_warnings"):
                result["关键警告"] = tr["key_warnings"]
            if tr.get("reasoning"):
                result["决策理由"] = tr["reasoning"][:300]
        # ── T1: 交易员层 ─────────────────────────────
        if self.trader_round:
            tr_data = self.trader_round
            tp = tr_data.get("trade_plan", {})
            if tp:
                result["交易计划"] = True
                result["交易方向"] = tp.get("direction", "Neutral")
                result["交易操作"] = tp.get("action", "hold").upper()
                result["目标仓位"] = f"{tp.get('total_position_pct', 0):.0%}"
                result["执行步骤数"] = len(tp.get("execution_steps", []))
                result["硬止损"] = f"{tp.get('max_drawdown_limit', 0.08):.0%}"
                result["盈亏比"] = f"{tp.get('risk_reward_ratio', 1.0):.1f}:1"
                result["仓位方法"] = tp.get("position_sizing_method", "N/A")
                if tp.get("contingency_plan"):
                    result["预案"] = tp["contingency_plan"][:200]
            result["执行摘要"] = tr_data.get("execution_summary", "")
            if tr_data.get("pm_review_required"):
                result["需PM复审"] = tr_data.get("pm_review_reason", "")
        return result


__all__ = [
    "AgentAnalysis",
    "AnalystReport",
    "BiasReport",
    "DebateInput",
    "DebateResult",
    "IndependentReview",
    "PeerReviewRound",
    "RebuttalAnalysis",
    "VoteSummary",
]

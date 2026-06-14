"""风控数据契约 —— Pydantic 模型定义

R1 三层风控辩论使用的数据契约（遵循 ADR-001/008）：
1. RiskAssessment — 单个风控官的风险评估
2. RiskRoundResult — 三层风控汇总
3. TradeRecommendation — PM 最终交易建议
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """单个风控官的风险评估

    每位风控官（激进/保守/中性）从各自风格视角审视辩论结果，
    输出结构化的风险评估。包含仓位建议、止损止盈、风险点识别等。

    Attributes:
        risk_style: 风控风格标识（aggressive/conservative/neutral）
        risk_style_label: 风控风格中文名（"激进型"/"保守型"/"中性型"）
        action: 建议操作（buy/sell/hold）
        position_size_pct: 建议仓位占总资金比例（0.0–1.0）
        stop_loss_pct: 止损比例（相对买入价，0.0–1.0）
        take_profit_pct: 止盈比例（相对买入价，0.0–1.0）
        risk_score: 风险评分（1–100，分数越低越安全）
        risk_rating: 风险评级（"低风险"/"中等风险"/"高风险"）
        key_risks: 识别的关键风险点列表
        risk_mitigations: 风险应对措施建议
        discipline_violations: 违反的交易纪律（空列表=无违规）
        analysis: 完整的风险分析文本
        confidence: 置信度（0.0–1.0）
        success: 风控分析是否成功
        error: 失败时的错误信息
        latency_ms: 调用耗时（毫秒）
    """

    risk_style: str = "neutral"  # aggressive | conservative | neutral
    risk_style_label: str = "中性型"
    action: str = "hold"  # buy | sell | hold
    position_size_pct: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    risk_score: int = 50
    risk_rating: str = "中等风险"
    key_risks: list[str] = Field(default_factory=list)
    risk_mitigations: list[str] = Field(default_factory=list)
    discipline_violations: list[str] = Field(default_factory=list)
    analysis: str = ""
    confidence: float = 0.0
    success: bool = True
    error: str | None = None
    latency_ms: float = 0.0


class RiskRoundResult(BaseModel):
    """三层风控审核汇总结果

    三位风控官（激进/保守/中性）各自独立输出后汇总。

    Attributes:
        assessments: 风控评估字典，key 为 risk_style
        errors: 本轮执行中的错误记录
        risk_consensus_action: 三位风控官的操作共识
        avg_risk_score: 平均风险评分
        min_position_pct: 最小建议仓位（最保守估计）
        max_position_pct: 最大建议仓位（最激进估计）
        avg_stop_loss_pct: 平均止损建议
        total_discipline_violations: 所有风控官识别的纪律违规总数
    """

    assessments: dict[str, RiskAssessment] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    risk_consensus_action: str = "hold"
    avg_risk_score: int = 50
    min_position_pct: float = 0.0
    max_position_pct: float = 0.0
    avg_stop_loss_pct: float = 0.0
    total_discipline_violations: int = 0


class TradeRecommendation(BaseModel):
    """PM（Portfolio Manager）最终交易建议

    PM 综合辩论结果 + 三层风控审核后的最终裁决。
    这是整个分析链路（分析师→策略师→辩论→风控→PM）的最终产出。

    Attributes:
        action: 最终操作建议（buy/sell/hold）
        position_size_pct: 最终建议仓位比例
        stop_loss_pct: 最终止损比例
        take_profit_pct: 最终止盈比例
        reasoning: PM 综合各方意见后的决策理由
        risk_level: 最终风险等级（"低风险"/"中等风险"/"高风险"）
        confidence: PM 对最终决策的置信度
        key_warnings: 关键风险警告（来自风控层）
        risk_consensus: 风控层共识描述
        risk_officers_summary: 三位风控官的简易概览
        discipline_checks_passed: 是否通过了全部交易纪律检查
        discipline_summary: 交易纪律检查摘要
        latency_ms: 调用耗时
    """

    action: str = "hold"
    position_size_pct: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    reasoning: str = ""
    risk_level: str = "中等风险"
    confidence: float = 0.0
    key_warnings: list[str] = Field(default_factory=list)
    risk_consensus: str = ""
    risk_officers_summary: str = ""
    discipline_checks_passed: bool = True
    discipline_summary: str = ""
    latency_ms: float = 0.0

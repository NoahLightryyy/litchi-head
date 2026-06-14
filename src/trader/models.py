"""交易员数据契约 —— Pydantic 模型定义

T1 交易员层使用的数据契约（遵循 ADR-001/008）：
1. ExecutionStep — 单步执行指令
2. TradePlan — 交易员产出的完整执行计划
3. TraderRoundResult — 交易员轮次汇总
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """单步执行指令

    交易员将总仓位拆分为多个步骤顺序执行。每步有明确的价格条件或技术信号触发，
    避免一次性投入全部仓位造成市场冲击。

    Attributes:
        step: 步骤序号（1-based）
        action: 操作类型（buy / sell / hold）
        quantity_pct: 该步仓位占总资金比例（0.0–1.0）
        price_condition: 触发该步执行的价格条件描述
        timing: 执行时机（"立即" / "等回调" / "等突破确认" / "分批"）
        stop_loss_pct: 该步独立的止损比例（None 则沿用全局止损）
        signal_triggers: 触发该步的技术信号列表
        rationale: 该步的执行理由
    """

    step: int = 1
    action: str = "buy"
    quantity_pct: float = 0.0
    price_condition: str = ""
    timing: str = "立即"
    stop_loss_pct: float | None = None
    signal_triggers: list[str] = Field(default_factory=list)
    rationale: str = ""


class TradePlan(BaseModel):
    """交易员产出的完整执行计划

    交易员接收上游信息（辩论结果 + 风控评估 + PM 方向指示），
    将其转化为结构化的多步执行计划。

    Attributes:
        ticker: 股票代码
        direction: 交易方向（Bullish / Bearish / Neutral）
        action: 总体操作（buy / sell / hold）
        total_position_pct: 目标总仓位比例（0.0–1.0）
        execution_steps: 顺序执行的步骤列表
        max_drawdown_limit: 最大回撤熔断线（触发即清仓）
        time_horizon_days: 预期持仓天数
        risk_reward_ratio: 预期盈亏比
        position_sizing_method: 仓位计算方法（"kelly" / "fixed_fraction" / "volatility_adjusted"）
        contingency_plan: 意外情况预案（如"若大盘单日跌超3%，暂停加仓"）
        trader_notes: 交易员的分析注释
        confidence: 交易员对执行方案的置信度（0.0–1.0）
        success: 是否成功生成方案
        error: 失败时的错误信息
        latency_ms: 调用耗时（毫秒）
    """

    ticker: str = ""
    direction: str = "Neutral"
    action: str = "hold"
    total_position_pct: float = 0.0
    execution_steps: list[ExecutionStep] = Field(default_factory=list)
    max_drawdown_limit: float = 0.08  # 默认 8% 硬止损
    time_horizon_days: int = 20
    risk_reward_ratio: float = 1.0
    position_sizing_method: str = "fixed_fraction"
    contingency_plan: str = ""
    trader_notes: str = ""
    confidence: float = 0.0
    success: bool = True
    error: str | None = None
    latency_ms: float = 0.0


class TraderRoundResult(BaseModel):
    """交易员轮次汇总结果

    包含交易员产出的执行计划 + 执行摘要，供 PM 最终裁决时参考。

    Attributes:
        trade_plan: 交易员完整执行计划
        execution_summary: 人类可读的执行计划摘要
        key_risks_in_execution: 执行层面的关键风险
        pm_review_required: 是否需要 PM 特别关注
        pm_review_reason: 需要 PM 关注的原因
    """

    trade_plan: TradePlan = Field(default_factory=TradePlan)
    execution_summary: str = ""
    key_risks_in_execution: list[str] = Field(default_factory=list)
    pm_review_required: bool = False
    pm_review_reason: str = ""
    errors: list[str] = Field(default_factory=list)

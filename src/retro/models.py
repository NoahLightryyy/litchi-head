"""交易复盘数据契约 —— Pydantic 模型定义

一次辩论完成后自动生成复盘记录（RetroRecord），
追踪 AI 推荐了什么 → 用户做了什么 → 实际结果如何。

完整复盘看板 = RetroRecord 列表 + RetroSummary 聚合统计
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RetroRecord(BaseModel):
    """单条复盘记录

    每次辩论完成自动创建，记录 AI 推荐的真实快照，
    后续可手动补全用户操作和实际盈亏。

    Attributes:
        record_id: 记录唯一标识（UUID）
        session_id: 关联的辩论会话 ID
        stock_code: 股票代码
        stock_name: 股票名称
        created_at: 记录创建时间
        debate_latency_ms: 辩论耗时（毫秒）
        consensus: AI 共识方向
        weighted_score: 加权评分
        confidence: 置信度 (0.0-1.0)
        direction_distribution: 方向分布 {Bullish/Bearish/Neutral: 数量}
        avg_score: 大师平均评分
        rating_distribution: 评级分布
        price_at_debate: 辩论时的最新价（用于后续计算实际涨跌幅）
        user_action: 用户操作（buy/sell/hold 或 None）
        user_action_at: 用户操作时间
        actual_return_pct: 实际涨跌幅（%）
        actual_price: 实际价格（用于计算的实际价格）
        outcome: 结果（correct/wrong/pending）
        notes: 用户备注
    """

    record_id: str = ""
    session_id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    debate_latency_ms: float = 0.0

    # ── AI 推荐快照 ──
    consensus: str = ""
    weighted_score: float = 0.0
    confidence: float = 0.0
    direction_distribution: dict[str, int] = Field(default_factory=dict)
    avg_score: float = 0.0
    rating_distribution: dict[str, int] = Field(default_factory=dict)

    # ── 行情快照 ──
    price_at_debate: float | None = None

    # ── 用户操作（可选） ──
    user_action: str | None = None
    user_action_at: datetime | None = None

    # ── 实际结果（可选） ──
    actual_return_pct: float | None = None
    actual_price: float | None = None
    outcome: Literal["correct", "wrong", "pending"] = "pending"
    notes: str = ""


class RetroSummary(BaseModel):
    """复盘聚合统计

    基于所有 RetroRecord 计算的汇总指标，用于前端聚合卡片展示。

    Attributes:
        total_records: 总记录数
        today_records: 今日新增
        closed_records: 已有明确结果的记录数
        win_count: 正确次数
        loss_count: 错误次数
        win_rate: 准确率（仅 closed_records）
        avg_confidence: 平均置信度
        avg_score: 平均加权评分
        last_record_at: 最近一次辩论时间
    """

    total_records: int = 0
    today_records: int = 0
    closed_records: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_score: float = 0.0
    last_record_at: datetime | None = None


def compute_retro_summary(records: list[RetroRecord]) -> RetroSummary:
    """从记录列表计算聚合统计

    Args:
        records: 复盘记录列表

    Returns:
        聚合统计摘要
    """
    total = len(records)
    today = sum(
        1
        for r in records
        if r.created_at.date() == datetime.now().date()
    )
    closed = [r for r in records if r.outcome != "pending"]
    wins = sum(1 for r in closed if r.outcome == "correct")
    losses = sum(1 for r in closed if r.outcome == "wrong")

    avg_conf = (
        sum(r.confidence for r in records) / total
        if total > 0
        else 0.0
    )
    avg_score = (
        sum(r.weighted_score for r in records) / total
        if total > 0
        else 0.0
    )

    last_at: datetime | None = None
    if records:
        # 按 created_at 降序取最新
        sorted_records = sorted(records, key=lambda r: r.created_at, reverse=True)
        last_at = sorted_records[0].created_at

    return RetroSummary(
        total_records=total,
        today_records=today,
        closed_records=len(closed),
        win_count=wins,
        loss_count=losses,
        win_rate=round(wins / len(closed), 4) if closed else 0.0,
        avg_confidence=round(avg_conf, 4),
        avg_score=round(avg_score, 2),
        last_record_at=last_at,
    )


def compute_outcome(
    direction: str,
    return_pct: float,
    threshold: float = 0.5,
) -> Literal["correct", "wrong"]:
    """根据方向判断结果对错

    看涨 Bullish → 涨幅 > threshold → correct
    看跌 Bearish → 跌幅 > threshold → correct
    中性 Neutral → 涨跌幅 < threshold → correct
    否则 wrong

    Args:
        direction: 方向（Bullish/Bearish/Neutral）
        return_pct: 实际涨跌幅（%），如 3.0 表示涨 3%
        threshold: 判断阈值（默认 0.5%，单位与 return_pct 一致）

    Returns:
        correct 或 wrong
    """
    if direction == "Bullish":
        return "correct" if return_pct > threshold else "wrong"
    if direction == "Bearish":
        return "correct" if return_pct < -threshold else "wrong"
    # Neutral: 不涨不跌算对
    return "correct" if abs(return_pct) <= threshold else "wrong"


__all__ = [
    "RetroRecord",
    "RetroSummary",
    "compute_retro_summary",
    "compute_outcome",
]

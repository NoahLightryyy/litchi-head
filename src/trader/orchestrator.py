"""交易员编排器 —— T1 交易员层执行节点

T1 核心模块：在风控审核之后插入交易员执行规划层，
将 PM 的投资决策转化为具体的、分步的、可执行的交易计划。

节点：
    1. trader_round — 交易员基于上游信息制定多步执行方案

用法：
    from src.trader.orchestrator import make_trader_round_node

    trader_node = make_trader_round_node(trader_profile)
"""

from __future__ import annotations

import time
from typing import Any, cast

from src.debate.models import VoteSummary
from src.trader.models import ExecutionStep, TradePlan, TraderRoundResult
from src.trader.profiles import TraderProfile
from src.utils.llm import llm_service

# ── 单个交易员执行 ──────────────────────────────────────────────


async def _run_trader(
    profile: TraderProfile,
    session_id: str,
    question: str,
    stock_code: str,
    vote_summary_text: str = "",
    risk_assessments_text: str = "",
    pm_direction_text: str = "",
    strategy_analyses_text: str = "",
) -> TradePlan:
    """运行交易员制定执行计划

    构建包含辩论结果 + 风控审核 + PM 方向的 prompt，
    调用 LLM 生成结构化 TradePlan。
    失败时返回默认 TradePlan（不中断流程）。

    Args:
        profile: 交易员人格定义
        session_id: 会话 ID
        question: 原始投资问题
        stock_code: 股票代码
        vote_summary_text: 辩论投票汇总
        risk_assessments_text: 风控审核结果
        pm_direction_text: PM 方向指示
        strategy_analyses_text: 策略师分析摘要

    Returns:
        结构化的交易执行计划
    """
    start = time.monotonic()
    try:
        prompt_parts: list[str] = [
            f"## 股票\n{stock_code}",
            f"## 投资问题\n{question}",
        ]

        if strategy_analyses_text:
            prompt_parts.append(f"## 策略师分析摘要\n{strategy_analyses_text}")

        prompt_parts.append(f"## 辩论投票汇总\n{vote_summary_text}")

        if risk_assessments_text:
            prompt_parts.append(f"## 风控审核结果\n{risk_assessments_text}")

        if pm_direction_text:
            prompt_parts.append(f"## PM 方向指示\n{pm_direction_text}")

        prompt_parts.append(
            "\n## 你的任务\n"
            "作为交易执行专家，请基于以上信息制定具体的多步执行计划。\n"
            "你必须输出结构化的 TradePlan，包含以下字段：\n\n"
            "1. direction: 交易方向（Bullish/Bearish/Neutral）\n"
            "2. action: 总体操作（buy/sell/hold）\n"
            "3. total_position_pct: 目标总仓位比例（0.0–1.0）\n"
            "4. execution_steps: 至少 1 步的执行步骤列表，每步包含：\n"
            "   - step: 步骤序号（从 1 开始）\n"
            "   - action: 该步操作（buy/sell/hold）\n"
            "   - quantity_pct: 该步仓位比例\n"
            "   - price_condition: 触发该步的价格条件\n"
            "   - timing: 执行时机\n"
            "   - signal_triggers: 技术信号触发条件列表\n"
            "   - rationale: 该步理由\n"
            "5. max_drawdown_limit: 最大回撤熔断线（如 0.08 表示 8% 硬止损）\n"
            "6. time_horizon_days: 预期持仓天数\n"
            "7. risk_reward_ratio: 预期盈亏比\n"
            "8. position_sizing_method: 仓位计算方法（kelly/fixed_fraction/volatility_adjusted）\n"
            "9. contingency_plan: 意外情况预案（大盘暴跌/个股跌停等）\n"
            "10. trader_notes: 交易员注释（150–300 字）\n"
            "11. confidence: 置信度（0.0–1.0）\n"
        )

        prompt = "\n\n".join(prompt_parts)

        raw = cast(TradePlan, await llm_service.invoke_structured(
            prompt=prompt,
            output_model=TradePlan,
            system_prompt=profile.system_prompt,
            agent_name="trader.execution",
            session_id=session_id,
        ))

        elapsed = (time.monotonic() - start) * 1000

        # 规范化并钳制数值
        steps = []
        for s in raw.execution_steps or []:
            steps.append(ExecutionStep(
                step=max(1, s.step),
                action=s.action or "hold",
                quantity_pct=max(0.0, min(1.0, s.quantity_pct)),
                price_condition=s.price_condition or "",
                timing=s.timing or "立即",
                stop_loss_pct=(
                    max(0.0, min(1.0, s.stop_loss_pct))
                    if s.stop_loss_pct is not None
                    else None
                ),
                signal_triggers=list(s.signal_triggers or []),
                rationale=s.rationale or "",
            ))

        return TradePlan(
            ticker=stock_code,
            direction=raw.direction or "Neutral",
            action=raw.action or "hold",
            total_position_pct=max(0.0, min(1.0, raw.total_position_pct)),
            execution_steps=steps,
            max_drawdown_limit=max(0.0, min(1.0, raw.max_drawdown_limit or 0.08)),
            time_horizon_days=max(1, raw.time_horizon_days or 20),
            risk_reward_ratio=max(0.0, raw.risk_reward_ratio or 1.0),
            position_sizing_method=raw.position_sizing_method or "fixed_fraction",
            contingency_plan=raw.contingency_plan or "",
            trader_notes=raw.trader_notes or "",
            confidence=max(0.0, min(1.0, raw.confidence)),
            success=True,
            latency_ms=round(elapsed, 0),
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return TradePlan(
            ticker=stock_code,
            action="hold",
            confidence=0.0,
            success=False,
            error=str(e),
            latency_ms=round(elapsed, 0),
        )


# ── 节点工厂 ────────────────────────────────────────────────────


def make_trader_round_node(
    trader_profile: TraderProfile | None = None,
    node_name: str = "trader_round",
):
    """创建交易员轮次节点

    交易员接收上游信息（辩论投票 + 风控审核 + PM 方向），
    制定结构化的多步执行计划。

    Args:
        trader_profile: 交易员人格配置（None 则使用默认）
        node_name: 节点名称（用于日志）

    Returns:
        异步节点函数 (state) -> dict[str, TraderRoundResult]
    """
    from src.trader.profiles import get_default_trader

    profile = trader_profile or get_default_trader()

    async def trader_round_node(state: dict) -> dict:
        """交易员制定执行计划"""
        inp = state.get("debate_input", {})
        sid = state.get("session_id", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        code = inp.get("stock_code", "")

        # 收集上游信息
        vote_summary = state.get("vote_summary", {})
        vote_text = _format_vote_for_trader(vote_summary)

        # 策略师分析摘要
        analyses: dict = state.get("analyses", {})
        strategy_text = _format_analyses_for_trader(analyses)

        # 风控结果
        risk_data = state.get("risk_round", {})
        risk_text = _format_risk_for_trader(risk_data) if risk_data else ""

        # PM 方向（如果已有）
        pm_data = state.get("trade_recommendation", {})
        pm_text = _format_pm_for_trader(pm_data) if pm_data else ""

        # 分析师报告
        analyst_reports: list[dict] = state.get("analyst_reports", []) or []
        if analyst_reports:
            # 策略文本中已经包含了分析师报告摘要，这里不再重复
            pass

        trade_plan = await _run_trader(
            profile=profile,
            session_id=sid,
            question=question,
            stock_code=code,
            vote_summary_text=vote_text,
            risk_assessments_text=risk_text,
            pm_direction_text=pm_text,
            strategy_analyses_text=strategy_text,
        )

        # 生成人类可读的执行摘要
        exec_summary = _build_execution_summary(trade_plan)

        # 检测执行层面的关键风险
        exec_risks = _detect_execution_risks(trade_plan)

        # 判断是否需要 PM 特别关注
        needs_pm = trade_plan.total_position_pct > 0.15 or not trade_plan.success
        pm_reason = ""
        if trade_plan.total_position_pct > 0.15:
            pm_reason = f"仓位比例 {trade_plan.total_position_pct:.0%} 较高，建议 PM 复审"
        if not trade_plan.success:
            pm_reason = f"交易员规划失败: {trade_plan.error}"

        result = TraderRoundResult(
            trade_plan=trade_plan,
            execution_summary=exec_summary,
            key_risks_in_execution=exec_risks,
            pm_review_required=needs_pm,
            pm_review_reason=pm_reason,
        )

        return {"trader_round": result.model_dump(), "state_updated": True}

    setattr(trader_round_node, "__name__", node_name)
    return trader_round_node


# ── 格式化辅助 ──────────────────────────────────────────────────


def _vs_get(vs: dict | VoteSummary, key: str, default: Any = None) -> Any:
    """安全读取 VoteSummary 或 dict 的字段

    兼容两个阶段的数据格式：
    - aggregate 节点之前：state 中 vote_summary 为 dict
    - aggregate 节点之后：state 中 vote_summary 为 VoteSummary Pydantic 对象
    """
    if isinstance(vs, VoteSummary):
        return getattr(vs, key, default)
    return vs.get(key, default)


def _fmt_score(vs: dict | VoteSummary) -> str:
    """安全格式化 VoteSummary 中的评分字段"""
    raw = _vs_get(vs, "weighted_score", 0)
    if isinstance(raw, (int, float)):
        return f"最终评分: {raw:.2f}"
    return f"最终评分: {raw}"


def _format_vote_for_trader(vote_summary: dict | VoteSummary) -> str:
    """将 VoteSummary 格式化为交易员可读的文本"""
    if not vote_summary:
        return "（无辩论投票数据）"

    vs = vote_summary
    consensus = _vs_get(vs, "consensus", "N/A")
    total_votes_val = _vs_get(vs, "total_votes", 0)
    dd = _vs_get(vs, "direction_distribution", {})
    support = _vs_get(vs, "consensus_support", 0.0)
    rn = _vs_get(vs, "review_notes", "")

    parts: list[str] = [
        _fmt_score(vs),
        f"最终信号: {consensus}",
        f"参与大师数: {total_votes_val}",
        f"方向分布: {dd}",
    ]

    if support:
        parts.append(f"共识支持度: {support:.2f}")
    if rn:
        parts.append(f"评审说明: {rn}")

    return "\n".join(parts)


def _format_analyses_for_trader(analyses: dict) -> str:
    """格式化策略师分析摘要"""
    if not analyses:
        return "（无策略师分析数据）"

    lines: list[str] = []
    for name, analysis in analyses.items():
        if isinstance(analysis, dict):
            direction = analysis.get("direction", "?")
            score = analysis.get("score", 0)
            summary = analysis.get("summary", "")[:120]
            lines.append(f"- [{direction}] {name}: 评分 {score} | {summary}")
        else:
            lines.append(f"- {name}: {str(analysis)[:150]}")

    return "\n".join(lines) if lines else "（无策略师分析数据）"


def _format_risk_for_trader(risk_data: dict) -> str:
    """格式化风控审核结果"""
    if not risk_data:
        return "（无风控数据）"

    parts: list[str] = [
        f"风控共识操作: {risk_data.get('risk_consensus_action', 'N/A')}",
        f"平均风险评分: {risk_data.get('avg_risk_score', 50)}",
        (
            f"仓位建议范围: {risk_data.get('min_position_pct', 0):.1%}"
            f" – {risk_data.get('max_position_pct', 0):.1%}"
        ),
        f"平均止损建议: {risk_data.get('avg_stop_loss_pct', 0):.1%}",
    ]

    assessments = risk_data.get("assessments", {})
    if assessments:
        parts.append("\n风控官详情:")
        for style, assess in assessments.items():
            if isinstance(assess, dict):
                parts.append(
                    f"  [{style}] action={assess.get('action', '?')} "
                    f"position={assess.get('position_size_pct', 0):.1%} "
                    f"risk_score={assess.get('risk_score', 50)}"
                )

    return "\n".join(parts)


def _format_pm_for_trader(pm_data: dict) -> str:
    """格式化 PM 方向指示"""
    if not pm_data:
        return "（PM 尚未给出方向指示）"

    return (
        f"PM 最终操作: {pm_data.get('action', 'N/A')}\n"
        f"PM 仓位建议: {pm_data.get('position_size_pct', 0):.1%}\n"
        f"PM 止损建议: {pm_data.get('stop_loss_pct', 0):.1%}\n"
        f"PM 决策理由: {pm_data.get('reasoning', 'N/A')[:300]}"
    )


def _build_execution_summary(trade_plan: TradePlan) -> str:
    """生成人类可读的执行计划摘要"""
    if not trade_plan.success:
        return f"⚠️ 交易计划生成失败: {trade_plan.error}"

    step_count = len(trade_plan.execution_steps)
    total_qty = sum(s.quantity_pct for s in trade_plan.execution_steps)

    lines = [
        f"📊 {trade_plan.ticker} | 方向: {trade_plan.direction} | "
        f"操作: {trade_plan.action.upper()} | 目标仓位: {trade_plan.total_position_pct:.1%}",
        f"📋 执行步骤: {step_count} 步 | 总执行量: {total_qty:.1%}",
        f"⏱ 持仓周期: {trade_plan.time_horizon_days} 天 | "
        f"盈亏比: {trade_plan.risk_reward_ratio:.1f}:1",
        f"🛑 硬止损: {trade_plan.max_drawdown_limit:.1%} | "
        f"仓位方法: {trade_plan.position_sizing_method}",
    ]

    for s in trade_plan.execution_steps:
        sl_info = f"止损 {s.stop_loss_pct:.1%}" if s.stop_loss_pct is not None else "全局止损"
        lines.append(
            f"  步骤{s.step}: {s.action.upper()} {s.quantity_pct:.1%} | "
            f"条件: {s.price_condition or '市价'} | "
            f"时机: {s.timing} | {sl_info}"
        )

    if trade_plan.contingency_plan:
        lines.append(f"📝 预案: {trade_plan.contingency_plan[:200]}")

    return "\n".join(lines)


def _detect_execution_risks(trade_plan: TradePlan) -> list[str]:
    """检测执行计划中的关键风险"""
    risks: list[str] = []

    if not trade_plan.success:
        risks.append("交易计划生成失败，无法执行")
        return risks

    # 总仓位超限
    if trade_plan.total_position_pct > 0.20:
        risks.append(f"⚠️ 总仓位 {trade_plan.total_position_pct:.1%} 超过单票上限 20%")

    # 首次建仓过猛
    if (
        trade_plan.execution_steps
        and trade_plan.execution_steps[0].quantity_pct
        > trade_plan.total_position_pct * 0.5
    ):
        risks.append("首次建仓超过目标仓位的 50%，建议拆分")

    # 止损太宽
    if trade_plan.max_drawdown_limit > 0.12:
        risks.append(f"硬止损 {trade_plan.max_drawdown_limit:.1%} 较宽，可能造成过大亏损")

    # 持仓周期过短
    if trade_plan.time_horizon_days < 3:
        risks.append(f"持仓周期仅 {trade_plan.time_horizon_days} 天，可能存在过度交易风险")

    # 无预案
    if not trade_plan.contingency_plan:
        risks.append("缺少意外情况预案")

    # 盈亏比不利
    if trade_plan.risk_reward_ratio < 1.0:
        risks.append(f"盈亏比 {trade_plan.risk_reward_ratio:.1f}:1 不利（<1:1）")

    return risks

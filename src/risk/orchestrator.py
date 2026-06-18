"""风控编排器 —— 三层风控辩论 + PM 最终裁决

R1 核心模块：在辩论聚合层之后插入三层风控审核，
由 Portfolio Manager 综合各方意见做出最终交易决策。

节点：
    1. risk_round — 三位风控官顺序运行（复用 master_round 模式）
    2. pm_round — PM 综合辩论结果 + 风控审核 → TradeRecommendation

用法：
    from src.risk.orchestrator import make_risk_round_node, make_pm_round_node

    risk_node = make_risk_round_node(risk_officers)
    pm_node = make_pm_round_node()
"""

from __future__ import annotations

import logging
import time
from typing import cast

from src.risk.models import (
    RiskAssessment,
    RiskRoundResult,
    TradeRecommendation,
)
from src.risk.profiles import RiskOfficerProfile
from src.utils.llm import llm_service

logger = logging.getLogger(__name__)

# ── 单个风控官执行 ──────────────────────────────────────────────


async def _run_single_risk_officer(
    profile: RiskOfficerProfile,
    session_id: str,
    question: str,
    stock_code: str,
    vote_summary_text: str,
    strategy_analyses_text: str = "",
    analyst_reports_text: str = "",
) -> RiskAssessment:
    """运行一位风控官的风险评估

    构建包含辩论结果 + 交易纪律的 prompt，调用 LLM 生成结构化 RiskAssessment。
    失败时返回默认 RiskAssessment（不中断流程）。

    Args:
        profile: 风控官人格定义
        session_id: 会话 ID
        question: 原始投资问题
        stock_code: 股票代码
        vote_summary_text: 辩论投票汇总（aggregate 节点产出）
        strategy_analyses_text: 策略师分析摘要
        analyst_reports_text: 分析师报告摘要

    Returns:
        结构化的风险评估
    """
    start = time.monotonic()
    try:
        prompt_parts: list[str] = [
            f"## 投资问题\n{question}",
            f"## 股票代码\n{stock_code}",
        ]

        if analyst_reports_text:
            prompt_parts.append(f"## 专业分析师报告\n{analyst_reports_text}")
        if strategy_analyses_text:
            prompt_parts.append(f"## 策略师分析摘要\n{strategy_analyses_text}")

        prompt_parts.append(f"## 辩论投票汇总\n{vote_summary_text}")

        prompt_parts.append(
            "\n## 你的任务\n"
            "作为风控官，请从你的视角独立审视以上分析，输出结构化的风险评估。\n"
            "必须包含以下字段：\n"
            "1. action: 建议操作（buy/sell/hold）\n"
            "2. position_size_pct: 建议仓位比例（0.0–1.0）\n"
            "3. stop_loss_pct: 止损比例（相对买入价）\n"
            "4. take_profit_pct: 止盈比例（相对买入价）\n"
            "5. risk_score: 风险评分（1–100，分数越低越安全）\n"
            "6. risk_rating: 风险评级（\"低风险\"/\"中等风险\"/\"高风险\"）\n"
            "7. key_risks: 识别的关键风险点列表\n"
            "8. risk_mitigations: 风险应对措施建议\n"
            "9. discipline_violations: 违反的交易纪律（如无则为空列表）\n"
            "10. analysis: 完整的风险分析文本（300–500 字）\n"
            "11. confidence: 置信度（0.0–1.0）\n"
        )

        prompt = "\n\n".join(prompt_parts)

        raw = cast(RiskAssessment, await llm_service.invoke_structured(
            prompt=prompt,
            output_model=RiskAssessment,
            system_prompt=profile.system_prompt,
            agent_name=f"risk.{profile.style}",
            session_id=session_id,
        ))

        elapsed = (time.monotonic() - start) * 1000

        return RiskAssessment(
            risk_style=profile.style,
            risk_style_label=profile.name,
            action=raw.action or "hold",
            position_size_pct=max(0.0, min(1.0, raw.position_size_pct)),
            stop_loss_pct=max(0.0, min(1.0, raw.stop_loss_pct)),
            take_profit_pct=max(0.0, min(1.0, raw.take_profit_pct)),
            risk_score=max(1, min(100, raw.risk_score)),
            risk_rating=raw.risk_rating or "中等风险",
            key_risks=list(raw.key_risks),
            risk_mitigations=list(raw.risk_mitigations),
            discipline_violations=list(raw.discipline_violations),
            analysis=raw.analysis,
            confidence=max(0.0, min(1.0, raw.confidence)),
            success=True,
            latency_ms=round(elapsed, 0),
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return RiskAssessment(
            risk_style=profile.style,
            risk_style_label=profile.name,
            action="hold",
            confidence=0.0,
            success=False,
            error=str(e),
            latency_ms=round(elapsed, 0),
        )


# ── 节点工厂 ────────────────────────────────────────────────────


def make_risk_round_node(
    officers: list[RiskOfficerProfile],
    node_name: str = "risk_round",
):
    """创建风险审核轮次节点 —— 顺序运行三位风控官

    采用顺序执行（与 master_round 相同），避免 LangGraph 并行写入冲突。
    每位风控官失败不阻塞后续。

    Args:
        officers: 参与审核的风控官列表（默认 3 位）
        node_name: 节点名称（用于日志）

    Returns:
        异步节点函数 (state) -> dict[str, RiskRoundResult]
    """

    async def risk_round_node(state: dict) -> dict:
        """运行三层风控审核"""
        inp = state.get("debate_input", {})
        sid = state.get("session_id", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        code = inp.get("stock_code", "")

        # 从 state 读取辩论结果
        vs_raw = state.get("vote_summary", {})
        analyses_raw = state.get("analyses", {})

        # 格式化辩论汇总文本（供风控官阅读）
        vote_summary_text = _format_vote_summary_for_risk(vs_raw)
        strategy_text = _format_strategy_analyses_for_risk(analyses_raw)

        # 格式化分析师报告
        ar_raw = state.get("analyst_reports", {})
        analyst_text = _format_analyst_reports_for_risk(ar_raw)

        assessments: dict[str, RiskAssessment] = {}
        all_errors: list[str] = []

        for officer in officers:
            result = await _run_single_risk_officer(
                profile=officer,
                session_id=sid,
                question=question,
                stock_code=code,
                vote_summary_text=vote_summary_text,
                strategy_analyses_text=strategy_text,
                analyst_reports_text=analyst_text,
            )
            key = f"risk.{officer.style}"
            assessments[key] = result
            if not result.success:
                all_errors.append(f"{key}: {result.error}")

        # 计算风险共识
        actions = [a.action for a in assessments.values() if a.success]
        scores = [a.risk_score for a in assessments.values() if a.success]
        positions = [a.position_size_pct for a in assessments.values() if a.success]
        stop_losses = [a.stop_loss_pct for a in assessments.values() if a.success]
        violations = sum(
            len(a.discipline_violations) for a in assessments.values() if a.success
        )

        if actions:
            # 众数作为共识
            consensus_action = max(set(actions), key=actions.count)
        else:
            consensus_action = "hold"

        risk_round_result = RiskRoundResult(
            assessments=assessments,
            errors=all_errors,
            risk_consensus_action=consensus_action,
            avg_risk_score=round(sum(scores) / len(scores)) if scores else 50,
            min_position_pct=min(positions) if positions else 0.0,
            max_position_pct=max(positions) if positions else 0.0,
            avg_stop_loss_pct=(
                round(sum(stop_losses) / len(stop_losses), 3) if stop_losses else 0.0
            ),
            total_discipline_violations=violations,
        )

        return {node_name: risk_round_result.model_dump()}

    return risk_round_node


def make_pm_round_node(
    node_name_output: str = "trade_recommendation",
    risk_round_key: str = "risk_round",
):
    """创建 PM（Portfolio Manager）最终裁决节点

    PM 综合辩论结果 + 三层风控审核，做出最终交易决策。
    这是整个分析链路的终点。

    Args:
        node_name_output: 节点输出写入 state 的 key
        risk_round_key: 从 state 读取风险审核结果的 key

    Returns:
        异步节点函数 (state) -> dict
    """

    async def pm_round_node(state: dict) -> dict:
        """PM 最终裁决"""
        start = time.monotonic()
        sid = state.get("session_id", "")

        # 读取辩论汇总
        vs_raw = state.get("vote_summary", {})
        vote_summary_text = _format_vote_summary_for_risk(vs_raw)

        # 读取风控审核
        rr_raw = state.get(risk_round_key, {})
        if rr_raw and isinstance(rr_raw, dict):
            try:
                risk_round = RiskRoundResult(**rr_raw)
            except Exception:
                sid = str(state.get("session_id", ""))[:30]
                logger.exception("RiskRoundResult 解析失败: session=%s", sid)
                risk_round = RiskRoundResult()
        else:
            risk_round = RiskRoundResult()

        risk_summary = _format_risk_round_for_pm(risk_round)

        # 读取策略师分析
        analyses_raw = state.get("analyses", {})
        strategy_text = _format_strategy_analyses_for_risk(analyses_raw)

        # 读取分析师报告
        ar_raw = state.get("analyst_reports", {})
        analyst_text = _format_analyst_reports_for_risk(ar_raw)

        prompt_parts: list[str] = []
        if analyst_text:
            prompt_parts.append(f"## 分析师报告\n{analyst_text}")
        if strategy_text:
            prompt_parts.append(f"## 策略师分析\n{strategy_text}")
        prompt_parts.append(f"## 辩论共识\n{vote_summary_text}")
        prompt_parts.append(f"## 三层风控审核\n{risk_summary}")

        prompt_parts.append(
            "\n## 你的任务\n"
            "作为 Portfolio Manager（投资组合经理），请综合以上所有信息，"
            "做出最终交易决策。你的输出是整条分析链路的最终产品。\n\n"
            "**决策框架：**\n"
            "- 如果三位风控官中有 2 位或以上认为应该「buy」且无严重纪律违规 → 批准买入\n"
            "- 如果多数风控官认为「sell」或有严重纪律违规 → 建议卖出/观望\n"
            "- 如果风控官意见分歧严重 → 建议「hold」并等待更多信息\n"
            "- 仓位大小取保守型和中型型建议的中间值（激进型仅作参考上限）\n\n"
            "请输出以下字段：\n"
            "1. action: 最终操作建议（buy/sell/hold）\n"
            "2. position_size_pct: 最终仓位比例（0.0–1.0）\n"
            "3. stop_loss_pct: 最终止损比例\n"
            "4. take_profit_pct: 最终止盈比例\n"
            "5. reasoning: 综合决策理由（300–500字，包含对三方风控意见的综合考量）\n"
            "6. risk_level: 最终风险等级\n"
            "7. confidence: 决策置信度（0.0–1.0）\n"
            "8. key_warnings: 关键风险警告列表\n"
            "9. risk_consensus: 风控共识描述（一句话概括三方风控官的意见）\n"
            "10. risk_officers_summary: 三位风控官简易概览\n"
            "11. discipline_checks_passed: 是否通过全部交易纪律检查\n"
            "12. discipline_summary: 交易纪律检查摘要\n"
        )

        prompt = "\n\n".join(prompt_parts)

        system_prompt = (
            "你是一位经验丰富的 Portfolio Manager（投资组合经理）。\n"
            "你的职责是综合分析师、策略师、辩论评审和风控审核的所有信息，"
            "做出最终的投资决策。你不是简单地「投票」，而是要综合各方观点，"
            "提出有依据、可执行的交易建议。\n\n"
            "**你的决策哲学**：\n"
            "- 体系大于天才：依赖流程而非个人直觉\n"
            "- 风控优先：宁可错过不可做错\n"
            "- 纪律底线：任何违反交易纪律的交易都需特别标注\n"
        )

        try:
            raw = cast(TradeRecommendation, await llm_service.invoke_structured(
                prompt=prompt,
                output_model=TradeRecommendation,
                system_prompt=system_prompt,
                agent_name="portfolio_manager",
                session_id=sid,
            ))

            elapsed = (time.monotonic() - start) * 1000

            return {
                node_name_output: TradeRecommendation(
                    action=raw.action or "hold",
                    position_size_pct=max(0.0, min(1.0, raw.position_size_pct)),
                    stop_loss_pct=max(0.0, min(1.0, raw.stop_loss_pct)),
                    take_profit_pct=max(0.0, min(1.0, raw.take_profit_pct)),
                    reasoning=raw.reasoning,
                    risk_level=raw.risk_level or "中等风险",
                    confidence=max(0.0, min(1.0, raw.confidence)),
                    key_warnings=list(raw.key_warnings),
                    risk_consensus=raw.risk_consensus,
                    risk_officers_summary=raw.risk_officers_summary,
                    discipline_checks_passed=raw.discipline_checks_passed,
                    discipline_summary=raw.discipline_summary,
                    latency_ms=round(elapsed, 0),
                ).model_dump(),
            }

        except Exception:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception("PM 裁决失败: session=%s", state.get("session_id", ""))
            return {
                node_name_output: TradeRecommendation(
                    action="hold",
                    reasoning="PM 裁决失败，默认保守观望",
                    latency_ms=round(elapsed, 0),
                ).model_dump(),
            }

    return pm_round_node


# ── 辅助：格式化 state 数据为可读文本 ────────────────────────────


def _format_vote_summary_for_risk(vs_raw: dict) -> str:
    """将 vote_summary dict 格式化为风控官可读的文本"""
    if not vs_raw or not isinstance(vs_raw, dict):
        return "暂无辩论汇总数据"

    parts: list[str] = []
    if vs_raw.get("consensus"):
        parts.append(f"共识评级: {vs_raw['consensus']}")
    if vs_raw.get("average_score"):
        parts.append(f"平均分: {vs_raw['average_score']:.1f}")
    if vs_raw.get("confidence"):
        parts.append(f"共识置信度: {vs_raw['confidence']:.2f}")

    rating_dist = vs_raw.get("rating_distribution", {})
    if rating_dist:
        dist_text = ", ".join(f"{k}: {v}票" for k, v in rating_dist.items())
        parts.append(f"评级分布: {dist_text}")

    direction_dist = vs_raw.get("direction_distribution", {})
    if direction_dist:
        dir_text = ", ".join(f"{k}: {v}" for k, v in direction_dist.items())
        parts.append(f"方向分布: {dir_text}")

    # D4 字段
    if vs_raw.get("review_score"):
        parts.append(f"独立评审评分: {vs_raw['review_score']}")
    if vs_raw.get("consensus_support"):
        parts.append(f"共识支持度: {vs_raw['consensus_support']}")

    return "\n".join(parts) if parts else "暂无辩论汇总数据"


def _format_strategy_analyses_for_risk(analyses_raw: dict) -> str:
    """将策略师分析 dict 格式化为风控官可读的文本"""
    if not analyses_raw or not isinstance(analyses_raw, dict):
        return ""

    parts: list[str] = []
    for name, analysis in analyses_raw.items():
        if not isinstance(analysis, dict):
            continue
        if not analysis.get("success", False):
            continue

        agent_name = analysis.get("skill_name", name)
        direction = analysis.get("direction", "Neutral")
        rating = analysis.get("rating", "")
        score = analysis.get("score", 0)
        summary = analysis.get("summary", "")

        text = f"**{agent_name}** ({direction}, {rating}, {score}分)"
        if summary:
            text += f"\n  {summary[:200]}"
        parts.append(text)

    return "\n\n".join(parts) if parts else ""


def _format_analyst_reports_for_risk(ar_raw: dict) -> str:
    """将分析师报告 dict 格式化为风控官可读的文本"""
    if not ar_raw or not isinstance(ar_raw, dict):
        return ""

    parts: list[str] = []
    for key, report in ar_raw.items():
        if not isinstance(report, dict):
            continue
        analyst_type = report.get("analyst_type", key)
        findings = report.get("key_findings", [])
        red_flags = report.get("red_flags", [])
        direction = report.get("direction_hint", "")
        confidence = report.get("confidence", 0.0)
        score = report.get("score", 0)

        text = f"**{analyst_type}** ({direction}, 置信度: {confidence:.0%}, 评分: {score})"
        if findings:
            finding_text = "; ".join(str(f) for f in findings[:3])
            text += f"\n  发现: {finding_text}"
        if red_flags:
            flag_text = "; ".join(str(f) for f in red_flags[:3])
            text += f"\n  ⚠️ 红旗: {flag_text}"
        parts.append(text)

    return "\n\n".join(parts) if parts else ""


def _format_risk_round_for_pm(risk_round: RiskRoundResult) -> str:
    """将风控审核结果格式化为 PM 可读的文本"""
    if not risk_round.assessments:
        return "暂无风控审核数据"

    parts: list[str] = [
        f"## 风控共识\n"
        f"- 共识操作: {risk_round.risk_consensus_action}\n"
        f"- 平均风险评分: {risk_round.avg_risk_score}/100\n"
        f"- 仓位范围: {risk_round.min_position_pct:.0%} ~ {risk_round.max_position_pct:.0%}\n"
        f"- 纪律违规总数: {risk_round.total_discipline_violations}\n",
    ]

    parts.append("## 各风控官意见\n")
    for key, assessment in risk_round.assessments.items():
        if not assessment.success:
            parts.append(f"### {assessment.risk_style_label}\n❌ 分析失败: {assessment.error}\n")
            continue

        violations_text = ""
        if assessment.discipline_violations:
            violations_text = (
                "\n  ⚠️ 纪律违规: " + "; ".join(assessment.discipline_violations)
            )

        parts.append(
            f"### {assessment.risk_style_label}\n"
            f"- 建议: {assessment.action.upper()} | "
            f"仓位: {assessment.position_size_pct:.0%} | "
            f"止损: {assessment.stop_loss_pct:.0%} | "
            f"止盈: {assessment.take_profit_pct:.0%}\n"
            f"- 风险评分: {assessment.risk_score}/100 ({assessment.risk_rating})\n"
            f"- 置信度: {assessment.confidence:.0%}{violations_text}\n"
            f"- 关键风险: {'; '.join(assessment.key_risks[:3]) if assessment.key_risks else '无'}\n"
            f"- 分析: {assessment.analysis[:200]}...\n"
        )

    return "\n".join(parts)

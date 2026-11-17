"""单个参与者的执行函数：分析师、策略师、同侪复核、独立评审。

自 orchestrator.py 拆出，逻辑未改。
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import cast

from src.agents.base import AgentContext
from src.agents.master_agent import MasterAgent
from src.data.research_policy import MARKET_RESEARCH_PROMPT
from src.debate.analysts import AnalystPersona
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    IndependentReview,
    RebuttalAnalysis,
)
from src.memory.skill_disk import MasterSkill
from src.memory.store import MemoryItem
from src.utils.llm import llm_service

logger = logging.getLogger("src.debate.orchestrator")


def _format_history_context(items: list[MemoryItem], stock_code: str) -> str:
    """将历史决策记忆格式化为 prompt 插入文本

    从 MemoryStore 查询到的历史决策条目格式化成可读的上下文，
    注入到大师 prompt 末尾，帮助大师参考历史分析记录。

    Args:
        items: 历史决策 MemoryItem 列表
        stock_code: 当前股票代码

    Returns:
        格式化后的历史上下文文本（无相关记录时返回 ""）
    """
    if not items:
        return ""

    # 过滤与当前股票相关的历史决策，取最近的 5 条
    relevant = []
    for item in items:
        val = item.value if isinstance(item.value, dict) else {}
        if val.get("stock_code") == stock_code:
            relevant.append(val)

    if not relevant:
        return ""

    lines = ["", "📜 历史决策参考：", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append("以下是本系统对该股票的历史分析记录（仅供参考，独立判断应基于当前市场数据）：")
    lines.append("")

    for i, decision in enumerate(reversed(relevant[-5:]), 1):
        ts = str(decision.get("timestamp", "未知日期"))[:10]
        lines.append(f"──── 历史决策 #{i}（{ts}）────")
        lines.append(f"  问题：{decision.get('question', '未知')}")
        lines.append(f"  共识：{decision.get('consensus', '未知')}")
        lines.append(f"  平均评分：{decision.get('average_score', 'N/A')}")
        lines.append(f"  置信度：{decision.get('confidence', 'N/A')}")
        lines.append(f"  参与大师数：{decision.get('total_votes', 0)}")

        analyses = decision.get("analyses_summary", [])
        if analyses:
            lines.append("  大师观点：")
            for a in analyses:
                summary_snippet = (a.get("summary", "") or "")[:80]
                direction_str = a.get("direction", "")
                dir_tag = f" [{direction_str}]" if direction_str else ""
                if summary_snippet:
                    lines.append(
                        f"    · {a.get('skill_name', '未知')}："
                        f"{a.get('rating', '')}{dir_tag} — "
                        f"{a.get('score', 0)}分 — {summary_snippet}"
                    )
                else:
                    lines.append(
                        f"    · {a.get('skill_name', '未知')}："
                        f"{a.get('rating', '')}{dir_tag} — "
                        f"{a.get('score', 0)}分"
                    )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _format_analyst_reports(reports: dict[str, AnalystReport]) -> str:
    """将分析师报告格式化为 prompt 插入文本

    供 _run_single_master 使用，将分析师层的结构化报告转换为
    策略师（大师）阅读的专业报告格式。

    Args:
        reports: analyst_type → AnalystReport 的映射（如 "analyst.fundamental" → report）

    Returns:
        格式化后的分析师报告文本（无报告时返回 ""）
    """
    if not reports:
        return ""

    lines = ["", "📋 分析师专题报告：", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    for key, report in reports.items():
        # 从 key 提取类型（如 "analyst.fundamental" → "fundamental"）
        atype = key.replace("analyst.", "")
        lines.append(f"\n▶ {atype}——{report.analyst_type}")
        lines.append(
            f"  评分：{report.score}/100"
            f" | 方向：{report.direction_hint}"
            f" | 置信度：{report.confidence:.0%}"
        )
        lines.append(f"  摘要：{report.summary}")
        if report.key_findings:
            lines.append("  关键发现：")
            for f in report.key_findings:
                lines.append(f"    · {f}")
        if report.data_evidence:
            lines.append("  数据支撑：")
            for e in report.data_evidence:
                lines.append(f"    · {e}")
        if report.red_flags:
            lines.append("  风险信号：")
            for rf in report.red_flags:
                lines.append(f"    ⚠ {rf}")
        lines.append("")

    return "\n".join(lines)


async def _run_single_analyst(
    persona: AnalystPersona,
    session_id: str,
    question: str,
    stock_code: str,
    stock_name: str,
    market_data: dict,
) -> AnalystReport:
    """运行一位分析师，返回 AnalystReport

    与 _run_single_master 不同，分析师直接调用 LLM（无 MasterAgent 封装），
    是专业领域的结构化输出工具。失败时返回默认 AnalystReport（不中断流程）。

    Args:
        persona: 分析师人格（定义专注领域和方法论）
        session_id: 会话标识
        question: 分析问题
        stock_code: 股票代码
        stock_name: 股票名称
        market_data: 市场数据缓存

    Returns:
        结构化分析报告
    """
    start = time.monotonic()

    # 构建分析 prompt（全量数据 + 专注提示）
    enhanced = question
    brief = market_data.get("brief", "")
    if brief:
        enhanced += f"\n\n📊 以下为当前市场数据：\n{brief}"

    try:
        raw = cast(AnalystReport, await llm_service.invoke_structured(
            prompt=enhanced,
            output_model=AnalystReport,
            system_prompt=persona.system_prompt + "\n" + MARKET_RESEARCH_PROMPT,
            agent_name=f"analyst.{persona.analyst_type}",
            session_id=session_id,
        ))
        elapsed = (time.monotonic() - start) * 1000

        return AnalystReport(
            analyst_type=persona.analyst_type,
            key_findings=list(raw.key_findings),
            data_evidence=list(raw.data_evidence),
            red_flags=list(raw.red_flags),
            confidence=raw.confidence,
            summary=raw.summary,
            score=raw.score,
            direction_hint=(
                raw.direction_hint
                if raw.direction_hint in ("Bullish", "Bearish", "Neutral")
                else "Neutral"
            ),
            latency_ms=round(elapsed, 0),
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return AnalystReport(
            analyst_type=persona.analyst_type,
            summary=f"分析失败: {str(e)[:100]}",
            latency_ms=round(elapsed, 0),
        )


async def _run_single_master(
    skill: MasterSkill,
    session_id: str,
    question: str,
    stock_code: str,
    stock_name: str,
    market_data: dict,
    history_context: str = "",
    reflection_context: str = "",
    analyst_reports: dict[str, AnalystReport] | None = None,
) -> AgentAnalysis:
    """运行一位大师的策略分析，返回 AgentAnalysis

    大师现在作为「策略师」角色——基于分析师层的专业报告进行综合判断，
    而非直接从原始数据分析。大师的投资哲学用于解读专家报告并形成最终决策。

    Args:
        skill: 大师 Skill
        session_id: 会话标识
        question: 分析问题
        stock_code: 股票代码
        stock_name: 股票名称
        market_data: 市场数据缓存
        history_context: 历史决策上下文（注入到 prompt 末尾）
        analyst_reports: 分析师层产出的结构化报告（策略师的核心输入）

    Returns:
        结构化分析结果
    """
    start = time.monotonic()

    # 构建策略合成 prompt
    # 策略师的核心输入是分析师报告，市场数据作为辅助上下文
    enhanced = question

    # 1. 分析师报告（策略师的主要输入）
    if analyst_reports:
        reports_text = _format_analyst_reports(analyst_reports)
        enhanced += f"\n{reports_text}"

    # 2. 市场数据（辅助上下文）
    brief = market_data.get("brief", "")
    if brief:
        enhanced += f"\n\n📊 当前市场数据（辅助参考）：\n{brief}"

    # 3. 战略合成指示（角色转换关键）
    if analyst_reports:
        enhanced += (
            "\n\n【战略合成指示】\n"
            "你正在审阅上述专业分析师团队的报告。"
            "请运用你的投资哲学对这些专家分析进行综合评判，"
            "形成你自己的最终判断。\n"
            "注意：分析师报告可能存在分歧或盲区。"
            "你的角色不是重新分析原始数据，"
            "而是运用经验和智慧对不同维度的专业分析做出综合裁决。"
        )

    # 4. 历史决策上下文
    if history_context:
        enhanced += f"\n\n{history_context}"

    # 5. M2 反思上下文（从过去的错误中学习）
    if reflection_context:
        enhanced += f"\n\n{reflection_context}"

    try:
        agent = MasterAgent(
            skill=skill,
            name=f"master.{skill.skill_id}",
        )
        ctx = AgentContext(
            session_id=session_id,
            input_data={
                "question": enhanced,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market_data": market_data,
            },
            current_round=1,
            target_audience="debate_group",
        )
        result = await agent.run_safe(ctx)

        if not result.success:
            elapsed = (time.monotonic() - start) * 1000
            return AgentAnalysis(
                agent_name=f"master.{skill.skill_id}",
                skill_id=skill.skill_id,
                skill_name=skill.name,
                rating="中性",
                score=0,
                summary="",
                analysis="",
                key_evidence=[],
                confidence=0.0,
                success=False,
                error=result.error or "分析失败",
                latency_ms=elapsed,
            )

        # 从 AgentResult 提取结构化分析
        data = result.data if isinstance(result.data, dict) else {}
        analysis_raw = data.get("analysis", {})
        if isinstance(analysis_raw, dict):
            rating = analysis_raw.get("rating", "中性")
            score = analysis_raw.get("score", 50)
            summary = analysis_raw.get("summary", "")
            analysis_text = analysis_raw.get("analysis", "")
            key_evidence = analysis_raw.get("key_evidence", [])
            risk_warning = analysis_raw.get("risk_warning")
            direction = analysis_raw.get("direction", "Neutral")
        else:
            rating, score, summary, analysis_text, key_evidence, risk_warning = (
                "中性", 50, "", "", [], None
            )
            direction = "Neutral"

        # 方向值规范化
        if direction not in ("Bullish", "Bearish", "Neutral"):
            direction = "Neutral"

        elapsed = (time.monotonic() - start) * 1000
        return AgentAnalysis(
            agent_name=f"master.{skill.skill_id}",
            skill_id=skill.skill_id,
            skill_name=skill.name,
            rating=rating,
            score=score,
            summary=summary,
            analysis=analysis_text,
            key_evidence=list(key_evidence),
            risk_warning=risk_warning,
            research_generated_at=datetime.now(UTC),
            horizons=analysis_raw.get("horizons", []) if isinstance(analysis_raw, dict) else [],
            confidence=result.confidence,
            latency_ms=elapsed,
            direction=direction,
        )

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return AgentAnalysis(
            agent_name=f"master.{skill.skill_id}",
            skill_id=skill.skill_id,
            skill_name=skill.name,
            rating="中性",
            score=0,
            summary="",
            analysis="",
            key_evidence=[],
            confidence=0.0,
            success=False,
            error=str(e),
            latency_ms=elapsed,
        )


async def _run_review_for_master(
    skill: MasterSkill,
    session_id: str,
    question: str,
    own_analysis: AgentAnalysis,
    peer_analyses: list[AgentAnalysis],
    market_data: dict,
    history_context: str = "",
    reflection_context: str = "",
) -> RebuttalAnalysis:
    """运行一位大师的第二轮交叉审阅 —— 回应同行分析

    构建包含大师自身分析 + 所有同行分析的上下文，调用 LLM 生成 RebuttalAnalysis。
    失败时返回默认 RebuttalAnalysis（不中断流程）。

    Args:
        skill: 大师 Skill（用于 system_prompt）
        own_analysis: 该大师的第一轮分析结果
        peer_analyses: 其他大师的分析列表
        market_data: 市场数据缓存
        history_context: 历史决策上下文（注入到 review prompt）

    Returns:
        结构化反驳/补充意见
    """
    start = time.monotonic()
    try:
        # 构建同行分析摘要
        peers_text = ""
        for i, peer in enumerate(peer_analyses, 1):
            peers_text += (
                f"\n--- 同行 {i}：{peer.skill_name}（{peer.agent_name}）---\n"
                f"评级：{peer.rating}（评分：{peer.score}）\n"
                f"方向：{peer.direction}\n"
                f"核心观点：{peer.summary}\n"
                f"分析：{peer.analysis[:500]}\n"
                f"关键证据：{'; '.join(peer.key_evidence)}\n"
            )
            if peer.risk_warning:
                peers_text += f"风险提示：{peer.risk_warning}\n"

        # 构建审阅 prompt
        brief = market_data.get("brief", "")
        review_prompt = (
            f"你之前对「{question}」的分析如下：\n"
            f"---\n"
            f"评级：{own_analysis.rating}（评分：{own_analysis.score}）\n"
            f"核心观点：{own_analysis.summary}\n"
            f"你的分析：{own_analysis.analysis[:500]}\n"
            f"关键证据：{'; '.join(own_analysis.key_evidence)}\n"
        )
        if own_analysis.risk_warning:
            review_prompt += f"你的风险提示：{own_analysis.risk_warning}\n"

        if peers_text:
            review_prompt += (
                f"\n现在你看到了其他大师的分析："
                f"{peers_text}\n"
            )

        if brief:
            review_prompt += f"\n📊 市场背景：\n{brief}\n"
        if history_context:
            review_prompt += f"\n{history_context}\n"
        if reflection_context:
            review_prompt += f"\n{reflection_context}\n"

        review_prompt += (
            "\n请基于以上所有信息，重新审视你的原始判断。请以三段式格式输出回应：\n"
            "1. 你对同行观点的共识度（0.0 完全不同意 - 1.0 完全同意）\n"
            "2. **赞同**：你认可同行的哪些观点？\n"
            "3. **补充**：你有什么额外信息、数据或分析角度要补充？\n"
            "4. **异议**：你不认同同行的哪些观点？理由是什么？\n"
            "5. 调整后的评级（看涨/看跌/中性/谨慎/观望，或留空表示不变）\n"
            "6. 调整后的评分（1-100，或 0 表示不变）\n"
            "7. 调整后的置信度（0.0-1.0，或 0.0 表示不变）\n"
            "8. 关键要点\n"
            "9. 受哪位同行影响的说明\n"
        )

        system_prompt = skill.system_prompt + (
            "\n\n你现在正在参与一场投资辩论的第二轮——"
            "你看到了其他大师对你的分析，请基于同行的观点给出你的回应。"
            "请从「赞同」「补充」「异议」三个角度分别阐述。"
            "你可以坚持原有判断，也可以调整。关键是要给出有逻辑支撑的理由。"
        )

        raw = cast(RebuttalAnalysis, await llm_service.invoke_structured(
            prompt=review_prompt,
            output_model=RebuttalAnalysis,
            system_prompt=system_prompt + "\n" + MARKET_RESEARCH_PROMPT,
            agent_name=f"master.{skill.skill_id}",
            session_id=session_id,
        ))
        elapsed = (time.monotonic() - start) * 1000
        # invoke_structured 返回的是已验证的 RebuttalAnalysis 实例，直接使用
        return RebuttalAnalysis(
            agent_name=f"master.{skill.skill_id}",
            original_agreement=raw.original_agreement,
            agreement=raw.agreement,
            supplement=raw.supplement,
            objection=raw.objection,
            adjusted_rating=raw.adjusted_rating,
            adjusted_score=raw.adjusted_score,
            adjusted_confidence=raw.adjusted_confidence,
            key_counterpoints=raw.key_counterpoints,
            peer_influences=raw.peer_influences,
            latency_ms=round(elapsed, 0),
        )

    except Exception:
        logger.exception("RebuttalAnalysis 生成失败: agent=master.%s", skill.skill_id)
        # 失败时返回默认值，不阻塞流程
        return RebuttalAnalysis(
            agent_name=f"master.{skill.skill_id}",
        )


async def _run_independent_review(
    session_id: str,
    question: str,
    successful_analyses: list[AgentAnalysis],
    rebuttals: list[RebuttalAnalysis],
    market_data: dict,
    history_context: str = "",
    reflection_context: str = "",
) -> IndependentReview:
    """运行独立评审 Agent —— 以裁判视角评估所有大师的分析质量

    读取所有大师的分析和（可选的）第二轮反驳，由独立的 LLM 评审人格
    对辩论整体质量、分析一致性、集体偏差等做出结构化评估。
    失败时返回默认 IndependentReview（不中断流程）。

    Args:
        session_id: 会话标识
        question: 辩论问题
        successful_analyses: 所有成功大师的分析
        rebuttals: 第二轮交叉审阅的反驳列表（可能为空）
        market_data: 市场数据缓存
        history_context: 历史决策上下文（注入到评审 prompt）

    Returns:
        结构化评审报告
    """
    start = time.monotonic()
    try:
        # 构建大师分析摘要
        analyses_text = ""
        for i, a in enumerate(successful_analyses, 1):
            analyses_text += (
                f"\n--- 大师 {i}：{a.skill_name}（{a.agent_name}）---\n"
                f"评级：{a.rating}（评分：{a.score}）\n"
                f"方向：{a.direction}\n"
                f"核心观点：{a.summary}\n"
                f"分析：{a.analysis[:600]}\n"
                f"关键证据：{'; '.join(a.key_evidence)}\n"
                f"置信度：{a.confidence}\n"
            )
            if a.risk_warning:
                analyses_text += f"风险提示：{a.risk_warning}\n"

        # 构建同行互评摘要（赞同+补充+异议三段式）
        rebuttals_text = ""
        if rebuttals:
            rebuttals_text = "\n--- 第二轮交叉审阅（大师同行互评）---\n"
            for i, r in enumerate(rebuttals, 1):
                rebuttals_text += f"  {i}. {r.agent_name}（共识度 {r.original_agreement}）:\n"
                if r.agreement:
                    rebuttals_text += f"     ✅ 赞同：{r.agreement[:200]}\n"
                if r.supplement:
                    rebuttals_text += f"     📌 补充：{r.supplement[:200]}\n"
                if r.objection:
                    rebuttals_text += f"     ❌ 异议：{r.objection[:200]}\n"
                if r.adjusted_score is not None:
                    rebuttals_text += f"     调整后评分：{r.adjusted_score}\n"

        # 构建评审 prompt
        brief = market_data.get("brief", "")
        review_prompt = (
            f"你是一位独立的投资评审专家。请对以下关于「{question}」的投资辩论进行评审。\n\n"
            f"--- 大师分析 ---"
            f"{analyses_text}\n"
        )
        if rebuttals_text:
            review_prompt += f"{rebuttals_text}\n"
        if brief:
            review_prompt += f"\n📊 市场背景：\n{brief}\n"
        if history_context:
            review_prompt += f"\n{history_context}\n"
        if reflection_context:
            review_prompt += f"\n{reflection_context}\n"

        review_prompt += (
            "\n请以独立裁判的视角评审这场辩论，输出结构化评审报告：\n"
            "1. overall_quality: 辩论整体质量（0.0-1.0）\n"
            "2. independent_rating: 基于全部信息的独立评级（看涨/看跌/中性/谨慎/观望）\n"
            "3. independent_score: 独立评分（1-100）\n"
            "4. confidence: 对你评审结论的置信度（0.0-1.0）\n"
            "5. consensus_support: 你是否支持当前共识？0.0=强烈反对, 1.0=强烈支持\n"
            "6. quality_assessments: 对每位大师分析质量的评估\n"
            "7. weight_suggestions: 对每位大师的权重调整建议（乘数，0.0-2.0。"
            "1.0=不变，<1.0=降低权重，>1.0=提高权重）\n"
            "8. identified_biases: 你发现的所有大师共有的集体偏见\n"
            "9. blind_spots: 所有分析中缺失的关键视角\n"
            "10. key_risks_synthesis: 关键风险综合\n"
            "11. consistency_observation: 分析间一致性的观察\n"
            "12. aggregation_recommendation: 对聚合方式的建议\n"
        )

        system_prompt = (
            "你是一位冷静、客观的投资评审专家。你的职责是独立评估辩论质量，"
            "不受任何大师立场影响。如果发现集体偏见或盲点，请明确指出。"
            "你的评审将对最终投票聚合产生直接影响。"
        )
        if market_data.get("instrument_type") == "etf":
            from src.debate.etf_analysts import ETF_SCOPE_PROMPT

            system_prompt += "\n" + ETF_SCOPE_PROMPT

        raw = cast(IndependentReview, await llm_service.invoke_structured(
            prompt=review_prompt,
            output_model=IndependentReview,
            system_prompt=system_prompt + "\n" + MARKET_RESEARCH_PROMPT,
            agent_name="independent_reviewer",
            session_id=session_id,
        ))
        elapsed = (time.monotonic() - start) * 1000

        return IndependentReview(
            reviewer_style="independent_reviewer",
            overall_quality=raw.overall_quality,
            independent_rating=raw.independent_rating,
            independent_score=raw.independent_score,
            confidence=raw.confidence,
            consensus_support=raw.consensus_support,
            quality_assessments=raw.quality_assessments,
            weight_suggestions=raw.weight_suggestions,
            identified_biases=raw.identified_biases,
            blind_spots=raw.blind_spots,
            key_risks_synthesis=raw.key_risks_synthesis,
            consistency_observation=raw.consistency_observation,
            aggregation_recommendation=raw.aggregation_recommendation,
            latency_ms=round(elapsed, 0),
        )

    except Exception:
        logger.exception("IndependentReview 生成失败: session=%s", session_id)
        # 失败时返回默认值，不阻塞流程
        return IndependentReview()

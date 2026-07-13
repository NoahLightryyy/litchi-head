"""辩论编排器 —— LangGraph StateGraph 驱动多大师顺序分析

核心流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. analyst_round — 4 位专业分析师（基本面/技术面/情绪面/宏观面）
  3. master_round — 策略师基于分析师报告综合判断
  4. review_round — D1 交叉审阅（赞同+补充+异议三段式）
  5. review_report — D3 独立评审
  6. aggregate — 加权投票汇总（D4 评审修正字段）
  8. risk_round（可选） — R1 三层风控审核
  9. trader_round（可选） — T1 交易员执行规划
  10. pm_round（可选） — PM 最终裁决

记忆增强（可选，提供 memory_store 时自动启用）：
  · M1 历史决策注入 — 查询过去决策注入到 prompt
  · M2 反思闭环 — 查询过去反思注入到 prompt（需 enable_reflection=True）

用法：
    orchestrator = DebateOrchestrator()
    result = await orchestrator.run(DebateInput(stock_code="000001"))

    # 启用风控层
    orchestrator = DebateOrchestrator(enable_risk=True)
    result = await orchestrator.run(DebateInput(stock_code="000001"))

    # 启用风控 + 交易员层 + M2 反思
    orchestrator = DebateOrchestrator(
        enable_risk=True, enable_trader=True,
        memory_store=store, enable_reflection=True,
    )
    result = await orchestrator.run(DebateInput(stock_code="000001"))
    print(result.trade_recommendation["action"])

    # 事后反思
    reflection = await orchestrator.reflect_on_decision(
        stock_code="000001",
        outcome=ActualOutcome(
            stock_code="000001",
            price_change_pct=+3.5,
            actual_direction="Bullish",
        ),
    )
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, TypedDict, cast

logger = logging.getLogger(__name__)

from langgraph.graph import END, StateGraph  # noqa: E402 — 惰性导入避免 Windows torch crash

from src.agents.base import AgentContext  # noqa: E402
from src.agents.master_agent import MasterAgent  # noqa: E402
from src.callback import CallbackEventType, ResultCallbackEngine  # noqa: E402
from src.callback.callbacks import register_m3_ext_callback  # noqa: E402
from src.data.collector import DataCollector, format_market_brief  # noqa: E402
from src.data.models import KLine, NewsItem, StockQuote  # noqa: E402
from src.debate.analysts import AnalystPersona, get_default_analysts  # noqa: E402
from src.debate.models import (  # noqa: E402
    AgentAnalysis,
    AnalystReport,
    BiasReport,
    DebateInput,
    DebateResult,
    IndependentReview,
    PeerReviewRound,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.reflection import (  # noqa: E402
    ActualOutcome,
    ReflectionRecord,
    _format_reflection_context,
    _load_decision_from_memory,
    generate_reflection,
)
from src.debate.trust import TrustTracker, compute_weight_factor  # noqa: E402
from src.memory.skill_disk import MasterSkill, SkillDisk  # noqa: E402
from src.memory.store import MemoryItem, MemoryStore  # noqa: E402
from src.utils.llm import llm_service  # noqa: E402

# ── 模块级常量 ─────────────────────────────────────────────

_MAX_HISTORY_FETCH = 20  # 查询历史决策的最大条数

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


# ── 节点函数 ──────────────────────────────────────────────────────


def collect_data_node(state: DebateState, collector: DataCollector) -> dict:
    """数据采集节点 —— 从 DataCollector 获取行情 + K线 + 新闻

    Args:
        state: 当前辩论状态
        collector: DataCollector 实例

    Returns:
        State 更新，写入 market_data
    """
    inp = state.get("debate_input", {})
    code = inp.get("stock_code", "")

    quotes: list[StockQuote] = []
    klines: list[KLine] = []
    news: list[NewsItem] = []

    try:
        quotes = collector.get_realtime_quotes()
    except Exception as e:
        logger.exception("行情数据获取失败: %s", e)

    try:
        klines = collector.get_klines(code, period="daily", start="", end="")
    except Exception as e:
        logger.exception("K线数据获取失败 [%s]: %s", code, e)

    try:
        news = collector.get_news(code)
    except Exception as e:
        logger.exception("新闻数据获取失败 [%s]: %s", code, e)

    # 按个股过滤行情
    target_quote: StockQuote | None = None
    for q in quotes:
        if q.code == code:
            target_quote = q
            break

    # 生成市场简报
    brief = format_market_brief(
        stock_code=code,
        stock_name=inp.get("stock_name", ""),
        quote=target_quote,
        klines=klines,
        news=news,
    )

    return {
        "market_data": {
            "brief": brief,
            "quote": target_quote.model_dump() if target_quote else None,
            "quotes": [q.model_dump() for q in quotes],
            "klines": [k.model_dump() for k in klines],
            "news": [n.model_dump() for n in news],
        },
    }


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
            system_prompt=persona.system_prompt,
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
            system_prompt=system_prompt,
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

        raw = cast(IndependentReview, await llm_service.invoke_structured(
            prompt=review_prompt,
            output_model=IndependentReview,
            system_prompt=system_prompt,
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


def make_analyst_round_node(personas: list[AnalystPersona]):
    """创建分析师轮次节点 —— 顺序运行所有分析师

    每位分析师专注一个数据维度（基本面/技术面/情绪面/宏观面），
    各自产出 AnalystReport。顺序执行以避免 LangGraph 并行写入冲突。
    失败的分析师返回默认空报告，不阻塞后续流程。

    Args:
        personas: 参与分析的分析师人格列表

    Returns:
        异步节点函数 (state) -> dict
    """

    async def analyst_round_node(state: DebateState) -> dict:
        """运行所有分析师的专业分析"""
        inp = state.get("debate_input", {})
        code = inp.get("stock_code", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        stock_name = inp.get("stock_name", "")
        md = state.get("market_data", {})
        sid = state.get("session_id", "")

        all_reports: dict[str, AnalystReport] = {}
        all_errors: list[str] = []

        for persona in personas:
            report = await _run_single_analyst(
                persona=persona,
                session_id=sid,
                question=question,
                stock_code=code,
                stock_name=stock_name,
                market_data=md,
            )
            key = f"analyst.{persona.analyst_type}"
            all_reports[key] = report
            if not report.key_findings and report.score == 0:
                all_errors.append(f"{key} 执行失败或无有效发现")

        return {
            "analyst_reports": all_reports,
            "errors": all_errors,
        }

    return analyst_round_node


def make_master_round_node(skills: list[MasterSkill]):
    """创建大师轮次节点 —— 顺序运行所有大师

    使用顺序而非并行执行，避免 LangGraph 并行写入同一 state key 的冲突。
    每位大师的 Agent.run_safe() 内部自带超时保护，失败不会阻塞后续大师。

    Args:
        skills: 参与辩论的大师列表

    Returns:
        异步节点函数 (state) -> dict
    """

    async def master_round_node(state: DebateState) -> dict:
        """运行所有大师的策略分析（基于分析师报告）"""
        inp = state.get("debate_input", {})
        code = inp.get("stock_code", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        stock_name = inp.get("stock_name", "")
        md = state.get("market_data", {})
        sid = state.get("session_id", "")
        history_ctx = state.get("history_context", "")
        reflection_ctx = state.get("reflection_context", "")
        analyst_reports_raw = state.get("analyst_reports", {})

        # 将 state 中的 dict 转换为 AnalystReport 实例
        analyst_reports: dict[str, AnalystReport] = {}
        if analyst_reports_raw and isinstance(analyst_reports_raw, dict):
            for k, v in analyst_reports_raw.items():
                if isinstance(v, dict):
                    try:
                        analyst_reports[k] = AnalystReport(**v)
                    except Exception as e:
                        logger.warning("分析师报告解析失败 [%s]: %s", k, e)
                elif isinstance(v, AnalystReport):
                    analyst_reports[k] = v

        all_analyses: dict[str, AgentAnalysis] = {}
        all_errors: list[str] = []

        for skill in skills:
            analysis = await _run_single_master(
                skill=skill,
                session_id=sid,
                question=question,
                stock_code=code,
                stock_name=stock_name,
                market_data=md,
                history_context=history_ctx,
                reflection_context=reflection_ctx,
                analyst_reports=analyst_reports,
            )
            key = f"master.{skill.skill_id}"
            all_analyses[key] = analysis
            if not analysis.success:
                all_errors.append(f"{key} 执行失败: {analysis.error}")

        return {
            "analyses": all_analyses,
            "errors": all_errors,
        }

    return master_round_node


def make_review_round_node(skills: list[MasterSkill]):
    """创建第二轮交叉审阅节点 —— 所有大师互相审阅同行分析后产生反驳

    在 master_round 之后、aggregate 之前运行。每位成功的大师看到所有同行
    的原始分析，然后给出针对性反驳或补充。

    失败的大师不参与审阅。仅有一位成功大师时返回空（交叉审阅无意义）。

    Args:
        skills: 参与辩论的大师列表

    Returns:
        异步节点函数 (state) -> dict
    """

    async def review_round_node(state: DebateState) -> dict:
        """运行所有成功大师的交叉审阅"""
        all_analyses: dict[str, AgentAnalysis] = state.get("analyses", {})
        successful = [a for a in all_analyses.values() if a.success]

        # 少于 2 位成功大师时，交叉审阅无意义
        if len(successful) < 2:
            return {"review_round": PeerReviewRound(rebuttals=[]).model_dump()}

        # 构建 agent_name → skill 的映射
        skill_map: dict[str, MasterSkill] = {}
        for s in skills:
            skill_map[f"master.{s.skill_id}"] = s

        inp = state.get("debate_input", {})
        sid = state.get("session_id", "")
        history_ctx = state.get("history_context", "")
        reflection_ctx = state.get("reflection_context", "")

        rebuttals: list[RebuttalAnalysis] = []
        for analysis in successful:
            agent_name = analysis.agent_name
            skill = skill_map.get(agent_name)
            if skill is None:
                continue

            peers = [a for a in successful if a.agent_name != agent_name]

            rebuttal = await _run_review_for_master(
                skill=skill,
                session_id=sid,
                question=inp.get("question", ""),
                own_analysis=analysis,
                peer_analyses=peers,
                market_data=state.get("market_data", {}),
                history_context=history_ctx,
                reflection_context=reflection_ctx,
            )
            rebuttals.append(rebuttal)

        return {"review_round": PeerReviewRound(rebuttals=rebuttals).model_dump()}

    return review_round_node


def make_review_report_node():
    """创建独立评审节点 —— 以裁判视角评估所有大师的分析质量

    在 master_round（+ review_round）之后运行。读取所有成功大师的分析和
    第二轮反驳，由独立的 LLM 评审人格生成结构化评审报告。
    失败/无成功大师时返回空评审（不中断流程）。

    Returns:
        异步节点函数 (state) -> dict
    """

    async def review_report_node(state: DebateState) -> dict:
        """运行独立评审，评估辩论整体质量"""
        all_analyses: dict[str, AgentAnalysis] = state.get("analyses", {})
        successful = [a for a in all_analyses.values() if a.success]

        # 无成功大师时，返回空评审
        if not successful:
            return {"review_report": IndependentReview(
                overall_quality=0.0,
                independent_score=0,
            ).model_dump()}

        # 解析 review_round（如果有）
        rr_raw = state.get("review_round", {})
        rebuttals: list[RebuttalAnalysis] = []
        if rr_raw and isinstance(rr_raw, dict):
            try:
                prr = PeerReviewRound(**rr_raw)
                rebuttals = prr.rebuttals
            except Exception as e:
                logger.warning("PeerReviewRound 解析失败: %s", e)

        inp = state.get("debate_input", {})
        sid = state.get("session_id", "")
        history_ctx = state.get("history_context", "")
        reflection_ctx = state.get("reflection_context", "")

        review = await _run_independent_review(
            session_id=sid,
            question=inp.get("question", ""),
            successful_analyses=successful,
            rebuttals=rebuttals,
            market_data=state.get("market_data", {}),
            history_context=history_ctx,
            reflection_context=reflection_ctx,
        )

        return {"review_report": review.model_dump()}

    return review_report_node


def compute_bias_report(direction_distribution: dict[str, int]) -> BiasReport:
    """从方向分布计算偏斜报告

    Args:
        direction_distribution: {"Bullish": int, "Bearish": int, "Neutral": int}

    Returns:
        计算后的 BiasReport

    Note:
        纯计算函数，当 total == 0 时返回默认 BiasReport。
    """
    bullish = direction_distribution.get("Bullish", 0)
    bearish = direction_distribution.get("Bearish", 0)
    neutral = direction_distribution.get("Neutral", 0)
    total = bullish + bearish + neutral

    if total == 0:
        return BiasReport()

    bullish_r = round(bullish / total, 4)
    bearish_r = round(bearish / total, 4)
    neutral_r = round(neutral / total, 4)
    overall_bias = round((bullish - bearish) / total, 4)
    consensus_strength = round(max(bullish, bearish, neutral) / total, 4)

    # ── 共识类型判定 ──
    if max(bullish, bearish, neutral) / total > 0.5:
        if bullish > bearish and bullish > neutral:
            consensus_type = "Bullish"
        elif bearish > bullish and bearish > neutral:
            consensus_type = "Bearish"
        else:
            consensus_type = "Neutral"
    else:
        consensus_type = "Divided"

    return BiasReport(
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        total_count=total,
        bullish_ratio=bullish_r,
        bearish_ratio=bearish_r,
        neutral_ratio=neutral_r,
        overall_bias=overall_bias,
        consensus_strength=consensus_strength,
        consensus_type=consensus_type,
    )


async def aggregate_node(state: DebateState) -> dict:
    """投票聚合节点 —— 汇总所有大师分析

    从 state 读取 analyses，如果存在 review_round 则吸收反驳调整：
    - 有反驳的大师使用 adjusted_score / adjusted_rating / adjusted_confidence
    - 无反驳的大师使用原始值
    - 计算评级分布、平均分、加权分、共识评级

    Args:
        state: 当前辩论状态

    Returns:
        State 更新，写入 vote_summary
    """
    all_analyses: dict[str, AgentAnalysis] = state.get("analyses", {})
    successful = [a for a in all_analyses.values() if a.success]

    if not successful:
        return {
            "vote_summary": VoteSummary(
                total_votes=0,
                rating_distribution={},
                average_score=0.0,
                weighted_score=0.0,
                consensus="中性",
                confidence=0.0,
            )
        }

    # 解析 review_round（如果有）
    rr_raw = state.get("review_round", {})
    rebuttal_map: dict[str, RebuttalAnalysis] = {}
    if rr_raw and isinstance(rr_raw, dict):
        try:
            prr = PeerReviewRound(**rr_raw)
            for r in prr.rebuttals:
                rebuttal_map[r.agent_name] = r
        except Exception as e:
            logger.warning("PeerReviewRound 解析失败(rebuttal_map): %s", e)

    # 解析 review_report（如果有），提取 weight_suggestions
    rrpt_raw = state.get("review_report", {})
    weight_suggestions: dict[str, float] = {}
    if rrpt_raw and isinstance(rrpt_raw, dict) and rrpt_raw.get("weight_suggestions"):
        try:
            review = IndependentReview(**rrpt_raw)
            weight_suggestions = review.weight_suggestions
        except Exception as e:
            logger.warning("IndependentReview 解析失败: %s", e)

    # 评级分布 + 方向分布
    dist: dict[str, int] = {}
    dir_dist: dict[str, int] = {}
    total_score = 0
    weighted_score_sum = 0.0
    total_weight = 0.0

    for a in successful:
        rebuttal = rebuttal_map.get(a.agent_name)

        # 确定使用的评分、评级和置信度
        if rebuttal is not None:
            use_rating = (
                rebuttal.adjusted_rating
                if rebuttal.adjusted_rating is not None else a.rating
            )
            use_score = (
                rebuttal.adjusted_score
                if rebuttal.adjusted_score is not None else a.score
            )
            use_confidence = (
                rebuttal.adjusted_confidence if rebuttal.adjusted_confidence is not None
                else a.confidence
            )
        else:
            use_rating = a.rating
            use_score = a.score
            use_confidence = a.confidence

        # 应用 weight_suggestion（如果有）
        weight_factor = weight_suggestions.get(a.agent_name, 1.0)

        # ── M4: 叠加信任度权重因子 ─────────────────
        trust_factors_raw = state.get("trust_weight_factors", {})
        trust_weight_factors: dict[str, float] = {}
        if isinstance(trust_factors_raw, dict):
            trust_weight_factors = trust_factors_raw
        trust_factor = trust_weight_factors.get(a.agent_name, 1.0)
        combined_factor = weight_factor * trust_factor

        dist[use_rating] = dist.get(use_rating, 0) + 1
        dir_dist[a.direction] = dir_dist.get(a.direction, 0) + 1
        total_score += use_score
        weighted_score_sum += use_score * use_confidence * combined_factor
        total_weight += use_confidence * combined_factor

    # ── DP-003: 偏斜公示 ────────────────────────────
    bias_report = compute_bias_report(dir_dist)

    avg_score = total_score / len(successful)
    weighted_score = weighted_score_sum / total_weight if total_weight > 0 else avg_score

    # 共识（众数）
    consensus = max(dist, key=lambda k: dist[k]) if dist else "中性"

    # 置信度：一致性比例 * 0.4 + 平均信心 * 0.6
    max_count = max(dist.values())
    agreement_ratio = max_count / len(successful)
    avg_confidence = total_weight / len(successful)
    confidence = agreement_ratio * 0.4 + avg_confidence * 0.6

    # 检测是否使用了反驳调整（至少有一个大师的 rebuttal 产生了实际调整）
    adjustments_applied = any(
        rebuttal_map.get(a.agent_name) is not None
        for a in successful
    )

    # ── D4: 从 review_report 吸收评审修正字段 ──────────
    rrpt_raw = state.get("review_report", {})
    review_score = 0
    review_rating = ""
    review_quality = 0.0
    weight_adjustments: dict[str, float] = {}
    review_notes_parts: list[str] = []
    consensus_support = 0.5
    if rrpt_raw and isinstance(rrpt_raw, dict):
        try:
            review = IndependentReview(**rrpt_raw)
            review_score = review.independent_score
            review_rating = review.independent_rating
            review_quality = round(review.overall_quality, 2)
            weight_adjustments = review.weight_suggestions

            # 合成评审说明摘要
            if review.consistency_observation:
                review_notes_parts.append(f"一致性: {review.consistency_observation[:100]}")
            if review.key_risks_synthesis:
                review_notes_parts.append(f"风险综合: {review.key_risks_synthesis[:100]}")
            if review.aggregation_recommendation:
                review_notes_parts.append(f"聚合建议: {review.aggregation_recommendation[:100]}")
            if review.identified_biases:
                review_notes_parts.append(
                    f"发现偏差: {'; '.join(review.identified_biases[:3])}"
                )

            consensus_support = review.consensus_support
        except Exception as e:
            logger.warning("IndependentReview 解析失败(默认值): %s", e)

    review_notes = " | ".join(review_notes_parts) if review_notes_parts else ""

    return {
        "vote_summary": VoteSummary(
            total_votes=len(successful),
            rating_distribution=dist,
            average_score=round(avg_score, 1),
            weighted_score=round(weighted_score, 1),
            consensus=consensus,
            confidence=round(min(confidence, 0.95), 2),
            adjustments_applied=adjustments_applied,
            direction_distribution=dir_dist,
            # ── D4: 评审修正字段 ─────────────────────
            review_score=review_score,
            review_rating=review_rating,
            review_quality=review_quality,
            weight_adjustments=weight_adjustments,
            review_notes=review_notes,
            consensus_support=round(consensus_support, 2),
            # ── M4: 信任度权重因子 ───────────────────
            trust_weight_factors=trust_weight_factors,
            bias_report=bias_report,  # ← DP-003 追加
        )
    }


# ── DebateOrchestrator ────────────────────────────────────────────


class DebateOrchestrator:
    """辩论编排器：LangGraph StateGraph 驱动多大师分析

    工作流程：
    1. 接收 DebateInput（股票代码 + 问题）
    2. collect_data 节点采集行情/K线/新闻
    3. analyst_round 节点运行 4 位专业分析师
    4. master_round 节点策略师基于分析师报告综合判断
    5. review_round 节点 D1 交叉审阅
    6. review_report 节点 D3 独立评审
    7. aggregate 节点加权投票汇总
    8. risk_round 节点（可选）R1 三层风控
    9. trader_round 节点（可选）T1 交易员执行规划
    10. pm_round 节点（可选）PM 最终裁决
    11. 返回 DebateResult

    用法：
        orch = DebateOrchestrator()
        result = await orch.run(DebateInput(stock_code="000001"))

        # 启用风控层
        orch = DebateOrchestrator(enable_risk=True)
        result = await orch.run(DebateInput(stock_code="000001"))

        # 启用风控 + 交易员层
        orch = DebateOrchestrator(enable_risk=True, enable_trader=True)
        result = await orch.run(DebateInput(stock_code="000001"))
    """

    def __init__(
        self,
        data_collector: DataCollector | None = None,
        skill_disk: SkillDisk | None = None,
        skill_ids: list[str] | None = None,
        memory_store: MemoryStore | None = None,
        analyst_personas: list[AnalystPersona] | None = None,
        enable_risk: bool = False,
        risk_officers: list | None = None,
        enable_trader: bool = False,
        enable_reflection: bool = False,
        enable_trust: bool = False,
        callback_engine: ResultCallbackEngine | None = None,
    ):
        """初始化辩论编排器

        Args:
            data_collector: 数据采集器，不传则新建
            skill_disk: 大师 Skill 盘，不传则新建
            skill_ids: 参与辩论的大师 ID 列表，None 则使用默认加载的大师
            memory_store: 记忆存储实例（可选）。提供后，
                辩论前自动查询历史决策注入 prompt，辩论后自动保存结果。
            analyst_personas: 分析师人格列表（可选）。
                None 则使用 get_default_analysts() 的 4 位默认分析师。
            enable_risk: 是否启用 R1 三层风控辩论（默认 False）
            risk_officers: 风控官人格列表（可选）。
                None 且 enable_risk=True 时使用 get_default_risk_officers()。
            enable_trader: 是否启用 T1 交易员层（默认 False）
                启用后，交易员将在风控审核后制定多步执行计划，
                PM 将基于风控+交易员方案做出最终裁决。
            enable_reflection: 是否启用 M2 反思注入（默认 False）
                启用后，辩论前自动查询历史反思记忆注入到策略师/评审 prompt。
                需要同时提供 memory_store。
            enable_trust: 是否启用 M4 动态权重（默认 False）
                启用后，aggregate 节点使用 TrustTracker 的 compute_weight_factor()
                自动调整每位大师的投票权重。需要同时提供 memory_store。
            callback_engine: 结果回调引擎（可选）。
                不提供且 enable_trust=True 时自动创建并注册 M3-EXT 回调。
        """
        self.data_collector = data_collector or DataCollector()
        self.skill_disk = skill_disk or SkillDisk()
        self.memory_store = memory_store
        self.analyst_personas = analyst_personas or get_default_analysts()
        self.enable_risk = enable_risk
        self._risk_officers = risk_officers  # None 表示使用默认
        self.enable_trader = enable_trader
        self.enable_reflection = enable_reflection
        self.enable_trust = enable_trust
        self.callback_engine = callback_engine
        if self.callback_engine is None and enable_trust:
            self.callback_engine = ResultCallbackEngine(memory_store=memory_store)
            register_m3_ext_callback(self.callback_engine, memory_store=memory_store)

        # 加载大师列表
        if skill_ids is not None:
            self.master_skills: list[MasterSkill] = []
            for sid in skill_ids:
                try:
                    self.master_skills.append(self.skill_disk.load(sid))
                except KeyError:
                    logger.warning("技能 ID 未找到，已跳过: %s", sid)
        else:
            self.master_skills = self.skill_disk.load_defaults()

        # 缓存编译好的图
        self._compiled_graph: Any = None

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 计算图

        collect_data → analyst_round → master_round → review_round
        → review_report → aggregate → (risk_round → trader_round? → pm_round)? → END

        Returns:
            未编译的 StateGraph
        """
        graph = StateGraph(DebateState)

        # 数据采集节点
        graph.add_node(
            "collect_data",
            lambda state: collect_data_node(state, self.data_collector),  # type: ignore[arg-type]
        )
        graph.set_entry_point("collect_data")

        # 分析师轮次节点：4 位专业分析师（基本面/技术面/情绪面/宏观面）
        graph.add_node(
            "analyst_round",
            make_analyst_round_node(self.analyst_personas),
        )
        graph.add_edge("collect_data", "analyst_round")

        # 大师轮次节点（策略师）：基于分析师报告进行综合判断
        graph.add_node(
            "master_round",
            make_master_round_node(self.master_skills),
        )
        graph.add_edge("analyst_round", "master_round")

        # 第二轮交叉审阅节点：所有大师互相审阅同行分析
        graph.add_node(
            "review_round",
            make_review_round_node(self.master_skills),
        )
        graph.add_edge("master_round", "review_round")

        # 独立评审节点：裁判视角评估所有大师分析质量
        graph.add_node(
            "review_report",
            make_review_report_node(),
        )
        graph.add_edge("review_round", "review_report")

        # 投票聚合节点（吸收反驳调整 + 评审权重建议）
        graph.add_node("aggregate", aggregate_node)
        graph.add_edge("review_report", "aggregate")

        # ── R1: 三层风控 + T1 交易员 + PM 裁决（可选）──────────
        if self.enable_risk:
            from src.risk.orchestrator import (
                make_pm_round_node,
                make_risk_round_node,
            )
            from src.risk.profiles import get_default_risk_officers

            officers = (
                self._risk_officers
                if self._risk_officers is not None
                else get_default_risk_officers()
            )

            graph.add_node(
                "risk_round",
                make_risk_round_node(officers),  # type: ignore[arg-type]
            )
            graph.add_edge("aggregate", "risk_round")

            # T1 交易员层（可选，在风控和 PM 之间）
            if self.enable_trader:
                from src.trader.orchestrator import make_trader_round_node

                graph.add_node(
                    "trader_round",
                    make_trader_round_node(),  # type: ignore[arg-type]
                )
                graph.add_edge("risk_round", "trader_round")

                graph.add_node(
                    "pm_round",
                    make_pm_round_node(),  # type: ignore[arg-type]
                )
                graph.add_edge("trader_round", "pm_round")
            else:
                graph.add_node(
                    "pm_round",
                    make_pm_round_node(),  # type: ignore[arg-type]
                )
                graph.add_edge("risk_round", "pm_round")

            graph.add_edge("pm_round", END)
        else:
            graph.add_edge("aggregate", END)

        return graph

    def _get_graph(self) -> Any:
        """获取编译好的 LangGraph 应用（惰性编译）"""
        if self._compiled_graph is None:
            graph = self._build_graph()
            self._compiled_graph = graph.compile()
        return self._compiled_graph

    async def _save_reflection_to_memory(
        self, reflection: ReflectionRecord
    ) -> None:
        """将反思记录保存到记忆存储（不阻塞调用方）

        Args:
            reflection: 已生成的反思记录
        """
        if not self.memory_store:
            return

        try:
            await self.memory_store.put(
                key=f"{reflection.stock_code}_{reflection.session_id}",
                value=reflection.model_dump(),
                namespace=("reflective", "debate"),
            )
        except Exception as e:
            logger.warning("反思记忆存储失败: %s", e)

    async def reflect_on_decision(
        self,
        stock_code: str,
        outcome: ActualOutcome,
        session_id: str = "",
    ) -> ReflectionRecord | None:
        """事后反思入口 —— 加载历史决策 + 对比实际结果 → 生成反思记录

        这是 M2 反思闭环的公开 API。调用方提供股票代码和实际市场结果，
        编排器从 MemoryStore 加载对应的历史决策、调用 LLM 生成结构化反思、
        并自动保存到 ("reflective", "debate") 命名空间。

        Args:
            stock_code: 股票代码（用于查找对应的历史决策）
            outcome: 实际市场结果
            session_id: 历史会话标识（可选，用于关联）

        Returns:
            生成的反思记录（无历史决策或生成失败时返回 None）
        """
        if not self.memory_store:
            return None

        # 1. 加载历史决策
        decision = await _load_decision_from_memory(
            self.memory_store, stock_code
        )
        if decision is None:
            return None

        # 2. 生成反思
        reflection = await generate_reflection(
            decision_summary=decision,
            outcome=outcome,
            session_id=session_id,
        )

        # 3. 保存反思
        await self._save_reflection_to_memory(reflection)

        # 4. 分发实际结果事件，驱动信任度/后续结果回调（不阻塞反思返回）
        await self._dispatch_actual_outcome(decision, outcome, session_id)

        return reflection

    async def _dispatch_actual_outcome(
        self,
        decision: dict,
        outcome: ActualOutcome,
        session_id: str = "",
    ) -> None:
        """将实际结果分发给 RC 回调引擎（失败不阻塞主流程）。"""
        if self.callback_engine is None:
            return

        context = self._build_actual_outcome_context(decision, outcome, session_id)
        if not context["agent_analyses"]:
            logger.info("实际结果回调跳过：历史决策缺少 agent_analyses")
            return

        try:
            await self.callback_engine.dispatch(
                CallbackEventType.ACTUAL_OUTCOME_RECEIVED,
                context=context,
                source="debate.reflect_on_decision",
            )
        except Exception as e:
            logger.warning("实际结果回调分发失败: %s", e)

    def _build_actual_outcome_context(
        self,
        decision: dict,
        outcome: ActualOutcome,
        session_id: str = "",
    ) -> dict[str, Any]:
        """构造 ACTUAL_OUTCOME_RECEIVED 事件上下文。"""
        agent_analyses = decision.get("agent_analyses")
        if not isinstance(agent_analyses, list):
            agent_analyses = decision.get("analyses_summary")
        if not isinstance(agent_analyses, list):
            agent_analyses = []

        resolved_session_id = session_id or str(decision.get("session_id", ""))
        return {
            "agent_analyses": agent_analyses,
            "actual_outcome": {
                "actual_direction": outcome.actual_direction,
                "actual_price_change_pct": outcome.price_change_pct,
                "decision_date": outcome.decision_date or str(decision.get("decision_date", "")),
                "evaluation_date": outcome.evaluation_date,
                "session_id": resolved_session_id,
                "stock_code": outcome.stock_code,
                "sector": str(decision.get("sector", "")),
            },
            "session_id": resolved_session_id,
            "stock_code": outcome.stock_code,
            "sector": str(decision.get("sector", "")),
            "decision_date": outcome.decision_date or str(decision.get("decision_date", "")),
            "evaluation_date": outcome.evaluation_date,
        }

    async def _save_decision_to_memory(self, result: DebateResult) -> None:
        """将当前辩论结果保存到记忆存储（不阻塞辩论流程）

        Args:
            result: 已完成的辩论结果
        """
        if not self.memory_store:
            return

        decision = {
            "stock_code": result.stock_code,
            "stock_name": result.stock_name,
            "session_id": result.session_id,
            "question": result.question,
            "timestamp": date.today().isoformat(),
            "decision_date": date.today().isoformat(),
            "consensus": result.vote_summary.consensus,
            "average_score": result.vote_summary.average_score,
            "weighted_score": result.vote_summary.weighted_score,
            "confidence": result.vote_summary.confidence,
            "total_votes": result.vote_summary.total_votes,
            "agent_analyses": [a.model_dump() for a in result.analyses],
            "analyses_summary": [
                {
                    "agent_name": a.agent_name,
                    "skill_id": a.skill_id,
                    "skill_name": a.skill_name,
                    "rating": a.rating,
                    "score": a.score,
                    "summary": a.summary,
                    "confidence": a.confidence,
                    "direction": a.direction,
                    "success": a.success,
                }
                for a in result.analyses
            ],
        }
        if result.review_report is not None:
            decision["review_report"] = {
                "overall_quality": result.review_report.overall_quality,
                "independent_rating": result.review_report.independent_rating,
                "independent_score": result.review_report.independent_score,
            }

        try:
            await self.memory_store.put(
                key=result.stock_code,
                value=decision,
                namespace=("episodic", "debate"),
            )
        except Exception as e:
            logger.warning("反思记忆存储失败: %s", e)

    async def run(self, debate_input: DebateInput) -> DebateResult:
        """执行一轮辩论

        Args:
            debate_input: 辩论输入（股票代码 + 问题）

        Returns:
            辩论结果（含所有大师的分析 + 投票汇总）
        """
        app = self._get_graph()
        overall_start = time.monotonic()

        # 查询历史决策注入
        history_context = ""
        if self.memory_store:
            try:
                items = await self.memory_store.search(
                    namespace=("episodic", "debate"),
                    query="",
                    k=_MAX_HISTORY_FETCH,
                )
                history_context = _format_history_context(
                    items, debate_input.stock_code
                )
            except Exception as e:
                logger.exception("历史记忆查询失败: %s", e)

        # 查询反思记忆注入（M2 反思闭环）
        reflection_context = ""
        if self.memory_store and self.enable_reflection:
            try:
                refl_items = await self.memory_store.search(
                    namespace=("reflective", "debate"),
                    query="",
                    k=_MAX_HISTORY_FETCH,
                )
                reflection_context = _format_reflection_context(
                    refl_items, debate_input.stock_code
                )
            except Exception as e:
                logger.exception("反思记忆查询失败: %s", e)

        # 查询信任度权重（M4 动态权重）
        trust_weight_factors: dict[str, float] = {}
        if self.memory_store and self.enable_trust:
            try:
                tracker = TrustTracker(memory_store=self.memory_store)
                for skill in self.master_skills:
                    agent_name = f"master.{skill.skill_id}"
                    report = await tracker.get_trust_report(agent_name)
                    if report.is_reliable:
                        factor = compute_weight_factor(report.metrics)
                        trust_weight_factors[agent_name] = factor
            except Exception as e:
                logger.exception("信任度查询失败: %s", e)

        initial_state: DebateState = {
            "session_id": debate_input.session_id,
            "debate_input": debate_input.model_dump(),
            "current_round": 1,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {},
            "errors": [],
            "history_context": history_context,
            "reflection_context": reflection_context,
            "analyst_reports": {},
            "risk_round": {},
            "trader_round": {},
            "trade_recommendation": {},
            "trust_weight_factors": trust_weight_factors,
        }

        final_state = await app.ainvoke(initial_state)
        total_latency = (time.monotonic() - overall_start) * 1000

        analyses = list(final_state.get("analyses", {}).values())
        vs_raw = final_state.get("vote_summary", {})
        vote_summary = VoteSummary(**vs_raw) if isinstance(vs_raw, dict) else vs_raw

        # 解析 review_round（如果有）
        rr_raw = final_state.get("review_round", {})
        review_round = None
        if rr_raw and isinstance(rr_raw, dict) and rr_raw.get("rebuttals"):
            try:
                review_round = PeerReviewRound(**rr_raw)
            except Exception as e:
                logger.warning("PeerReviewRound 解析失败(结果构建): %s", e)

        # 解析 review_report（如果有）
        rrpt_raw = final_state.get("review_report", {})
        review_report = None
        if rrpt_raw and isinstance(rrpt_raw, dict) and rrpt_raw.get("overall_quality", 0) > 0:
            try:
                review_report = IndependentReview(**rrpt_raw)
            except Exception as e:
                logger.warning("IndependentReview 解析失败(结果构建): %s", e)

        # 解析 analyst_reports（如果有）
        ar_raw = final_state.get("analyst_reports", {})
        analyst_reports_result: dict[str, AnalystReport] | None = None
        if ar_raw and isinstance(ar_raw, dict):
            try:
                analyst_reports_result = {
                    k: AnalystReport(**v) if isinstance(v, dict) else v
                    for k, v in ar_raw.items()
                }
                if not analyst_reports_result:
                    analyst_reports_result = None
            except Exception as e:
                logger.warning("分析师报告解析失败(结果构建): %s", e)

        # 解析 risk_round（R1 风控层，如果启用）
        risk_raw = final_state.get("risk_round", {})
        risk_round_result: dict | None = None
        if risk_raw and isinstance(risk_raw, dict) and risk_raw.get("assessments"):
            risk_round_result = risk_raw

        # 解析 trader_round（T1 交易员层，如果启用）
        tdr_raw = final_state.get("trader_round", {})
        trader_round_result: dict | None = None
        if tdr_raw and isinstance(tdr_raw, dict) and tdr_raw.get("trade_plan"):
            trader_round_result = tdr_raw

        # 解析 trade_recommendation（R1 PM 裁决，如果启用）
        tr_raw = final_state.get("trade_recommendation", {})
        trade_rec: dict | None = None
        if tr_raw and isinstance(tr_raw, dict) and tr_raw.get("action"):
            trade_rec = tr_raw

        result = DebateResult(
            session_id=debate_input.session_id,
            stock_code=debate_input.stock_code,
            stock_name=debate_input.stock_name,
            question=debate_input.question,
            analyses=analyses,
            vote_summary=vote_summary,
            review_round=review_round,
            review_report=review_report,
            analyst_reports=analyst_reports_result,
            risk_round=risk_round_result,
            trader_round=trader_round_result,
            trade_recommendation=trade_rec,
            total_latency_ms=round(total_latency, 0),
        )

        # 保存决策到记忆存储（不阻塞，方法内部已处理 None 情况）
        await self._save_decision_to_memory(result)

        return result


__all__ = [
    "DebateOrchestrator",
    "DebateState",
    "aggregate_node",
    "collect_data_node",
    "make_analyst_round_node",
    "make_master_round_node",
    "make_review_report_node",
    "make_review_round_node",
]

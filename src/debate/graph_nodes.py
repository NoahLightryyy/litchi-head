"""辩论图的轮次节点工厂、偏差报告与加权聚合（自 orchestrator.py 拆出，逻辑未改）。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from src.debate.analysts import AnalystPersona
from src.debate.graph_state import (
    DebateState,
    _trim_market_data,
)
from src.debate.mirror import generate_mirror_report
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    BiasReport,
    IndependentReview,
    PeerReviewRound,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.participants import (
    _run_independent_review,
    _run_review_for_master,
    _run_single_analyst,
    _run_single_master,
)
from src.debate.trust import TrustTracker, calibrate_confidence
from src.memory.skill_disk import MasterSkill
from src.memory.store import MemoryStore

logger = logging.getLogger("src.debate.orchestrator")


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
            # DP-007: 信息隔离 — 裁剪 market_data，下游只需要 brief 文本
            "market_data": _trim_market_data(md),
        }

    return analyst_round_node


def make_master_round_node(
    skills: list[MasterSkill],
    min_trust_factor: float = 0.7,
):
    """创建大师轮次节点 —— 按信任度排序后顺序运行所有大师

    支持 DP-004 TrustTracker 旋钮扩展：
    - 发言顺序：按 trust_weight_factors 降序排列（信任度高的先发言）
    - 参与资格：trust_weight_factor < min_trust_factor 的大师跳过辩论
     - 注意：reliable 标记的过滤在 run() 阶段已处理，这里做二次保护。

    Args:
        skills: 参与辩论的大师列表
        min_trust_factor: 最低信任权重阈值（低于此值跳过发言）

    Returns:
        异步节点函数 (state) -> dict
    """

    async def master_round_node(state: DebateState) -> dict:
        """运行所有大师的策略分析（基于分析师报告）

        DP-004: 从 state 读取 trust_weight_factors，
        按信任度降序排序，低于阈值的大师跳过。
        """
        inp = state.get("debate_input", {})
        code = inp.get("stock_code", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        stock_name = inp.get("stock_name", "")
        md = state.get("market_data", {})
        sid = state.get("session_id", "")
        history_ctx = state.get("history_context", "")
        reflection_ctx = state.get("reflection_context", "")
        analyst_reports_raw = state.get("analyst_reports", {})

        # DP-004: 读取 trust_weight_factors
        trust_factors: dict[str, float] = state.get("trust_weight_factors", {})

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

        # DP-004: 按 trust_weight_factor 排序（降序），过滤低于阈值的
        skill_entries: list[tuple[float, MasterSkill]] = []
        for skill in skills:
            key = f"master.{skill.skill_id}"
            factor = trust_factors.get(key, 1.0)
            if factor < min_trust_factor:
                logger.info(
                    "DP-004 跳过大师 %s (factor=%.2f < %.2f)",
                    skill.skill_id, factor, min_trust_factor,
                )
                continue
            skill_entries.append((factor, skill))

        # 降序排列：信任度高的优先发言
        skill_entries.sort(key=lambda x: x[0], reverse=True)

        all_analyses: dict[str, AgentAnalysis] = {}
        all_errors: list[str] = []

        for _, skill in skill_entries:
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


def make_mirror_node(
    memory_store: MemoryStore | None = None,
    trust_tracker: TrustTracker | None = None,
    sector: str = "",
) -> Callable:  # type: ignore[type-arg]
    """创建镜子反思节点 —— 辩论结束后产出一份历史对比

    从 MemoryStore 查询历史辩论记录，对比当前分析中各位大师的表现。
    纯统计计算，不调用 LLM。

    Args:
        memory_store: 记忆存储（用于查询历史辩论和反思记录）
        trust_tracker: 信任度追踪器（用于板块胜率补充）
        sector: 板块标识（可选，用于筛选同板块记录）

    Returns:
        异步节点函数
    """

    async def mirror_node(state: DebateState) -> dict:
        if memory_store is None:
            return {"mirror_report": {}}

        inp = state.get("debate_input", {})
        code = str(inp.get("stock_code", ""))
        name = str(inp.get("stock_name", ""))
        analyses = state.get("analyses", {})

        report = await generate_mirror_report(
            stock_code=code,
            stock_name=name,
            current_analyses=analyses,
            memory_store=memory_store,
            trust_tracker=trust_tracker,
            sector=sector,
        )
        return {"mirror_report": report.model_dump()}

    return mirror_node


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
    trust_weight_factors: dict[str, float] = {}
    calibration_map: dict[str, list[dict[str, float]]] = state.get("calibration_map", {})

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

        # ── R4: 用校准曲线校准置信度 ─────────────────
        agent_calibration = calibration_map.get(a.agent_name, [])
        if agent_calibration:
            calibrated = calibrate_confidence(use_confidence, agent_calibration)
            use_confidence = calibrated

        # 应用 weight_suggestion（如果有）
        weight_factor = weight_suggestions.get(a.agent_name, 1.0)

        # ── M4: 叠加信任度权重因子 ─────────────────
        trust_factors_raw = state.get("trust_weight_factors", {})
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

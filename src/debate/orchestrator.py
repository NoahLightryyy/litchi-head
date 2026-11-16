"""辩论编排器 —— LangGraph StateGraph 驱动多大师顺序分析

核心流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. analyst_round — 5 位专业分析师（基本面/技术面/情绪面/宏观面/灵感官）
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
from collections.abc import Callable
from datetime import date
from typing import Any, cast

logger = logging.getLogger(__name__)

from langgraph.graph import END, StateGraph  # noqa: E402 — 惰性导入避免 Windows torch crash

from src.callback import CallbackEventType, ResultCallbackEngine  # noqa: E402
from src.callback.callbacks import register_m3_ext_callback  # noqa: E402
from src.data.collector import DataCollector  # noqa: E402
from src.data.evidence import (  # noqa: E402
    EvidenceEnvelope,
)
from src.data.evidence_service import DataEvidenceService  # noqa: E402
from src.data.kline_business import (  # noqa: E402
    KlineBusinessFailure,
)
from src.data.quote_runtime import (  # noqa: E402
    RealtimeQuoteEvidenceService,
    get_realtime_quote_evidence_runtime,
)
from src.debate.analysts import AnalystPersona, get_default_analysts  # noqa: E402
from src.debate.collection import (  # noqa: E402, F401
    _route_after_collection,
    _route_after_reasoning,
    collect_data_node,
)
from src.debate.evidence_gate import EvidenceIncompleteError  # noqa: E402
from src.debate.graph_nodes import (  # noqa: E402, F401
    aggregate_node,
    compute_bias_report,
    make_analyst_round_node,
    make_master_round_node,
    make_mirror_node,
    make_review_report_node,
    make_review_round_node,
)

# ── 拆分后的再导出：保持 `from src.debate.orchestrator import ...` 兼容 ──
from src.debate.graph_state import (  # noqa: E402, F401
    _BLOCKING_EVIDENCE_CODES,
    _DEFAULT_QUOTE_EVIDENCE_SERVICE,
    _MAX_HISTORY_FETCH,
    DebateState,
    _evidence_limitation,
    _format_evidence_limitation_notice,
    _must_block_reasoning,
    _trim_market_data,
)
from src.debate.kline_context import (  # noqa: E402
    KlineBusinessProvider,
)
from src.debate.models import (  # noqa: E402
    AnalystReport,
    DebateInput,
    DebateResult,
    EvidenceLimitation,
    EvidenceReference,
    IndependentReview,
    MirrorReport,
    PeerReviewRound,
    VoteSummary,
)
from src.debate.participants import (  # noqa: E402, F401
    _format_analyst_reports,
    _format_history_context,
    _run_independent_review,
    _run_review_for_master,
    _run_single_analyst,
    _run_single_master,
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
from src.memory.store import MemoryStore  # noqa: E402

# ── DebateOrchestrator ────────────────────────────────────────────


class DebateOrchestrator:
    """辩论编排器：LangGraph StateGraph 驱动多大师分析

    工作流程：
    1. 接收 DebateInput（股票代码 + 问题）
    2. collect_data 节点采集行情/K线/新闻
    3. analyst_round 节点运行 5 位专业分析师
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
        min_trust_factor: float = 0.7,
        enable_mirror: bool = False,
        news_evidence_service: DataEvidenceService | None = None,
        quote_evidence_service: RealtimeQuoteEvidenceService | None | object = (
            _DEFAULT_QUOTE_EVIDENCE_SERVICE
        ),
        kline_business_provider: KlineBusinessProvider | None = None,
        research_supplement: Callable[[str], str] | None = None,
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
            enable_mirror: 是否启用 DP-006 镜子反思（默认 False）
                启用后，辩论结束后自动产出一份历史对比报告。
                需要同时提供 memory_store。
            callback_engine: 结果回调引擎（可选）。
                不提供且 enable_trust=True 时自动创建并注册 M3-EXT 回调。
            min_trust_factor: DP-004 最低信任权重阈值（默认 0.7）。
                低于此值的大师跳过辩论发言，仅保留投票权重参与 aggregate。
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
        self.enable_mirror = enable_mirror
        self.research_supplement = research_supplement
        self.news_evidence_service = news_evidence_service
        self.quote_evidence_service = (
            get_realtime_quote_evidence_runtime().service
            if quote_evidence_service is _DEFAULT_QUOTE_EVIDENCE_SERVICE
            else cast(
                RealtimeQuoteEvidenceService | None,
                quote_evidence_service,
            )
        )
        self.kline_business_provider = kline_business_provider
        self.callback_engine = callback_engine
        self.min_trust_factor = min_trust_factor
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
            lambda state: collect_data_node(
                cast(DebateState, state),
                self.data_collector,
                self.news_evidence_service,
                self.quote_evidence_service,
                self.kline_business_provider,
                self.research_supplement,
            ),
        )
        graph.set_entry_point("collect_data")

        # 分析师轮次节点：5 位专业分析师（基本面/技术面/情绪面/宏观面/灵感官）
        graph.add_node(
            "analyst_round",
            make_analyst_round_node(self.analyst_personas),
        )
        graph.add_conditional_edges(
            "collect_data",
            _route_after_collection,
            {"continue": "analyst_round", "stop": END},
        )

        # 大师轮次节点（DP-004: 按信任度排序，低信任跳过）
        graph.add_node(
            "master_round",
            make_master_round_node(
                self.master_skills,
                min_trust_factor=self.min_trust_factor if self.enable_trust else 0.0,
            ),
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

        # ── DP-006: 镜子反思节点（可选）─────────────────
        if self.enable_mirror:
            graph.add_node(
                "mirror",
                make_mirror_node(
                    memory_store=self.memory_store,
                    trust_tracker=(
                        TrustTracker(memory_store=self.memory_store)
                        if self.enable_mirror
                        else None
                    ),
                    sector="",
                ),
            )
            after_aggregate = "mirror"
        else:
            after_aggregate = "aggregate"

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
            graph.add_conditional_edges(
                after_aggregate,
                _route_after_reasoning,
                {"risk": "risk_round", "stop": END},
            )

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
            graph.add_edge(after_aggregate, END)

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
            "evidence_limitations": [
                item.model_dump(mode="json") for item in result.evidence_limitations
            ],
            "evidence_references": [
                item.model_dump(mode="json") for item in result.evidence_references
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

        # 查询信任度权重（M4 动态权重）+ 校准曲线（R4 置信度校准）
        trust_weight_factors: dict[str, float] = {}
        calibration_map: dict[str, list[dict[str, float]]] = {}
        if self.memory_store and self.enable_trust:
            try:
                tracker = TrustTracker(memory_store=self.memory_store)
                for skill in self.master_skills:
                    agent_name = f"master.{skill.skill_id}"
                    report = await tracker.get_trust_report(agent_name)
                    if report.is_reliable:
                        factor = compute_weight_factor(report.metrics)
                        trust_weight_factors[agent_name] = factor
                        calibration_map[agent_name] = report.metrics.calibration_curve
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
            "calibration_map": calibration_map,
            "mirror_report": {},
            "evidence_envelope": {},
            "evidence_limitations": [],
            "evidence_references": [],
            "evidence_failure_kind": "",
        }

        final_state = await app.ainvoke(initial_state)
        total_latency = (time.monotonic() - overall_start) * 1000

        if "EVIDENCE_INCOMPLETE" in final_state.get("errors", []):
            failure_payload = final_state.get("evidence_envelope", {})
            failure_kind = final_state.get("evidence_failure_kind", "")
            if failure_kind == "kline_business":
                envelope: EvidenceEnvelope | KlineBusinessFailure | dict[str, object] = (
                    KlineBusinessFailure.model_validate(failure_payload)
                )
            elif failure_kind == "detail":
                envelope = failure_payload
            else:
                envelope = EvidenceEnvelope.model_validate(failure_payload)
            raise EvidenceIncompleteError(envelope)

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

        # 解析 mirror_report（DP-006 镜子反思，如果启用）
        mr_raw = final_state.get("mirror_report", {})
        mirror_report_result: MirrorReport | None = None
        if mr_raw and isinstance(mr_raw, dict) and mr_raw.get("total_histories_found", 0) > 0:
            try:
                mirror_report_result = MirrorReport(**mr_raw)
            except Exception as e:
                logger.warning("MirrorReport 解析失败(结果构建): %s", e)

        evidence_limitations = [
            EvidenceLimitation.model_validate(item)
            for item in final_state.get("evidence_limitations", [])
        ]
        evidence_references = [
            EvidenceReference.model_validate(item)
            for item in final_state.get("evidence_references", [])
        ]
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
            mirror_report=mirror_report_result,
            evidence_limitations=evidence_limitations,
            evidence_references=evidence_references,
            total_latency_ms=round(total_latency, 0),
        )

        # 保存决策到记忆存储（不阻塞，方法内部已处理 None 情况）
        await self._save_decision_to_memory(result)

        return result


__all__ = [
    "DebateOrchestrator",
    "DebateState",
    "_route_after_collection",
    "_route_after_reasoning",
    "aggregate_node",
    "collect_data_node",
    "make_analyst_round_node",
    "make_master_round_node",
    "make_review_report_node",
    "make_review_round_node",
]

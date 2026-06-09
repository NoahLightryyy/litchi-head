"""辩论编排器 —— LangGraph StateGraph 驱动多大师顺序分析

核心流程：
  1. collect_data — 采集行情 + K线 + 新闻
  2. master_round — 顺序调用每位大师（避免 LangGraph 并行写入冲突）
  3. aggregate — 投票加权汇总

用法：
    orchestrator = DebateOrchestrator()
    result = await orchestrator.run(DebateInput(stock_code="000001"))
    print(result.to_summary_dict())
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.base import AgentContext
from src.agents.master_agent import MasterAgent
from src.data.collector import DataCollector, format_market_brief
from src.data.models import KLine, NewsItem, StockQuote
from src.debate.models import AgentAnalysis, DebateInput, DebateResult, VoteSummary
from src.memory.skill_disk import MasterSkill, SkillDisk

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
        errors:         错误记录
    """

    session_id: str
    debate_input: dict
    current_round: int
    analyses: dict[str, AgentAnalysis]
    market_data: dict
    vote_summary: dict  # 序列化的 VoteSummary
    errors: list[str]


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
    except Exception:
        pass

    try:
        klines = collector.get_klines(code, period="daily", start="", end="")
    except Exception:
        pass

    try:
        news = collector.get_news(code)
    except Exception:
        pass

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


async def _run_single_master(
    skill: MasterSkill,
    session_id: str,
    question: str,
    stock_code: str,
    stock_name: str,
    market_data: dict,
) -> AgentAnalysis:
    """运行一位大师的分析，返回 AgentAnalysis

    Args:
        skill: 大师 Skill
        question: 分析问题
        market_data: 市场数据缓存

    Returns:
        结构化分析结果
    """
    start = time.monotonic()

    # 构建增强问题（附加上下文）
    enhanced = question
    brief = market_data.get("brief", "")
    if brief:
        enhanced += f"\n\n📊 以下为当前市场数据：\n{brief}"

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
        else:
            rating, score, summary, analysis_text, key_evidence, risk_warning = (
                "中性", 50, "", "", [], None
            )

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
        """运行所有大师的分析"""
        inp = state.get("debate_input", {})
        code = inp.get("stock_code", "")
        question = inp.get("question", "请分析这只股票的投资价值")
        stock_name = inp.get("stock_name", "")
        md = state.get("market_data", {})
        sid = state.get("session_id", "")

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


async def aggregate_node(state: DebateState) -> dict:
    """投票聚合节点 —— 汇总所有大师分析

    从 state 读取 analyses，计算：
    - 评级分布
    - 平均分和加权分
    - 共识评级

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

    # 评级分布
    dist: dict[str, int] = {}
    total_score = 0
    weighted_score_sum = 0.0
    total_weight = 0.0

    for a in successful:
        dist[a.rating] = dist.get(a.rating, 0) + 1
        total_score += a.score
        weighted_score_sum += a.score * a.confidence
        total_weight += a.confidence

    avg_score = total_score / len(successful)
    weighted_score = weighted_score_sum / total_weight if total_weight > 0 else avg_score

    # 共识（众数）
    consensus = max(dist, key=lambda k: dist[k]) if dist else "中性"

    # 置信度：一致性比例 * 0.4 + 平均信心 * 0.6
    max_count = max(dist.values())
    agreement_ratio = max_count / len(successful)
    avg_confidence = total_weight / len(successful)
    confidence = agreement_ratio * 0.4 + avg_confidence * 0.6

    return {
        "vote_summary": VoteSummary(
            total_votes=len(successful),
            rating_distribution=dist,
            average_score=round(avg_score, 1),
            weighted_score=round(weighted_score, 1),
            consensus=consensus,
            confidence=round(min(confidence, 0.95), 2),
        )
    }


# ── DebateOrchestrator ────────────────────────────────────────────


class DebateOrchestrator:
    """辩论编排器：LangGraph StateGraph 驱动多大师分析

    工作流程：
    1. 接收 DebateInput（股票代码 + 问题）
    2. collect_data 节点采集行情/K线/新闻
    3. master_round 节点顺序运行多位大师
    4. aggregate 节点加权投票汇总
    5. 返回 DebateResult

    用法：
        orch = DebateOrchestrator()
        result = await orch.run(DebateInput(stock_code="000001"))
        print(result.to_summary_dict())
    """

    def __init__(
        self,
        data_collector: DataCollector | None = None,
        skill_disk: SkillDisk | None = None,
        skill_ids: list[str] | None = None,
    ):
        """初始化辩论编排器

        Args:
            data_collector: 数据采集器，不传则新建
            skill_disk: 大师 Skill 盘，不传则新建
            skill_ids: 参与辩论的大师 ID 列表，None 则使用默认加载的大师
        """
        self.data_collector = data_collector or DataCollector()
        self.skill_disk = skill_disk or SkillDisk()

        # 加载大师列表
        if skill_ids is not None:
            self.master_skills: list[MasterSkill] = []
            for sid in skill_ids:
                try:
                    self.master_skills.append(self.skill_disk.load(sid))
                except KeyError:
                    pass
        else:
            self.master_skills = self.skill_disk.load_defaults()

        # 缓存编译好的图
        self._compiled_graph: Any = None

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 计算图

        collect_data → master_round（顺序执行所有大师） → aggregate → END

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

        # 大师轮次节点：顺序运行所有大师
        graph.add_node(
            "master_round",
            make_master_round_node(self.master_skills),
        )
        graph.add_edge("collect_data", "master_round")

        # 投票聚合节点
        graph.add_node("aggregate", aggregate_node)
        graph.add_edge("master_round", "aggregate")

        graph.add_edge("aggregate", END)

        return graph

    def _get_graph(self) -> Any:
        """获取编译好的 LangGraph 应用（惰性编译）"""
        if self._compiled_graph is None:
            graph = self._build_graph()
            self._compiled_graph = graph.compile()
        return self._compiled_graph

    async def run(self, debate_input: DebateInput) -> DebateResult:
        """执行一轮辩论

        Args:
            debate_input: 辩论输入（股票代码 + 问题）

        Returns:
            辩论结果（含所有大师的分析 + 投票汇总）
        """
        app = self._get_graph()
        overall_start = time.monotonic()

        initial_state: DebateState = {
            "session_id": debate_input.session_id,
            "debate_input": debate_input.model_dump(),
            "current_round": 1,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }

        final_state = await app.ainvoke(initial_state)
        total_latency = (time.monotonic() - overall_start) * 1000

        analyses = list(final_state.get("analyses", {}).values())
        vs_raw = final_state.get("vote_summary", {})
        vote_summary = VoteSummary(**vs_raw) if isinstance(vs_raw, dict) else vs_raw

        return DebateResult(
            session_id=debate_input.session_id,
            stock_code=debate_input.stock_code,
            stock_name=debate_input.stock_name,
            question=debate_input.question,
            analyses=analyses,
            vote_summary=vote_summary,
            total_latency_ms=round(total_latency, 0),
        )


__all__ = [
    "DebateOrchestrator",
    "DebateState",
    "aggregate_node",
    "collect_data_node",
    "make_master_round_node",
]

"""D1 第二轮交叉审阅+反驳 —— 单元测试

测试策略：
- RebuttalAnalysis / PeerReviewRound 模型构造与序列化
- _run_review_for_master 辅助函数的 mock 测试
- make_review_round_node 节点函数的 state 读写
- aggregate_node 在 rebuttal 存在时的调整行为
- 全流程集成测试（mock LLM 层）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import (
    AgentAnalysis,
    DebateInput,
    DebateResult,
    PeerReviewRound,
    RebuttalAnalysis,
    VoteSummary,
)


# ═══════════════════════════════════════════════════════════════════
# Phase 1: 模型测试
# ═══════════════════════════════════════════════════════════════════


class TestRebuttalAnalysis:
    """RebuttalAnalysis 模型构造与序列化"""

    def test_minimal_construction(self):
        """最少字段构造（所有调整字段默认为 None）"""
        r = RebuttalAnalysis(agent_name="master.buffett")
        assert r.agent_name == "master.buffett"
        assert r.original_agreement == 0.5
        assert r.rebuttal == ""
        assert r.adjusted_rating is None
        assert r.adjusted_score is None
        assert r.adjusted_confidence is None
        assert r.key_counterpoints == []
        assert r.peer_influences == ""
        assert r.latency_ms == 0.0

    def test_full_construction(self):
        """全字段构造"""
        r = RebuttalAnalysis(
            agent_name="master.buffett",
            original_agreement=0.3,
            rebuttal="我认为同行过于乐观，忽视了估值风险",
            adjusted_rating="看跌",
            adjusted_score=40,
            adjusted_confidence=0.7,
            key_counterpoints=["同行未考虑加息影响", "估值已处于历史高位"],
            peer_influences="芒格的风险提示让我调整了判断",
        )
        assert r.agent_name == "master.buffett"
        assert r.original_agreement == 0.3
        assert r.adjusted_rating == "看跌"
        assert r.adjusted_score == 40
        assert r.adjusted_confidence == 0.7
        assert len(r.key_counterpoints) == 2

    def test_serialization(self):
        """JSON 序列化与反序列化"""
        r = RebuttalAnalysis(
            agent_name="master.munger",
            original_agreement=0.8,
            rebuttal="同意同行分析，补充流动性风险",
            adjusted_rating="看涨",
            adjusted_score=75,
            adjusted_confidence=0.85,
            key_counterpoints=["需要关注成交量变化"],
        )
        dumped = r.model_dump()
        assert dumped["agent_name"] == "master.munger"
        assert dumped["original_agreement"] == 0.8
        assert dumped["adjusted_score"] == 75

        loaded = RebuttalAnalysis(**dumped)
        assert loaded.rebuttal == r.rebuttal
        assert loaded.key_counterpoints == r.key_counterpoints

    def test_adjusted_fields_default_to_none(self):
        """调整字段默认为 None，调用方应使用原始值"""
        r = RebuttalAnalysis(agent_name="master.test")
        assert r.adjusted_rating is None
        assert r.adjusted_score is None
        assert r.adjusted_confidence is None


class TestPeerReviewRound:
    """PeerReviewRound 模型构造与查询"""

    def test_empty_round(self):
        """空交叉审阅轮次"""
        prr = PeerReviewRound()
        assert prr.rebuttals == []
        assert prr.round_number == 2
        assert len(prr) == 0

    def test_with_rebuttals(self):
        """含反驳列表"""
        rebuttals = [
            RebuttalAnalysis(agent_name="master.buffett"),
            RebuttalAnalysis(agent_name="master.munger"),
        ]
        prr = PeerReviewRound(rebuttals=rebuttals)
        assert len(prr) == 2
        assert prr.rebuttals[0].agent_name == "master.buffett"

    def test_get_for_agent_found(self):
        """按 agent_name 查找成功"""
        rebuttals = [
            RebuttalAnalysis(agent_name="master.buffett"),
            RebuttalAnalysis(agent_name="master.munger"),
        ]
        prr = PeerReviewRound(rebuttals=rebuttals)
        found = prr.get_for_agent("master.buffett")
        assert found is not None
        assert found.agent_name == "master.buffett"

    def test_get_for_agent_not_found(self):
        """按 agent_name 查找失败返回 None"""
        prr = PeerReviewRound(rebuttals=[
            RebuttalAnalysis(agent_name="master.buffett"),
        ])
        assert prr.get_for_agent("nonexistent") is None

    def test_serialization(self):
        """JSON 序列化与反序列化"""
        prr = PeerReviewRound(rebuttals=[
            RebuttalAnalysis(agent_name="master.buffett", adjusted_score=80),
        ])
        dumped = prr.model_dump()
        assert dumped["round_number"] == 2
        assert len(dumped["rebuttals"]) == 1

        loaded = PeerReviewRound(**dumped)
        assert loaded.round_number == 2
        assert loaded.rebuttals[0].adjusted_score == 80


class TestDebateResultWithReviewRound:
    """DebateResult 向后兼容性"""

    @pytest.fixture
    def base_result(self) -> DebateResult:
        return DebateResult(
            session_id="test-s1",
            stock_code="000001",
            stock_name="平安银行",
            question="是否值得投资？",
            analyses=[
                AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="详细分析",
                    key_evidence=["护城河"],
                    confidence=0.85,
                ),
            ],
            vote_summary=VoteSummary(
                total_votes=1,
                rating_distribution={"看涨": 1},
                average_score=85.0,
                weighted_score=85.0,
                consensus="看涨",
                confidence=0.85,
            ),
        )

    def test_without_review_round(self, base_result):
        """不设置 review_round 时正常（向后兼容）"""
        assert base_result.review_round is None
        summary = base_result.to_summary_dict()
        assert summary["共识"] == "看涨"
        assert "交叉审阅" not in summary

    def test_with_review_round(self, base_result):
        """设置 review_round 后正常"""
        prr = PeerReviewRound(rebuttals=[
            RebuttalAnalysis(
                agent_name="master.buffett",
                adjusted_rating="看涨",
                adjusted_score=80,
            ),
        ])
        base_result.review_round = prr
        assert base_result.review_round is not None
        assert len(base_result.review_round) == 1

    def test_serialization_with_review_round(self, base_result):
        """含 review_round 的完整序列化"""
        prr = PeerReviewRound(rebuttals=[
            RebuttalAnalysis(
                agent_name="master.buffett",
                adjusted_rating="看涨",
                adjusted_score=80,
                adjusted_confidence=0.8,
                key_counterpoints=["估值偏高"],
            ),
        ])
        base_result.review_round = prr

        dumped = base_result.model_dump()
        assert dumped["review_round"] is not None
        assert len(dumped["review_round"]["rebuttals"]) == 1

        loaded = DebateResult(**dumped)
        assert loaded.review_round is not None
        assert loaded.review_round.rebuttals[0].adjusted_score == 80
        assert loaded.stock_code == "000001"


# ═══════════════════════════════════════════════════════════════════
# Phase 2: review_round_node 测试
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_analyses() -> dict[str, AgentAnalysis]:
    """3 位大师的模拟分析结果"""
    return {
        "master.buffett": AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=85,
            summary="看好长期价值",
            analysis="该公司具有强大护城河和稳定现金流...",
            key_evidence=["ROE连续5年>15%", "资产负债率<40%"],
            confidence=0.85,
        ),
        "master.munger": AgentAnalysis(
            agent_name="master.munger",
            skill_id="munger",
            skill_name="芒格",
            rating="中性",
            score=55,
            summary="需谨慎看待",
            analysis="当前估值偏高，但基本面尚可...",
            key_evidence=["PE处于历史高位", "行业竞争加剧"],
            confidence=0.6,
        ),
        "master.graham": AgentAnalysis(
            agent_name="master.graham",
            skill_id="graham",
            skill_name="格雷厄姆",
            rating="看涨",
            score=70,
            summary="安全边际充足",
            analysis="股价低于内在价值约20%，存在安全边际...",
            key_evidence=["市净率<1.5", "股息率>3%"],
            confidence=0.7,
        ),
    }


class TestReviewRoundNodeBasic:
    """make_review_round_node 基本行为验证"""

    @pytest.mark.asyncio
    async def test_node_returns_review_round_key(self, sample_analyses):
        """节点返回结果包含 review_round 字段"""
        from src.debate.orchestrator import DebateState, make_review_round_node

        state: DebateState = {
            "session_id": "test-d1-1",
            "debate_input": {
                "stock_code": "000001",
                "question": "是否值得投资？",
                "stock_name": "",
            },
            "current_round": 1,
            "analyses": sample_analyses,
            "market_data": {"brief": "测试简报"},
            "vote_summary": {},
            "review_round": {},
            "errors": [],
        }

        # mock _run_review_for_master 为每位大师返回不同反驳
        mock_rebuttals = [
            RebuttalAnalysis(
                agent_name="master.buffett",
                original_agreement=0.7,
                rebuttal="同意部分观点，但需考虑风险",
                adjusted_rating="看涨",
                adjusted_score=80,
                adjusted_confidence=0.8,
                key_counterpoints=["估值需时间消化"],
                peer_influences="芒格的谨慎观点有一定道理",
            ),
            RebuttalAnalysis(
                agent_name="master.munger",
                original_agreement=0.4,
                rebuttal="不同意看涨观点",
                adjusted_rating="中性",
                adjusted_score=50,
                adjusted_confidence=0.6,
                key_counterpoints=[],
                peer_influences="",
            ),
            RebuttalAnalysis(
                agent_name="master.graham",
                original_agreement=0.8,
                rebuttal="补充安全边际分析",
                adjusted_rating="看涨",
                adjusted_score=72,
                adjusted_confidence=0.75,
                key_counterpoints=[],
                peer_influences="",
            ),
        ]

        from src.memory.skill_disk import SkillDisk
        disk = SkillDisk()
        skills = [disk.load("buffett"), disk.load("munger"), disk.load("graham")]

        with patch(
            "src.debate.orchestrator._run_review_for_master",
            new_callable=AsyncMock,
            side_effect=mock_rebuttals,
        ):
            node_fn = make_review_round_node(skills)
            result = await node_fn(state)

            assert "review_round" in result
            prr = result["review_round"]
            # 节点返回的是序列化 dict（LangGraph state 格式）
            assert isinstance(prr, dict)
            assert "rebuttals" in prr
            assert len(prr["rebuttals"]) == 3
            actual_names = {r["agent_name"] for r in prr["rebuttals"]}
            assert actual_names == {"master.buffett", "master.munger", "master.graham"}

    @pytest.mark.asyncio
    async def test_node_skips_failed_masters(self, sample_analyses):
        """失败的大师不参与交叉审阅"""
        # 将一位大师标记为失败
        analyses_with_fail = dict(sample_analyses)
        analyses_with_fail["master.buffett"] = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="中性",
            score=0,
            summary="",
            analysis="",
            key_evidence=[],
            confidence=0.0,
            success=False,
            error="LLM 超时",
        )

        from src.debate.orchestrator import DebateState, make_review_round_node

        state: DebateState = {
            "session_id": "test-d1-2",
            "debate_input": {
                "stock_code": "000001",
                "question": "是否值得投资？",
                "stock_name": "",
            },
            "current_round": 1,
            "analyses": analyses_with_fail,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "errors": [],
        }

        from src.memory.skill_disk import SkillDisk
        disk = SkillDisk()
        skills = [disk.load("buffett"), disk.load("munger"), disk.load("graham")]

        mock_rebuttals = [
            RebuttalAnalysis(agent_name="master.munger"),
            RebuttalAnalysis(agent_name="master.graham"),
        ]
        with patch(
            "src.debate.orchestrator._run_review_for_master",
            new_callable=AsyncMock,
            side_effect=mock_rebuttals,
        ):
            node_fn = make_review_round_node(skills)
            result = await node_fn(state)
            prr = result["review_round"]
            # buffett 失败不参与，所以只有 munger 和 graham 产生反驳
            assert prr is not None
            assert len(prr["rebuttals"]) == 2
            actual_names = {r["agent_name"] for r in prr["rebuttals"]}
            assert actual_names == {"master.munger", "master.graham"}

    @pytest.mark.asyncio
    async def test_node_single_master_returns_empty(self):
        """仅一位大师时交叉审阅返回空"""
        from src.debate.orchestrator import DebateState, make_review_round_node

        single_analysis = {
            "master.buffett": AgentAnalysis(
                agent_name="master.buffett",
                skill_id="buffett",
                skill_name="巴菲特",
                rating="看涨",
                score=80,
                summary="看好",
                analysis="分析",
                key_evidence=[],
                confidence=0.8,
            ),
        }
        state: DebateState = {
            "session_id": "test-d1-3",
            "debate_input": {"stock_code": "000001"},
            "current_round": 1,
            "analyses": single_analysis,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "errors": [],
        }

        from src.memory.skill_disk import SkillDisk
        disk = SkillDisk()
        skills = [disk.load("buffett")]

        node_fn = make_review_round_node(skills)
        result = await node_fn(state)
        prr = result["review_round"]
        assert prr is not None
        assert len(prr["rebuttals"]) == 0  # 少于2人，返回空列表


class TestReviewRoundHelpers:
    """_run_review_for_master 辅助函数行为验证"""

    @pytest.mark.asyncio
    async def test_helper_calls_llm_structured(self, sample_analyses):
        """辅助函数调用 llm_service.invoke_structured"""
        from src.debate.orchestrator import _run_review_for_master
        from src.memory.skill_disk import SkillDisk

        disk = SkillDisk()
        skill = disk.load("buffett")
        own = sample_analyses["master.buffett"]
        peers = [
            sample_analyses["master.munger"],
            sample_analyses["master.graham"],
        ]

        mock_llm_response = MagicMock()
        mock_llm_response.agent_name = "master.buffett"
        mock_llm_response.original_agreement = 0.6
        mock_llm_response.rebuttal = "同意基本面分析，但需关注估值"
        mock_llm_response.adjusted_rating = "看涨"
        mock_llm_response.adjusted_score = 78
        mock_llm_response.adjusted_confidence = 0.8
        mock_llm_response.key_counterpoints = ["估值偏高"]
        mock_llm_response.peer_influences = "同行提示了估值风险"

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await _run_review_for_master(
                skill=skill,
                session_id="test",
                question="是否值得投资？",
                own_analysis=own,
                peer_analyses=peers,
                market_data={"brief": "测试简报"},
            )

            assert isinstance(result, RebuttalAnalysis)
            assert result.agent_name == "master.buffett"
            assert result.original_agreement == 0.6
            assert result.adjusted_score == 78
            assert len(result.key_counterpoints) == 1

    @pytest.mark.asyncio
    async def test_helper_error_returns_default(self, sample_analyses):
        """辅助函数异常时返回默认 RebuttalAnalysis"""
        from src.debate.orchestrator import _run_review_for_master
        from src.memory.skill_disk import SkillDisk

        disk = SkillDisk()
        skill = disk.load("munger")
        own = sample_analyses["master.munger"]
        peers = [sample_analyses["master.buffett"]]

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM 调用失败"),
        ):
            result = await _run_review_for_master(
                skill=skill,
                session_id="test",
                question="测试",
                own_analysis=own,
                peer_analyses=peers,
                market_data={},
            )

            assert isinstance(result, RebuttalAnalysis)
            assert result.agent_name == "master.munger"
            assert result.adjusted_score is None
            assert result.rebuttal == ""
            assert result.latency_ms == 0.0


# ═══════════════════════════════════════════════════════════════════
# Phase 4: aggregate_node 在 rebuttal 存在时的行为
# ═══════════════════════════════════════════════════════════════════


class TestAggregateWithRebuttals:
    """aggregate_node 在 review_round 存在时的调整行为"""

    @pytest.mark.asyncio
    async def test_aggregate_uses_adjusted_scores(self):
        """rebuttal 存在时用 adjusted_score 替代原始 score"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d1-1",
            "debate_input": {},
            "current_round": 2,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.85,
                ),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=55,
                    summary="谨慎",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.6,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {
                "rebuttals": [
                    {
                        "agent_name": "master.buffett",
                        "original_agreement": 0.5,
                        "rebuttal": "同意部分观点",
                        "adjusted_rating": "看涨",
                        "adjusted_score": 75,
                        "adjusted_confidence": 0.8,
                        "key_counterpoints": ["估值偏高"],
                        "peer_influences": "",
                    },
                    {
                        "agent_name": "master.munger",
                        "original_agreement": 0.8,
                        "rebuttal": "同意同行",
                        "adjusted_rating": "看涨",
                        "adjusted_score": 65,
                        "adjusted_confidence": 0.7,
                        "key_counterpoints": [],
                        "peer_influences": "巴菲特的信心让我略微调整",
                    },
                ],
                "round_number": 2,
            },
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        # buffett: 75, munger: 65 → avg=(75+65)/2=70
        assert vs.average_score == 70.0, f"Expected 70.0, got {vs.average_score}"
        # 两者都是看涨 → consensus = "看涨"
        assert vs.consensus == "看涨"

    @pytest.mark.asyncio
    async def test_aggregate_without_review_round(self):
        """没有 review_round 时保持原行为"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d1-2",
            "debate_input": {},
            "current_round": 1,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.85,
                ),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=55,
                    summary="谨慎",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.6,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        # 原始: (85+55)/2=70
        assert vs.average_score == 70.0
        assert vs.total_votes == 2

    @pytest.mark.asyncio
    async def test_aggregate_with_empty_review_round(self):
        """review_round 为空 rebuttals 时保持原行为"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d1-3",
            "debate_input": {},
            "current_round": 2,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.85,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {"rebuttals": [], "round_number": 2},
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.average_score == 85.0
        assert vs.total_votes == 1

    @pytest.mark.asyncio
    async def test_rebuttal_only_updates_matching_agents(self):
        """只匹配 agent_name 的分析被调整，不匹配的保持原值"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d1-4",
            "debate_input": {},
            "current_round": 2,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.85,
                ),
                "master.dalio": AgentAnalysis(
                    agent_name="master.dalio",
                    skill_id="dalio",
                    skill_name="达利欧",
                    rating="中性",
                    score=50,
                    summary="中性",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.5,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {
                "rebuttals": [
                    {
                        "agent_name": "master.buffett",
                        "original_agreement": 0.5,
                        "rebuttal": "调整观点",
                        "adjusted_rating": "看涨",
                        "adjusted_score": 70,
                        "adjusted_confidence": 0.75,
                        "key_counterpoints": [],
                        "peer_influences": "",
                    },
                ],
                "round_number": 2,
            },
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        # buffett 调整: 70, dalio 保持: 50 → avg=60
        assert vs.average_score == 60.0
        assert vs.total_votes == 2


# ═══════════════════════════════════════════════════════════════════
# Phase 3+5: 完整图结构和全流程集成测试
# ═══════════════════════════════════════════════════════════════════


class TestGraphWithD1:
    """D1 集成后的 LangGraph 图结构"""

    def test_graph_has_review_round_node(self):
        """图包含 review_round 节点"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(data_collector=mock_collector)
        graph = orch._build_graph()
        app = graph.compile()
        graph_def = app.get_graph()
        assert graph_def is not None

        # get_graph() 返回的节点名可直接用 in 检查
        node_names = {n for n in graph_def.nodes}
        assert "collect_data" in node_names
        assert "master_round" in node_names
        assert "review_round" in node_names, "review_round 节点应存在于图中"
        assert "aggregate" in node_names

    def test_orchestrator_compiles_with_d1(self):
        """编排器在包含 review_round 的状态下成功编译"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(data_collector=mock_collector)
        graph = orch._build_graph()
        app = graph.compile()
        assert app is not None


class TestFullFlowWithD1:
    """D1 完整辩论流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_flow_with_d1(self):
        """全流程：3 位大师 + 交叉审阅 + 聚合"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger", "graham"],
        )

        # 模拟第一轮分析
        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="详细分析",
            key_evidence=["护城河"],
            confidence=0.8,
        )

        # 模拟第二轮反驳
        mock_rebuttal = RebuttalAnalysis(
            agent_name="master.buffett",
            original_agreement=0.6,
            rebuttal="同行分析有一定道理，但基本面未变",
            adjusted_rating="看涨",
            adjusted_score=75,
            adjusted_confidence=0.75,
            key_counterpoints=["短期波动不影响长期价值"],
            peer_influences="Graham 的安全边际分析很有见地",
        )

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=mock_rebuttal,
            ),
        ):
            inp = DebateInput(
                stock_code="000001",
                stock_name="平安银行",
                question="是否值得投资？",
            )
            result = await orch.run(inp)

            assert isinstance(result, DebateResult)
            assert result.stock_code == "000001"
            assert len(result.analyses) == 3

            # 验证 review_round 存在
            assert result.review_round is not None
            assert len(result.review_round) == 3

            # 验证 aggregate 使用了调整后的评分
            vs = result.vote_summary
            assert vs.total_votes == 3

    @pytest.mark.asyncio
    async def test_to_summary_dict_with_d1(self):
        """D1 全流程后 to_summary_dict 可用"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=85,
            summary="看好",
            analysis="分析",
            key_evidence=["证据"],
            confidence=0.85,
        )
        mock_rebuttal = RebuttalAnalysis(
            agent_name="master.buffett",
            adjusted_rating="看涨",
            adjusted_score=80,
            adjusted_confidence=0.8,
        )

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=mock_rebuttal,
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)
            summary = result.to_summary_dict()
            assert summary["共识"] == "看涨"
            assert summary["参与大师数"] == 1

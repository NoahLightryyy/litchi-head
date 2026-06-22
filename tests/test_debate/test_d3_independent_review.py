"""D3 独立评审 Agent —— 单元测试

测试策略（与 D1 测试模式一致）：
- IndependentReview 模型构造与序列化
- _run_independent_review 辅助函数的 mock 测试
- make_review_report_node 节点函数的 state 读写
- aggregate_node 在评审存在时的权重调整行为
- 全流程集成测试（mock LLM 层）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import (
    AgentAnalysis,
    DebateInput,
    DebateResult,
    IndependentReview,
    RebuttalAnalysis,
    VoteSummary,
)

# ═══════════════════════════════════════════════════════════════════
# Phase 1: 模型测试
# ═══════════════════════════════════════════════════════════════════


class TestIndependentReviewModel:
    """IndependentReview 模型构造与序列化"""

    def test_minimal_construction(self):
        """最少字段构造（所有可选字段使用默认值）"""
        r = IndependentReview()
        assert r.reviewer_style == "independent_reviewer"
        assert r.overall_quality == 0.0  # 默认 0.0 表示未运行
        assert r.independent_rating == "中性"
        assert r.independent_score == 0  # 默认 0 表示未运行
        assert r.confidence == 0.0
        assert r.consensus_support == 0.5
        assert r.quality_assessments == {}
        assert r.weight_suggestions == {}
        assert r.identified_biases == []
        assert r.blind_spots == []
        assert r.key_risks_synthesis == ""
        assert r.consistency_observation == ""
        assert r.aggregation_recommendation == ""
        assert r.latency_ms == 0.0

    def test_full_construction(self):
        """全字段构造"""
        r = IndependentReview(
            reviewer_style="independent_reviewer",
            overall_quality=0.75,
            independent_rating="看涨",
            independent_score=72,
            confidence=0.8,
            consensus_support=0.6,
            quality_assessments={
                "master.buffett": "分析全面，数据支撑充分",
                "master.munger": "逻辑清晰但缺少定量分析",
            },
            weight_suggestions={
                "master.buffett": 1.2,
                "master.munger": 0.8,
            },
            identified_biases=["过度关注短期波动", "对行业政策解读偏乐观"],
            blind_spots=["未考虑汇率风险"],
            key_risks_synthesis="主要风险来自政策变化和竞争加剧",
            consistency_observation="各位大师在基本面判断上基本一致",
            aggregation_recommendation="建议采纳巴菲特评分，对芒格做降权处理",
        )
        assert r.overall_quality == 0.75
        assert r.independent_score == 72
        assert r.weight_suggestions["master.buffett"] == 1.2
        assert len(r.identified_biases) == 2
        assert len(r.blind_spots) == 1

    def test_serialization(self):
        """JSON 序列化与反序列化"""
        r = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=78,
            weight_suggestions={"master.buffett": 1.1, "master.munger": 0.9},
            identified_biases=["共识偏差"],
        )
        dumped = r.model_dump()
        assert dumped["overall_quality"] == 0.8
        assert dumped["independent_rating"] == "看涨"
        assert len(dumped["weight_suggestions"]) == 2
        assert len(dumped["identified_biases"]) == 1

        loaded = IndependentReview(**dumped)
        assert loaded.independent_score == 78
        assert loaded.weight_suggestions["master.buffett"] == 1.1

    def test_default_weight_suggestions_empty(self):
        """权重建议默认为空字典（向后兼容）"""
        r = IndependentReview()
        assert r.weight_suggestions == {}
        assert r.quality_assessments == {}

    def test_confidence_default_zero(self):
        """confidence 默认为 0.0（未运行时）"""
        r = IndependentReview()
        assert r.confidence == 0.0


class TestDebateResultWithIndependentReview:
    """DebateResult 包含 IndependentReview 的向后兼容性"""

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

    def test_without_review_report(self, base_result):
        """不设置 review_report 时正常（向后兼容）"""
        assert base_result.review_report is None
        summary = base_result.to_summary_dict()
        assert summary["共识"] == "看涨"
        # review_report 默认不应出现
        assert "独立评审" not in summary

    def test_with_review_report(self, base_result):
        """设置 review_report 后正常"""
        review = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=80,
            weight_suggestions={"master.buffett": 1.0},
        )
        base_result.review_report = review
        assert base_result.review_report is not None
        assert base_result.review_report.overall_quality == 0.8

    def test_serialization_with_review_report(self, base_result):
        """含 review_report 的完整序列化"""
        review = IndependentReview(
            overall_quality=0.75,
            independent_rating="看涨",
            independent_score=75,
            identified_biases=["样本偏差"],
        )
        base_result.review_report = review

        dumped = base_result.model_dump()
        assert dumped["review_report"] is not None
        assert dumped["review_report"]["overall_quality"] == 0.75
        assert len(dumped["review_report"]["identified_biases"]) == 1

        loaded = DebateResult(**dumped)
        assert loaded.review_report is not None
        assert loaded.review_report.independent_rating == "看涨"
        assert loaded.stock_code == "000001"

    def test_review_report_in_summary_dict(self, base_result):
        """to_summary_dict 包含独立评审信息"""
        review = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=78,
        )
        base_result.review_report = review
        summary = base_result.to_summary_dict()
        assert summary.get("独立评审") is True
        assert summary.get("评审质量") == 0.8
        assert summary.get("评审评级") == "看涨"


# ═══════════════════════════════════════════════════════════════════
# Phase 2: review_report_node 测试
# ═══════════════════════════════════════════════════════════════════


class TestReviewReportNodeBasic:
    """make_review_report_node 基本行为验证"""

    @pytest.mark.asyncio
    async def test_node_returns_review_report_key(self, sample_analyses):
        """节点返回结果包含 review_report 字段"""
        from src.debate.orchestrator import DebateState, make_review_report_node

        state: DebateState = {
            "session_id": "test-d3-1",
            "debate_input": {
                "stock_code": "000001",
                "question": "是否值得投资？",
                "stock_name": "",
            },
            "current_round": 1,
            "analyses": sample_analyses,
            "market_data": {"brief": "测试简报"},
            "vote_summary": {},
            "review_round": {
                "rebuttals": [
                    {
                        "agent_name": "master.buffett",
                        "original_agreement": 0.6,
                        "rebuttal": "同意部分观点",
                    },
                ],
                "round_number": 2,
            },
            "review_report": {},
            "errors": [],
        }

        # mock _run_independent_review 返回预设评审
        mock_review = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=70,
            confidence=0.75,
            consensus_support=0.65,
            weight_suggestions={
                "master.buffett": 1.1,
                "master.munger": 0.9,
                "master.graham": 1.0,
            },
            identified_biases=["对行业政策过于乐观"],
            key_risks_synthesis="政策风险是主要不确定性",
        )

        with patch(
            "src.debate.orchestrator._run_independent_review",
            new_callable=AsyncMock,
            return_value=mock_review,
        ):
            node_fn = make_review_report_node()
            result = await node_fn(state)

            assert "review_report" in result
            report = result["review_report"]
            assert isinstance(report, dict)
            assert report["independent_rating"] == "看涨"
            assert report["overall_quality"] == 0.8
            assert len(report["weight_suggestions"]) == 3
            assert len(report["identified_biases"]) == 1

    @pytest.mark.asyncio
    async def test_node_no_successful_masters(self):
        """所有大师失败时返回空评审"""
        from src.debate.orchestrator import DebateState, make_review_report_node

        all_failed = {
            "master.fail1": AgentAnalysis(
                agent_name="master.fail1",
                skill_id="f1",
                skill_name="失败一",
                rating="中性",
                score=0,
                summary="",
                analysis="",
                key_evidence=[],
                confidence=0.0,
                success=False,
                error="超时",
            ),
        }
        state: DebateState = {
            "session_id": "test-d3-2",
            "debate_input": {"stock_code": "000001"},
            "current_round": 1,
            "analyses": all_failed,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {},
            "errors": ["全部失败"],
        }

        node_fn = make_review_report_node()
        result = await node_fn(state)
        report = result["review_report"]
        assert report is not None
        assert isinstance(report, dict)
        # 空评审应有默认值
        assert report["overall_quality"] == 0.0
        assert report["independent_rating"] == "中性"
        assert report["independent_score"] == 0

    @pytest.mark.asyncio
    async def test_node_without_review_round(self, sample_analyses):
        """没有 review_round 时仍能生成评审"""
        from src.debate.orchestrator import DebateState, make_review_report_node

        state: DebateState = {
            "session_id": "test-d3-3",
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
            "review_report": {},
            "errors": [],
        }

        mock_review = IndependentReview(
            overall_quality=0.7,
            independent_rating="中性",
            independent_score=60,
        )

        with patch(
            "src.debate.orchestrator._run_independent_review",
            new_callable=AsyncMock,
            return_value=mock_review,
        ):
            node_fn = make_review_report_node()
            result = await node_fn(state)

            assert "review_report" in result
            report = result["review_report"]
            assert report["independent_rating"] == "中性"
            assert report["overall_quality"] == 0.7


class TestIndependentReviewHelpers:
    """_run_independent_review 辅助函数行为验证"""

    @pytest.mark.asyncio
    async def test_helper_calls_llm_structured(self, sample_analyses):
        """辅助函数调用 llm_service.invoke_structured"""
        from src.debate.orchestrator import _run_independent_review

        successful = [a for a in sample_analyses.values() if a.success]

        mock_llm_response = MagicMock()
        mock_llm_response.reviewer_style = "independent_reviewer"
        mock_llm_response.overall_quality = 0.8
        mock_llm_response.independent_rating = "看涨"
        mock_llm_response.independent_score = 72
        mock_llm_response.confidence = 0.75
        mock_llm_response.consensus_support = 0.6
        mock_llm_response.quality_assessments = {
            "master.buffett": "详尽且数据充分",
        }
        mock_llm_response.weight_suggestions = {
            "master.buffett": 1.1,
            "master.munger": 0.9,
            "master.graham": 1.0,
        }
        mock_llm_response.identified_biases = ["共识偏差"]
        mock_llm_response.blind_spots = ["汇率风险"]
        mock_llm_response.key_risks_synthesis = "政策风险为主"
        mock_llm_response.consistency_observation = "基本一致"
        mock_llm_response.aggregation_recommendation = "加权采纳"

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await _run_independent_review(
                session_id="test",
                question="测试问题",
                successful_analyses=successful,
                rebuttals=[],
                market_data={"brief": "测试简报"},
            )

            assert isinstance(result, IndependentReview)
            assert result.overall_quality == 0.8
            assert result.independent_rating == "看涨"
            assert result.independent_score == 72
            assert result.confidence == 0.75
            assert len(result.weight_suggestions) == 3
            assert len(result.identified_biases) == 1
            assert result.latency_ms >= 0  # mock 瞬时返回，latency 可能为 0

    @pytest.mark.asyncio
    async def test_helper_with_rebuttals(self, sample_analyses):
        """辅助函数在有 rebuttals 时包含反驳信息"""
        from src.debate.orchestrator import _run_independent_review

        successful = [a for a in sample_analyses.values() if a.success]
        rebuttals = [
            RebuttalAnalysis(
                agent_name="master.buffett",
                original_agreement=0.6,
                rebuttal="同行观点有一定调整",
                adjusted_rating="看涨",
                adjusted_score=75,
            ),
        ]

        mock_llm_response = MagicMock()
        mock_llm_response.reviewer_style = "independent_reviewer"
        mock_llm_response.overall_quality = 0.75
        mock_llm_response.independent_rating = "看涨"
        mock_llm_response.independent_score = 70
        mock_llm_response.confidence = 0.7
        mock_llm_response.consensus_support = 0.55
        mock_llm_response.quality_assessments = {}
        mock_llm_response.weight_suggestions = {}
        mock_llm_response.identified_biases = []
        mock_llm_response.blind_spots = []
        mock_llm_response.key_risks_synthesis = ""
        mock_llm_response.consistency_observation = ""
        mock_llm_response.aggregation_recommendation = ""

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await _run_independent_review(
                session_id="test",
                question="测试问题",
                successful_analyses=successful,
                rebuttals=rebuttals,
                market_data={"brief": "有简报"},
            )

            assert isinstance(result, IndependentReview)
            assert result.independent_score == 70

    @pytest.mark.asyncio
    async def test_helper_error_returns_default(self, sample_analyses):
        """辅助函数异常时返回默认 IndependentReview"""
        from src.debate.orchestrator import _run_independent_review

        successful = [a for a in sample_analyses.values() if a.success]

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM 调用失败"),
        ):
            result = await _run_independent_review(
                session_id="test",
                question="测试",
                successful_analyses=successful,
                rebuttals=[],
                market_data={},
            )

            assert isinstance(result, IndependentReview)
            assert result.latency_ms == 0.0
            assert result.overall_quality == 0.0
            assert result.independent_score == 0


# ═══════════════════════════════════════════════════════════════════
# Phase 3: aggregate_node 在 review_report 存在时的行为
# ═══════════════════════════════════════════════════════════════════


class TestAggregateWithReviewReport:
    """aggregate_node 在 review_report 存在时的权重调整行为"""

    @pytest.mark.asyncio
    async def test_aggregate_applies_weight_suggestions(self):
        """review_report 的 weight_suggestions 影响加权评分"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d3-1",
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
                    confidence=0.8,
                ),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=50,
                    summary="谨慎",
                    analysis="分析",
                    key_evidence=[],
                    confidence=0.5,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.8,
                "independent_rating": "看涨",
                "independent_score": 70,
                "confidence": 0.75,
                "consensus_support": 0.6,
                "weight_suggestions": {
                    "master.buffett": 1.2,  # 权重上调
                    "master.munger": 0.5,  # 权重下调
                },
                "identified_biases": [],
                "blind_spots": [],
                "key_risks_synthesis": "",
                "consistency_observation": "",
                "aggregation_recommendation": "",
                "latency_ms": 500.0,
            },
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]

        # buffett: score=85, conf=0.8, weight=1.2 → 加权贡献=85*0.8*1.2=81.6
        # munger:  score=50, conf=0.5, weight=0.5 → 加权贡献=50*0.5*0.5=12.5
        # weighted_score = (81.6+12.5)/(0.8*1.2 + 0.5*0.5) = 94.1/(0.96+0.25) = 94.1/1.21 ≈ 77.77
        # average_score 保持原始 (85+50)/2 = 67.5
        assert vs.total_votes == 2
        assert vs.average_score == 67.5  # 平均分不受权重影响
        expected_weighted = round((85*0.8*1.2 + 50*0.5*0.5) / (0.8*1.2 + 0.5*0.5), 1)
        assert vs.weighted_score == expected_weighted, (
            f"Expected {expected_weighted}, got {vs.weighted_score}"
        )

    @pytest.mark.asyncio
    async def test_aggregate_without_review_report(self):
        """没有 review_report 时保持原行为"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d3-2",
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
            "review_report": {},
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        # 原始: avg=(85+55)/2=70, weighted=(85*0.85+55*0.6)/(0.85+0.6)
        raw_weighted = (85*0.85 + 55*0.6) / (0.85 + 0.6)
        assert vs.average_score == 70.0
        assert vs.weighted_score == round(raw_weighted, 1)

    @pytest.mark.asyncio
    async def test_aggregate_with_rebuttal_and_review_report(self):
        """review_report 与 rebuttal 叠加：先应用 rebuttal 调整，再应用 weight_suggestions"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d3-3",
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
                    confidence=0.8,
                ),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=50,
                    summary="谨慎",
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
                        "rebuttal": "调整",
                        "adjusted_rating": "看涨",
                        "adjusted_score": 75,
                        "adjusted_confidence": 0.75,
                        "key_counterpoints": [],
                        "peer_influences": "",
                    },
                ],
                "round_number": 2,
            },
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.8,
                "independent_rating": "看涨",
                "independent_score": 0,
                "confidence": 0.0,
                "consensus_support": 0.0,
                "weight_suggestions": {
                    "master.buffett": 1.2,
                    "master.munger": 0.8,
                },
                "identified_biases": [],
                "blind_spots": [],
                "key_risks_synthesis": "",
                "consistency_observation": "",
                "aggregation_recommendation": "",
                "latency_ms": 0.0,
            },
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]

        # buffett: rebuttal adjusted_score=75, adjusted_confidence=0.75, weight=1.2
        #   → 加权贡献=75*0.75*1.2=67.5, 权重=0.75*1.2=0.9
        # munger: 原始 score=50, conf=0.5, weight=0.8
        #   → 加权贡献=50*0.5*0.8=20.0, 权重=0.5*0.8=0.4
        # weighted_score = (67.5+20.0)/(0.9+0.4) = 87.5/1.3 ≈ 67.3
        assert vs.total_votes == 2
        expected_weighted = round((75*0.75*1.2 + 50*0.5*0.8) / (0.75*1.2 + 0.5*0.8), 1)
        assert vs.weighted_score == expected_weighted

    @pytest.mark.asyncio
    async def test_adjustments_applied_true_with_review_report(self):
        """有 review_report 时 adjustments_applied 标记通过 rebuttal 检测"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-aggr-d3-4",
            "debate_input": {},
            "current_round": 2,
            "analyses": {
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
            },
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.8,
                "independent_rating": "看涨",
                "independent_score": 75,
                "confidence": 0.75,
                "consensus_support": 0.6,
                "weight_suggestions": {"master.buffett": 0.9},
                "identified_biases": [],
                "blind_spots": [],
                "key_risks_synthesis": "",
                "consistency_observation": "",
                "aggregation_recommendation": "",
                "latency_ms": 500.0,
            },
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        # review_report alone 不会设 adjustments_applied=True（需有 rebuttal）
        assert not vs.adjustments_applied


# ═══════════════════════════════════════════════════════════════════
# Phase 4: 完整图结构和全流程集成测试
# ═══════════════════════════════════════════════════════════════════


class TestGraphWithD3:
    """D3 集成后的 LangGraph 图结构"""

    def test_graph_has_review_report_node(self):
        """图包含 review_report 节点"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(data_collector=mock_collector)
        graph = orch._build_graph()
        app = graph.compile()
        graph_def = app.get_graph()

        node_names = {n for n in graph_def.nodes}
        assert "collect_data" in node_names
        assert "master_round" in node_names
        assert "review_round" in node_names
        assert "review_report" in node_names, "review_report 节点应存在于图中"
        assert "aggregate" in node_names

    def test_orchestrator_compiles_with_d3(self):
        """编排器在包含 review_report 的状态下成功编译"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(data_collector=mock_collector)
        graph = orch._build_graph()
        app = graph.compile()
        assert app is not None


@pytest.mark.slow
class TestFullFlowWithD3:
    """D3 完整辩论流程集成测试（~30s 合计，标记为 slow）"""

    @pytest.mark.asyncio
    async def test_full_flow_with_d3(self):
        """全流程：3 位大师 + 交叉审阅 + 独立评审 + 聚合"""
        from src.debate.orchestrator import DebateOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger", "graham"],
        )

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

        mock_rebuttal = RebuttalAnalysis(
            agent_name="master.buffett",
            original_agreement=0.6,
            rebuttal="同行分析有一定道理",
            adjusted_rating="看涨",
            adjusted_score=75,
        )

        mock_review = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=72,
            confidence=0.75,
            weight_suggestions={
                "master.buffett": 1.1,
                "master.munger": 0.9,
                "master.graham": 1.0,
            },
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
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=mock_review,
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

            # 验证 review_report 存在
            assert result.review_report is not None
            assert result.review_report.overall_quality == 0.8
            assert result.review_report.independent_rating == "看涨"
            assert len(result.review_report.weight_suggestions) == 3

            # 验证 vote_summary 正常
            vs = result.vote_summary
            assert vs.total_votes == 3

            # review_round 仍然正常
            assert result.review_round is not None

    @pytest.mark.asyncio
    async def test_to_summary_dict_with_d3(self):
        """D3 全流程后 to_summary_dict 包含评审信息"""
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

        mock_review = IndependentReview(
            overall_quality=0.75,
            independent_rating="看涨",
            independent_score=80,
            confidence=0.7,
        )

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=mock_review,
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)
            summary = result.to_summary_dict()
            assert summary["共识"] == "看涨"
            assert summary["参与大师数"] == 1
            assert summary.get("独立评审") is True
            assert summary.get("评审评级") == "看涨"

"""D4 VoteSummary 结构化扩展 —— 单元测试

测试策略（与 D1/D2/D3/M1 测试模式一致）：
- VoteSummary 新字段的模型构造与默认值
- aggregate_node 从 review_report 吸收评审修正字段
- weight_adjustments / review_notes 合成逻辑
- 无 review_report 时的向后兼容行为
- to_summary_dict / model_dump 序列化
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.debate.models import (
    AgentAnalysis,
    DebateResult,
    IndependentReview,
    VoteSummary,
)


# ═══════════════════════════════════════════════════════════════════
# Phase 1: VoteSummary 模型 D4 字段
# ═══════════════════════════════════════════════════════════════════


class TestVoteSummaryD4Fields:
    """VoteSummary 模型 D4 新增字段"""

    def test_new_fields_default_values(self):
        """D4 字段使用安全的默认值（向后兼容）"""
        vs = VoteSummary()
        assert vs.review_score == 0
        assert vs.review_rating == ""
        assert vs.review_quality == 0.0
        assert vs.weight_adjustments == {}
        assert vs.review_notes == ""
        assert vs.consensus_support == 0.5

    def test_new_fields_full_construction(self):
        """全字段构造 D4 字段"""
        vs = VoteSummary(
            total_votes=3,
            rating_distribution={"看涨": 2, "中性": 1},
            average_score=72.0,
            weighted_score=70.5,
            consensus="看涨",
            confidence=0.75,
            direction_distribution={"Bullish": 2, "Neutral": 1},
            review_score=70,
            review_rating="看涨",
            review_quality=0.8,
            weight_adjustments={"master.buffett": 1.2, "master.munger": 0.8},
            review_notes="一致性: 各位大师基本面一致 | 风险综合: 政策风险为主",
            consensus_support=0.65,
        )
        assert vs.review_score == 70
        assert vs.review_rating == "看涨"
        assert vs.review_quality == 0.8
        assert vs.weight_adjustments["master.buffett"] == 1.2
        assert "风险综合" in vs.review_notes
        assert vs.consensus_support == 0.65

    def test_serialization(self):
        """D4 字段的 JSON 序列化与反序列化"""
        vs = VoteSummary(
            total_votes=2,
            rating_distribution={"看跌": 2},
            average_score=45.0,
            weighted_score=44.0,
            consensus="看跌",
            confidence=0.6,
            direction_distribution={"Bearish": 2},
            review_score=40,
            review_rating="看跌",
            review_quality=0.6,
            weight_adjustments={"master.buffett": 1.0, "master.dalio": 0.9},
            review_notes="聚合建议: 建议降权处理",
            consensus_support=0.45,
        )
        dumped = vs.model_dump()
        assert dumped["review_score"] == 40
        assert dumped["review_rating"] == "看跌"
        assert dumped["review_quality"] == 0.6
        assert len(dumped["weight_adjustments"]) == 2
        assert dumped["review_notes"] == "聚合建议: 建议降权处理"
        assert dumped["consensus_support"] == 0.45

        loaded = VoteSummary(**dumped)
        assert loaded.review_score == 40
        assert loaded.weight_adjustments["master.dalio"] == 0.9

    def test_default_fields_still_work(self):
        """原始字段不受 D4 扩展影响"""
        vs = VoteSummary()
        assert vs.total_votes == 0
        assert vs.rating_distribution == {}
        assert vs.average_score == 0.0
        assert vs.weighted_score == 0.0
        assert vs.consensus == "中性"
        assert vs.confidence == 0.0
        assert vs.adjustments_applied is False
        assert vs.direction_distribution == {}

    def test_backward_compatible_deserialization(self):
        """没有 D4 字段的旧数据反序列化时使用默认值"""
        old_data = {
            "total_votes": 3,
            "rating_distribution": {"看涨": 2, "中性": 1},
            "average_score": 70.0,
            "weighted_score": 68.0,
            "consensus": "看涨",
            "confidence": 0.7,
            "adjustments_applied": True,
            "direction_distribution": {"Bullish": 2, "Neutral": 1},
        }
        vs = VoteSummary(**old_data)
        assert vs.total_votes == 3
        assert vs.review_score == 0  # 默认值
        assert vs.review_rating == ""
        assert vs.weight_adjustments == {}
        assert vs.review_notes == ""
        assert vs.consensus_support == 0.5


# ═══════════════════════════════════════════════════════════════════
# Phase 2: DebateResult D4 字段展示
# ═══════════════════════════════════════════════════════════════════


class TestDebateResultD4Fields:
    """DebateResult 中 D4 字段的展示"""

    @pytest.fixture
    def base_result(self) -> DebateResult:
        return DebateResult(
            session_id="test-d4-1",
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
                    summary="看好价值",
                    analysis="详细分析",
                    key_evidence=["护城河"],
                    confidence=0.85,
                    direction="Bullish",
                ),
            ],
            vote_summary=VoteSummary(
                total_votes=1,
                rating_distribution={"看涨": 1},
                average_score=85.0,
                weighted_score=85.0,
                consensus="看涨",
                confidence=0.85,
                direction_distribution={"Bullish": 1},
            ),
        )

    def test_to_summary_dict_without_d4(self, base_result):
        """vote_summary.review_score=0 时 D4 字段不展示"""
        summary = base_result.to_summary_dict()
        assert "评审修正评分" not in summary
        assert "评审修正评级" not in summary
        assert "评审说明" not in summary

    def test_to_summary_dict_with_d4(self, base_result):
        """vote_summary 含 D4 字段时展示"""
        base_result.vote_summary.review_score = 72
        base_result.vote_summary.review_rating = "看涨"
        base_result.vote_summary.review_quality = 0.78
        base_result.vote_summary.weight_adjustments = {
            "master.buffett": 1.1,
        }
        base_result.vote_summary.review_notes = "一致性: 基本一致"
        base_result.vote_summary.consensus_support = 0.6

        summary = base_result.to_summary_dict()
        assert summary.get("评审修正评分") == 72
        assert summary.get("评审修正评级") == "看涨"
        assert summary.get("评审修正质量") == 0.78
        assert summary.get("评审共识支持度") == 0.6
        assert "评审说明" in summary
        assert "权重调整" in summary

    def test_to_summary_dict_with_review_report_and_d4(self, base_result):
        """review_report + D4 字段同时存在时都展示"""
        base_result.review_report = IndependentReview(
            overall_quality=0.8,
            independent_rating="看涨",
            independent_score=78,
        )
        base_result.vote_summary.review_score = 78
        base_result.vote_summary.review_quality = 0.8
        base_result.vote_summary.review_notes = "风险综合: 政策风险"

        summary = base_result.to_summary_dict()
        assert summary.get("独立评审") is True
        assert summary.get("评审质量") == 0.8
        assert summary.get("评审修正评分") == 78
        assert "风险综合" in summary.get("评审说明", "")


# ═══════════════════════════════════════════════════════════════════
# Phase 3: aggregate_node 填充 D4 字段
# ═══════════════════════════════════════════════════════════════════


class TestAggregateD4Fields:
    """aggregate_node 从 review_report 吸收 D4 字段"""

    SAMPLE_ANALYSES = {
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
            direction="Bullish",
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
            direction="Neutral",
        ),
        "master.dalio": AgentAnalysis(
            agent_name="master.dalio",
            skill_id="dalio",
            skill_name="达利欧",
            rating="看跌",
            score=40,
            summary="看空",
            analysis="分析",
            key_evidence=[],
            confidence=0.7,
            direction="Bearish",
        ),
    }

    @pytest.mark.asyncio
    async def test_aggregate_populates_review_fields(self):
        """review_report 存在时 aggregate 正确填充 D4 字段"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-1",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.75,
                "independent_rating": "中性",
                "independent_score": 60,
                "confidence": 0.7,
                "consensus_support": 0.55,
                "quality_assessments": {
                    "master.buffett": "分析充分",
                    "master.munger": "偏保守",
                    "master.dalio": "过于悲观",
                },
                "weight_suggestions": {
                    "master.buffett": 1.1,
                    "master.munger": 1.0,
                    "master.dalio": 0.8,
                },
                "identified_biases": ["共识偏差"],
                "blind_spots": ["汇率风险"],
                "key_risks_synthesis": "政策风险是主要不确定性",
                "consistency_observation": "大师们在基本面判断上基本一致",
                "aggregation_recommendation": "建议以巴菲特评分为基准",
                "latency_ms": 500,
            },
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        # D4 字段验证
        assert vs.review_score == 60
        assert vs.review_rating == "中性"
        assert vs.review_quality == 0.75
        assert vs.consensus_support == 0.55

        # weight_adjustments 继承自 review_report.weight_suggestions
        assert len(vs.weight_adjustments) == 3
        assert vs.weight_adjustments["master.buffett"] == 1.1
        assert vs.weight_adjustments["master.dalio"] == 0.8

        # review_notes 合成（含一致性 + 风险 + 聚合建议）
        assert "一致性" in vs.review_notes
        assert "风险综合" in vs.review_notes
        assert "聚合建议" in vs.review_notes
        assert "发现偏差" in vs.review_notes

        # 原始字段不受影响
        assert vs.total_votes == 3
        assert vs.average_score == 60.0
        assert vs.consensus == "看涨"

    @pytest.mark.asyncio
    async def test_aggregate_with_partial_review(self):
        """review_report 部分字段缺失时 D4 字段使用默认值"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-2",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.6,
                "independent_rating": "看涨",
                "independent_score": 65,
                "confidence": 0.5,
                # 无 weight_suggestions、consensus_support 等
            },
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        assert vs.review_score == 65
        assert vs.review_rating == "看涨"
        assert vs.review_quality == 0.6
        assert vs.weight_adjustments == {}  # 无则空
        assert vs.review_notes == ""  # 无文本字段则空
        assert vs.consensus_support == 0.5  # 默认值

    @pytest.mark.asyncio
    async def test_aggregate_without_review_report(self):
        """无 review_report 时 D4 字段全部使用默认值（向后兼容）"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-3",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {},  # 空字典 = 无评审
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        # D4 默认值
        assert vs.review_score == 0
        assert vs.review_rating == ""
        assert vs.review_quality == 0.0
        assert vs.weight_adjustments == {}
        assert vs.review_notes == ""
        assert vs.consensus_support == 0.5

        # 原始字段正常
        assert vs.total_votes == 3
        assert vs.average_score == 60.0

    @pytest.mark.asyncio
    async def test_aggregate_with_review_report_error(self):
        """review_report 解析失败时 D4 字段使用默认值"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-4",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": "无效值",  # 应该是 float，类型不匹配会导致解析异常
            },
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        # 解析失败 -> 默认值
        # 注意: Pydantic 的 strict mode 下类型不匹配会抛异常，
        # 但默认宽松模式会尝试转换。如果 "无效值" 转为 float 失败，
        # IndependentReview(**data) 抛异常 -> 走 except 分支 -> 默认值
        assert vs.review_score == 0
        assert vs.review_rating == ""
        assert vs.review_quality == 0.0
        assert vs.review_notes == ""
        assert vs.consensus_support == 0.5

    @pytest.mark.asyncio
    async def test_review_notes_merges_multiple_sources(self):
        """review_notes 正确合并多个评审文本来源"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-5",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.7,
                "independent_rating": "中性",
                "independent_score": 55,
                "confidence": 0.6,
                "consistency_observation": "各位大师在风险评估上观点大致一致",
                "key_risks_synthesis": "行业政策不确定性是最大风险",
                "aggregation_recommendation": "建议给巴菲特更高权重",
                "identified_biases": ["对乐观情绪过度强调", "低估了竞争压力"],
            },
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        assert "一致性" in vs.review_notes
        assert "风险评估" in vs.review_notes
        assert "风险综合" in vs.review_notes
        assert "行业政策不确定性" in vs.review_notes
        assert "聚合建议" in vs.review_notes
        assert "巴菲特" in vs.review_notes
        assert "发现偏差" in vs.review_notes
        assert "乐观情绪" in vs.review_notes

    @pytest.mark.asyncio
    async def test_consensus_support_rounded(self):
        """consensus_support 被 round 到 2 位小数"""
        from src.debate.orchestrator import DebateState, aggregate_node

        state: DebateState = {
            "session_id": "test-d4-aggr-6",
            "debate_input": {},
            "current_round": 2,
            "analyses": self.SAMPLE_ANALYSES,
            "market_data": {},
            "vote_summary": {},
            "review_round": {},
            "review_report": {
                "reviewer_style": "independent_reviewer",
                "overall_quality": 0.7,
                "independent_rating": "中性",
                "independent_score": 55,
                "confidence": 0.6,
                "consensus_support": 0.6666667,
            },
            "errors": [],
        }

        result = await aggregate_node(state)
        vs: VoteSummary = result["vote_summary"]

        assert vs.consensus_support == 0.67  # round(0.6666667, 2)


# ═══════════════════════════════════════════════════════════════════
# Phase 4: 全流程集成测试（mock Graph 层）
# ═══════════════════════════════════════════════════════════════════


class TestD4Integration:
    """D4 全流程集成测试"""

    @pytest.mark.asyncio
    async def test_debate_result_includes_d4_fields(self):
        """完整辩论结果包含 D4 字段"""
        from src.debate.orchestrator import DebateOrchestrator

        result = DebateResult(
            session_id="test-d4-int-1",
            stock_code="000001",
            stock_name="平安银行",
            question="测试问题",
            analyses=[
                AgentAnalysis(
                    agent_name="master.test",
                    skill_id="test",
                    skill_name="测试大师",
                    rating="看涨",
                    score=80,
                    summary="测试",
                    analysis="测试分析",
                    confidence=0.8,
                    direction="Bullish",
                ),
            ],
            vote_summary=VoteSummary(
                total_votes=1,
                rating_distribution={"看涨": 1},
                average_score=80.0,
                weighted_score=80.0,
                consensus="看涨",
                confidence=0.8,
                direction_distribution={"Bullish": 1},
                review_score=75,
                review_rating="看涨",
                review_quality=0.78,
                weight_adjustments={"master.test": 1.0},
                review_notes="一致性: 基本一致",
                consensus_support=0.62,
            ),
        )

        assert result.vote_summary.review_score == 75
        assert result.vote_summary.review_quality == 0.78
        assert result.vote_summary.weight_adjustments["master.test"] == 1.0

        # 序列化反序列化
        dumped = result.model_dump()
        loaded = DebateResult(**dumped)
        assert loaded.vote_summary.review_score == 75
        assert loaded.vote_summary.review_notes == "一致性: 基本一致"

        # to_summary_dict
        summary = loaded.to_summary_dict()
        assert summary.get("评审修正评分") == 75
        assert summary.get("评审共识支持度") == 0.62

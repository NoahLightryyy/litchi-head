"""辩论数据契约单元测试"""

from __future__ import annotations

import json

from src.debate.models import (
    AgentAnalysis,
    DebateInput,
    DebateResult,
    VoteSummary,
)


class TestDebateInput:
    """DebateInput 构造与默认值"""

    def test_minimal_construction(self):
        """最少字段构造"""
        inp = DebateInput(stock_code="000001")
        assert inp.stock_code == "000001"
        assert inp.stock_name == ""
        assert inp.question == "请分析这只股票的投资价值"
        assert inp.session_id != ""

    def test_full_construction(self):
        """全字段构造"""
        inp = DebateInput(
            stock_code="600519",
            stock_name="贵州茅台",
            question="现在可以买入吗？",
            session_id="custom-id",
        )
        assert inp.stock_code == "600519"
        assert inp.stock_name == "贵州茅台"
        assert inp.question == "现在可以买入吗？"
        assert inp.session_id == "custom-id"

    def test_auto_session_id(self):
        """每次构造应生成唯一 session_id"""
        inp1 = DebateInput(stock_code="000001")
        inp2 = DebateInput(stock_code="000001")
        assert inp1.session_id != inp2.session_id

    def test_serialization(self):
        """JSON 序列化/反序列化"""
        inp = DebateInput(stock_code="000001", stock_name="平安银行")
        dumped = inp.model_dump()
        assert dumped["stock_code"] == "000001"
        loaded = DebateInput(**dumped)
        assert loaded.stock_name == "平安银行"
        assert loaded.session_id == inp.session_id


class TestAgentAnalysis:
    """AgentAnalysis 构造与状态"""

    def test_success_analysis(self):
        """成功的分析"""
        a = AgentAnalysis(
            agent_name="test_agent",
            skill_id="buffett",
            skill_name="沃伦·巴菲特",
            rating="看涨",
            score=85,
            summary="看好长期增长",
            analysis="详细分析内容",
            key_evidence=["护城河强大", "现金流充沛"],
            confidence=0.85,
        )
        assert a.agent_name == "test_agent"
        assert a.success is True
        assert a.error is None
        assert a.latency_ms == 0.0

    def test_failed_analysis(self):
        """失败的分析"""
        a = AgentAnalysis(
            agent_name="fail_agent",
            skill_id="test",
            skill_name="测试",
            rating="中性",
            score=0,
            summary="",
            analysis="",
            key_evidence=[],
            confidence=0.0,
            success=False,
            error="LLM 调用超时",
            latency_ms=120000.0,
        )
        assert a.success is False
        assert a.error == "LLM 调用超时"
        assert a.latency_ms == 120000.0

    def test_serialization(self):
        """JSON 序列化"""
        a = AgentAnalysis(
            agent_name="buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=90,
            summary="核心观点",
            analysis="详细分析",
            key_evidence=["证据1", "证据2", "证据3"],
            risk_warning="注意风险",
            confidence=0.9,
        )
        dumped = a.model_dump()
        assert dumped["rating"] == "看涨"
        assert dumped["risk_warning"] == "注意风险"
        assert len(dumped["key_evidence"]) == 3

        json_str = json.dumps(dumped, ensure_ascii=False)
        loaded_dict = json.loads(json_str)
        assert loaded_dict["skill_name"] == "巴菲特"


class TestVoteSummary:
    """VoteSummary 聚合逻辑"""

    def test_single_consensus(self):
        """单个分析的结果"""
        vs = VoteSummary(
            total_votes=1,
            rating_distribution={"看涨": 1},
            average_score=85.0,
            weighted_score=85.0,
            consensus="看涨",
            confidence=0.85,
        )
        assert vs.total_votes == 1
        assert vs.consensus == "看涨"

    def test_majority_consensus(self):
        """多数决共识"""
        vs = VoteSummary(
            total_votes=5,
            rating_distribution={"看涨": 3, "中性": 1, "看跌": 1},
            average_score=72.4,
            weighted_score=70.1,
            consensus="看涨",
            confidence=0.75,
        )
        assert vs.total_votes == 5
        assert vs.rating_distribution["看涨"] == 3

    def test_serialization(self):
        """JSON 序列化"""
        vs = VoteSummary(
            total_votes=3,
            rating_distribution={"看涨": 2, "看跌": 1},
            average_score=65.0,
            weighted_score=63.5,
            consensus="看涨",
            confidence=0.7,
        )
        dumped = vs.model_dump()
        assert dumped["consensus"] == "看涨"
        json_str = json.dumps(dumped, ensure_ascii=False)
        loaded = VoteSummary(**json.loads(json_str))
        assert loaded.average_score == 65.0


class TestDebateResult:
    """DebateResult 完整构造"""

    def test_full_result(self):
        """完整的辩论结果"""
        analyses = [
            AgentAnalysis(
                agent_name="master.buffett",
                skill_id="buffett",
                skill_name="巴菲特",
                rating="看涨",
                score=85,
                summary="看好",
                analysis="分析...",
                key_evidence=["护城河"],
                confidence=0.85,
            ),
            AgentAnalysis(
                agent_name="master.munger",
                skill_id="munger",
                skill_name="芒格",
                rating="中性",
                score=60,
                summary="谨慎",
                analysis="分析...",
                key_evidence=["不确定性高"],
                confidence=0.6,
            ),
        ]
        vote = VoteSummary(
            total_votes=2,
            rating_distribution={"看涨": 1, "中性": 1},
            average_score=72.5,
            weighted_score=72.5,
            consensus="看涨",
            confidence=0.75,
        )
        result = DebateResult(
            session_id="s1",
            stock_code="000001",
            stock_name="平安银行",
            question="是否值得投资",
            analyses=analyses,
            vote_summary=vote,
            total_latency_ms=3500.0,
        )
        assert len(result.analyses) == 2
        assert result.vote_summary.total_votes == 2
        assert result.total_latency_ms == 3500.0

    def test_serialization(self):
        """完整 JSON 序列化"""
        analyses = [
            AgentAnalysis(
                agent_name="master.buffett",
                skill_id="buffett",
                skill_name="巴菲特",
                rating="看涨",
                score=85,
                summary="看好",
                analysis="分析内容",
                key_evidence=["护城河"],
                confidence=0.85,
            )
        ]
        vote = VoteSummary(
            total_votes=1,
            rating_distribution={"看涨": 1},
            average_score=85.0,
            weighted_score=85.0,
            consensus="看涨",
            confidence=0.85,
        )
        result = DebateResult(
            session_id="s1",
            stock_code="000001",
            stock_name="平安银行",
            question="是否值得投资",
            analyses=analyses,
            vote_summary=vote,
            total_latency_ms=1200.0,
        )
        dumped = result.model_dump()
        assert len(dumped["analyses"]) == 1
        assert dumped["vote_summary"]["consensus"] == "看涨"

        json_str = json.dumps(dumped, ensure_ascii=False)
        loaded = DebateResult(**json.loads(json_str))
        assert loaded.stock_code == "000001"
        assert loaded.analyses[0].skill_id == "buffett"

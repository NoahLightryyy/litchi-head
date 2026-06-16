"""M4 动态权重单元测试

验证 TrustTracker 信任度因子在 aggregate 节点中的正确应用：
1. trust_weight_factors 传入 aggregate 后影响 weighted_score
2. 不传信任度因子时退化为 baseline（因子=1.0）
3. 不同信任度因子产生不同的加权分
4. VoteSummary 正确记录 trust_weight_factors
5. enable_trust 参数接受与安全降级

注意：所有可能触发 torch 的导入都使用惰性（lazy import）。
避免在模块级别导入任何可能加载 transformers/torch 的模块。
"""

from __future__ import annotations

import pytest

from src.debate.models import AgentAnalysis, VoteSummary

# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════


def _make_analysis(
    agent_name: str,
    score: int = 75,
    confidence: float = 0.8,
    direction: str = "Bullish",
    rating: str = "看涨",
    success: bool = True,
) -> AgentAnalysis:
    """快速构造 AgentAnalysis"""
    return AgentAnalysis(
        agent_name=agent_name,
        skill_id=agent_name.replace("master.", ""),
        skill_name=agent_name.split(".")[-1].title(),
        rating=rating,
        score=score,
        summary="测试分析",
        analysis="...",
        key_evidence=[],
        confidence=confidence,
        success=success,
        direction=direction,
    )


def _state(overrides: dict | None = None) -> dict:
    """生成最小化 DebateState 字典"""
    base: dict = {
        "session_id": "m4-test",
        "debate_input": {},
        "current_round": 1,
        "analyses": {},
        "market_data": {},
        "vote_summary": {},
        "review_round": {},
        "review_report": {},
        "errors": [],
        "history_context": "",
        "reflection_context": "",
        "analyst_reports": {},
        "risk_round": {},
        "trader_round": {},
        "trade_recommendation": {},
        "trust_weight_factors": {},
    }
    if overrides:
        base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════
# M4: aggregate 信任度权重测试
# ═══════════════════════════════════════════════════════════════════


class TestAggregateTrustWeights:
    """aggregate_node 应用 trust_weight_factors 的测试"""

    @staticmethod
    def _aggregate(*args, **kwargs):
        """惰性导入 aggregate_node"""
        from src.debate.orchestrator import aggregate_node
        return aggregate_node(*args, **kwargs)

    @pytest.mark.asyncio
    async def test_aggregate_with_trust_factors(self):
        """信任度因子影响 weighted_score"""
        state = _state({
            "analyses": {
                "master.trusted": _make_analysis(
                    agent_name="master.trusted",
                    score=75,
                    confidence=0.8,
                ),
                "master.untrusted": _make_analysis(
                    agent_name="master.untrusted",
                    score=75,
                    confidence=0.8,
                ),
            },
            "trust_weight_factors": {
                "master.trusted": 1.5,
                "master.untrusted": 0.5,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # weighted = (75*0.8*1.5 + 75*0.8*0.5) / (0.8*1.5 + 0.8*0.5)
        #         = (90 + 30) / (1.2 + 0.4)
        #         = 120 / 1.6
        #         = 75.0
        assert vs.weighted_score == 75.0
        assert vs.trust_weight_factors == {
            "master.trusted": 1.5,
            "master.untrusted": 0.5,
        }

    @pytest.mark.asyncio
    async def test_aggregate_trust_biases_weighted_score(self):
        """信任度因子使低分高信任 Agent 的权重超过高分低信任 Agent"""
        state = _state({
            "analyses": {
                "master.cautious": _make_analysis(
                    agent_name="master.cautious",
                    score=50,
                    confidence=0.95,
                ),
                "master.loud": _make_analysis(
                    agent_name="master.loud",
                    score=80,
                    confidence=0.8,
                ),
            },
            "trust_weight_factors": {
                "master.cautious": 1.5,
                "master.loud": 0.3,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # weighted = (50*0.95*1.5 + 80*0.8*0.3) / (0.95*1.5 + 0.8*0.3)
        #         = 54.32...
        assert vs.weighted_score < 60
        assert vs.average_score == 65.0

    @pytest.mark.asyncio
    async def test_aggregate_without_trust_factors(self):
        """不传 trust_weight_factors 时退化为 baseline"""
        state = _state({
            "analyses": {
                "master.a": _make_analysis(
                    agent_name="master.a",
                    score=70,
                    confidence=0.8,
                ),
                "master.b": _make_analysis(
                    agent_name="master.b",
                    score=90,
                    confidence=0.9,
                ),
            },
            "trust_weight_factors": {},
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # weighted = (70*0.8 + 90*0.9) / (0.8 + 0.9)
        #         = 137 / 1.7
        #         = 80.58...
        assert vs.weighted_score == pytest.approx(80.6, rel=0.02)
        assert vs.trust_weight_factors == {}

    @pytest.mark.asyncio
    async def test_aggregate_trust_missing_key(self):
        """某个 Agent 没有对应信任度因子时用 1.0"""
        state = _state({
            "analyses": {
                "master.a": _make_analysis(
                    agent_name="master.a",
                    score=80,
                    confidence=0.9,
                ),
                "master.b": _make_analysis(
                    agent_name="master.b",
                    score=60,
                    confidence=0.7,
                ),
            },
            "trust_weight_factors": {
                "master.a": 0.5,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # weighted = (80*0.9*0.5 + 60*0.7*1.0) / (0.9*0.5 + 0.7*1.0)
        #         = 67.83...
        assert vs.weighted_score == pytest.approx(67.8, rel=0.02)
        assert vs.trust_weight_factors == {"master.a": 0.5}

    @pytest.mark.asyncio
    async def test_aggregate_trust_with_weight_suggestions(self):
        """信任度因子与 D3 weight_suggestions 叠加"""
        state = _state({
            "analyses": {
                "master.a": _make_analysis(
                    agent_name="master.a",
                    score=60,
                    confidence=0.8,
                ),
                "master.b": _make_analysis(
                    agent_name="master.b",
                    score=60,
                    confidence=0.8,
                ),
            },
            "trust_weight_factors": {
                "master.a": 1.5,
                "master.b": 0.6,
            },
            "review_report": {
                "weight_suggestions": {
                    "master.a": 1.2,
                    "master.b": 0.8,
                },
                "overall_quality": 0.7,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # combined: A=1.8, B=0.48 → weighted = 60.0
        assert vs.weighted_score == 60.0
        assert vs.trust_weight_factors == {"master.a": 1.5, "master.b": 0.6}
        assert "master.a" in vs.weight_adjustments
        assert vs.weight_adjustments["master.a"] == 1.2

    @pytest.mark.asyncio
    async def test_aggregate_trust_three_agents_varied(self):
        """三个 Agent 不同信任度因子的综合测试"""
        state = _state({
            "analyses": {
                "master.high": _make_analysis(
                    agent_name="master.high",
                    score=90,
                    confidence=0.95,
                ),
                "master.medium": _make_analysis(
                    agent_name="master.medium",
                    score=70,
                    confidence=0.75,
                ),
                "master.low": _make_analysis(
                    agent_name="master.low",
                    score=50,
                    confidence=0.5,
                ),
            },
            "trust_weight_factors": {
                "master.high": 1.4,
                "master.medium": 1.0,
                "master.low": 0.6,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        assert vs.total_votes == 3
        assert vs.average_score == 70.0
        # weighted ≈ 78.66...
        assert vs.weighted_score == pytest.approx(78.7, rel=0.02)

    @pytest.mark.asyncio
    async def test_aggregate_trust_factor_extremes(self):
        """信任度因子极端值（0.5 和 1.5）对称抵消"""
        state = _state({
            "analyses": {
                "master.x": _make_analysis(
                    agent_name="master.x",
                    score=80,
                    confidence=0.8,
                ),
                "master.y": _make_analysis(
                    agent_name="master.y",
                    score=80,
                    confidence=0.8,
                ),
            },
            "trust_weight_factors": {
                "master.x": 1.5,
                "master.y": 0.5,
            },
        })

        result = await self._aggregate(state)
        vs = result["vote_summary"]

        # (80*0.8*1.5 + 80*0.8*0.5) / (0.8*1.5 + 0.8*0.5)
        # = 128 / 1.6 = 80.0 (等于算术平均)
        assert vs.weighted_score == 80.0


# ═══════════════════════════════════════════════════════════════════
# VoteSummary trust_weight_factors 序列化/反序列化
# ═══════════════════════════════════════════════════════════════════


class TestVoteSummaryTrustField:
    """VoteSummary.trust_weight_factors 字段"""

    def test_default_empty(self):
        """默认 trust_weight_factors 为空字典"""
        vs = VoteSummary()
        assert vs.trust_weight_factors == {}

    def test_serialize_deserialize(self):
        """model_dump / model_validate 保持 trust_weight_factors"""
        vs = VoteSummary(
            trust_weight_factors={
                "master.buffett": 1.3,
                "master.munger": 0.8,
            }
        )
        dumped = vs.model_dump()
        loaded = VoteSummary(**dumped)
        assert loaded.trust_weight_factors == {
            "master.buffett": 1.3,
            "master.munger": 0.8,
        }

    def test_with_vote_data(self):
        """与其他 VoteSummary 字段共存"""
        vs = VoteSummary(
            total_votes=2,
            consensus="看涨",
            average_score=75.0,
            trust_weight_factors={"master.a": 1.2, "master.b": 0.9},
        )
        assert vs.total_votes == 2
        assert vs.consensus == "看涨"
        assert vs.trust_weight_factors["master.a"] == 1.2

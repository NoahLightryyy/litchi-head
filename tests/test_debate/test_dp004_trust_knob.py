"""DP-004 TrustTracker 旋钮扩展测试

测试：
1. 大师按信任度权重排序（高信任先发言）
2. 低信任度大师跳过辩论
"""

from unittest.mock import MagicMock, patch

import pytest

from src.debate.models import AgentAnalysis
from src.debate.orchestrator import DebateState, make_master_round_node


def _make_mock_analysis(agent_name: str) -> dict:
    """创建模拟的 AgentAnalysis"""
    return AgentAnalysis(
        agent_name=agent_name,
        skill_id=agent_name.replace("master.", ""),
        skill_name=agent_name.replace("master.", ""),
        rating="看涨",
        score=70,
        summary="mock",
        analysis="mock analysis",
        confidence=0.7,
        direction="Bullish",
        success=True,
        latency_ms=100,
    )


class TestMasterRoundNodeDP004:
    """DP-004: master_round 信任度排序 + 跳过"""

    @pytest.fixture
    def state_with_trust(self) -> DebateState:
        """含 trust_weight_factors 的辩论状态"""
        return {
            "debate_input": {"stock_code": "000001", "stock_name": "平安银行", "question": "分析"},
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
            "trust_weight_factors": {
                "master.high_trust": 1.4,
                "master.medium_trust": 1.0,
                "master.low_trust": 0.5,
            },
            "calibration_map": {},
        }

    @patch("src.debate.orchestrator._run_single_master")
    def test_master_round_skips_low_trust(self, mock_run, state_with_trust):
        """信任度低于阈值的应跳过"""
        mock_run.return_value = AgentAnalysis(
            agent_name="mock", skill_id="mock", skill_name="mock",
            rating="看涨", score=70, summary="", analysis="",
            confidence=0.7, direction="Bullish", success=True, latency_ms=10,
        )

        skills = [
            MagicMock(skill_id="high_trust"),
            MagicMock(skill_id="medium_trust"),
            MagicMock(skill_id="low_trust"),
        ]
        node_fn = make_master_round_node(skills, min_trust_factor=0.7)
        import asyncio
        result = asyncio.run(node_fn(state_with_trust))

        # low_trust 被跳过，所以不应出现在 analyses 中
        analyses = result.get("analyses", {})
        assert "master.low_trust" not in analyses
        assert "master.high_trust" in analyses
        assert "master.medium_trust" in analyses

    @patch("src.debate.orchestrator._run_single_master")
    def test_master_round_no_trust_factors(self, mock_run):
        """无 trust_weight_factors 时应正常运行所有大师（默认权重 1.0，均通过阈值）"""
        mock_run.return_value = AgentAnalysis(
            agent_name="mock", skill_id="mock", skill_name="mock",
            rating="中性", score=50, summary="", analysis="",
            confidence=0.5, direction="Neutral", success=True, latency_ms=10,
        )

        state: DebateState = {
            "debate_input": {"stock_code": "000001", "stock_name": "平安银行", "question": "分析"},
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
            "calibration_map": {},
        }
        skills = [MagicMock(skill_id="a"), MagicMock(skill_id="b")]
        node_fn = make_master_round_node(skills, min_trust_factor=0.7)
        import asyncio
        result = asyncio.run(node_fn(state))

        analyses = result.get("analyses", {})
        # 没有 trust_factors 时所有大师默认权重 1.0，全部参与
        # (1.0 >= 0.7 所以通过)
        assert "master.a" in analyses
        assert "master.b" in analyses


class TestDebateOrchestratorDP004:
    """DebateOrchestrator DP-004 配置测试"""

    def test_default_min_trust_factor(self):
        """默认 min_trust_factor 应为 0.7"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator()
        assert orch.min_trust_factor == 0.7

    def test_custom_min_trust_factor(self):
        """可自定义 min_trust_factor"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(min_trust_factor=0.5)
        assert orch.min_trust_factor == 0.5

    def test_enable_trust_sets_threshold(self):
        """启用 trust 时使用自定义阈值"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_trust=True, min_trust_factor=0.8)
        assert orch.enable_trust is True
        assert orch.min_trust_factor == 0.8

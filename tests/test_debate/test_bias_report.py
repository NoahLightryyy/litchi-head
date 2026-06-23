"""DP-003 偏斜公示 —— BiasReport 模型测试

覆盖所有共识场景：集体看涨、看跌、分歧、全体观望等。
"""

import pytest

from pydantic import TypeAdapter

from src.debate.models import BiasReport, VoteSummary


class TestBiasReportDefaults:
    """BiasReport 默认值和基本行为"""

    def test_default_construction(self) -> None:
        """默认构造全部为零/中性"""
        r = BiasReport()
        assert r.total_count == 0
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 0.0
        assert r.consensus_type == "Neutral"

    def test_ratios_are_independent_fields(self) -> None:
        """ratio 字段是独立存储的，不通过计算推导"""
        r = BiasReport(
            bullish_count=4, bearish_count=1, neutral_count=1, total_count=6,
            bullish_ratio=4/6, bearish_ratio=1/6, neutral_ratio=1/6,
            overall_bias=0.5, consensus_strength=4/6, consensus_type="Bullish",
        )
        assert r.bullish_count == 4
        assert r.bearish_count == 1
        assert r.neutral_count == 1
        assert r.total_count == 6


class TestBiasReportConsensusType:
    """共识类型判定测试"""

    def test_strong_bullish(self) -> None:
        """看涨超过半数 → consensus_type=Bullish"""
        r = BiasReport(
            bullish_count=5, bearish_count=0, neutral_count=1, total_count=6,
            bullish_ratio=5/6, bearish_ratio=0.0, neutral_ratio=1/6,
            overall_bias=5/6, consensus_strength=5/6, consensus_type="Bullish",
        )
        assert r.consensus_type == "Bullish"
        assert r.overall_bias == pytest.approx(0.8333, abs=0.001)

    def test_strong_bearish(self) -> None:
        """看跌超过半数 → consensus_type=Bearish"""
        r = BiasReport(
            bullish_count=1, bearish_count=4, neutral_count=1, total_count=6,
            overall_bias=-0.5, consensus_strength=4/6, consensus_type="Bearish",
        )
        assert r.consensus_type == "Bearish"
        assert r.overall_bias == -0.5

    @pytest.mark.parametrize("b,bull,bear,neut", [
        ("all_neutral",  0, 0, 6),
        ("neutral_7",    1, 2, 7),
    ])
    def test_neutral_majority(
        self, b: str, bull: int, bear: int, neut: int,
    ) -> None:
        """中性超过半数 → consensus_type=Neutral"""
        total = bull + bear + neut
        r = BiasReport(
            bullish_count=bull, bearish_count=bear, neutral_count=neut,
            total_count=total,
            overall_bias=(bull - bear) / total,
            consensus_strength=neut / total,
            consensus_type="Neutral",
        )
        assert r.consensus_type == "Neutral"

    def test_divided_consensus(self) -> None:
        """无任一过半 → Divided"""
        r = BiasReport(
            bullish_count=2, bearish_count=2, neutral_count=2, total_count=6,
            overall_bias=0.0, consensus_strength=2/6,
            consensus_type="Divided",
        )
        assert r.consensus_type == "Divided"

    def test_one_analyst_bullish(self) -> None:
        """仅一位分析师且看涨"""
        r = BiasReport(
            bullish_count=1, bearish_count=0, neutral_count=0, total_count=1,
            overall_bias=1.0, consensus_strength=1.0, consensus_type="Bullish",
        )
        assert r.overall_bias == 1.0
        assert r.consensus_strength == 1.0

    def test_one_analyst_neutral(self) -> None:
        """仅一位分析师且中性"""
        r = BiasReport(
            bullish_count=0, bearish_count=0, neutral_count=1, total_count=1,
            overall_bias=0.0, consensus_strength=1.0, consensus_type="Neutral",
        )
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 1.0


class TestBiasReportScenarios:
    """真实投决场景验证"""

    def test_strongly_optimistic(self) -> None:
        """5 看涨 0 看跌 1 观望 → 高度乐观"""
        r = BiasReport(
            bullish_count=5, bearish_count=0, neutral_count=1, total_count=6,
            overall_bias=(5-0)/6, consensus_strength=5/6,
            consensus_type="Bullish",
        )
        assert r.consensus_type == "Bullish"
        assert r.overall_bias == pytest.approx(0.8333, abs=0.001)
        assert r.neutral_count == 1

    def test_cautious_market(self) -> None:
        """0 看涨 0 看跌 6 观望 → 全体谨慎"""
        r = BiasReport(
            bullish_count=0, bearish_count=0, neutral_count=6, total_count=6,
            overall_bias=0.0, consensus_strength=1.0,
            consensus_type="Neutral",
        )
        assert r.consensus_type == "Neutral"
        assert r.consensus_strength == 1.0  # 高度一致 = 全体谨慎

    def test_deep_split(self) -> None:
        """3 看涨 3 看跌 0 观望 → 深度分歧"""
        r = BiasReport(
            bullish_count=3, bearish_count=3, neutral_count=0, total_count=6,
            overall_bias=0.0, consensus_strength=3/6,
            consensus_type="Divided",
        )
        assert r.consensus_type == "Divided"
        assert r.overall_bias == 0.0
        assert r.consensus_strength == 0.5

    def test_leaning_bearish(self) -> None:
        """1 看涨 4 看跌 1 观望 → 偏悲观"""
        r = BiasReport(
            bullish_count=1, bearish_count=4, neutral_count=1, total_count=6,
            overall_bias=(1-4)/6, consensus_strength=4/6,
            consensus_type="Bearish",
        )
        assert r.consensus_type == "Bearish"
        assert r.overall_bias == pytest.approx(-0.5, abs=0.001)


class TestVoteSummaryBiasIntegration:
    """VoteSummary 与 BiasReport 集成测试"""

    def test_default_bias_report_on_vote_summary(self) -> None:
        """VoteSummary 默认构造包含空的 BiasReport"""
        vs = VoteSummary()
        assert vs.bias_report.total_count == 0
        assert vs.bias_report.overall_bias == 0.0
        assert vs.bias_report.consensus_type == "Neutral"

    def test_vote_summary_with_populated_bias_report(self) -> None:
        """VoteSummary 可携带非默认 BiasReport"""
        br = BiasReport(
            bullish_count=4, bearish_count=1, neutral_count=1, total_count=6,
            bullish_ratio=4/6, bearish_ratio=1/6, neutral_ratio=1/6,
            overall_bias=0.5, consensus_strength=4/6, consensus_type="Bullish",
        )
        vs = VoteSummary(bias_report=br)
        assert vs.bias_report.bullish_count == 4
        assert vs.bias_report.overall_bias == 0.5
        assert vs.bias_report.consensus_type == "Bullish"

    def test_vote_summary_json_roundtrip(self) -> None:
        """VoteSummary JSON 序列化/反序列化保留 BiasReport"""
        br = BiasReport(
            bullish_count=3, bearish_count=2, neutral_count=1, total_count=6,
            bullish_ratio=0.5, bearish_ratio=1/3, neutral_ratio=1/6,
            overall_bias=1/6, consensus_strength=0.5, consensus_type="Divided",
        )
        vs = VoteSummary(bias_report=br)
        json_str = vs.model_dump_json()
        restored = TypeAdapter(VoteSummary).validate_json(json_str)
        assert restored.bias_report.bullish_count == 3
        assert restored.bias_report.consensus_type == "Divided"
        assert restored.bias_report.overall_bias == pytest.approx(1/6, abs=0.001)

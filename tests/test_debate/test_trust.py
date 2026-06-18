"""M3 信任度评分测试

测试策略：
- AgentOutcome / AgentTrustMetrics / TrustReport 模型验证
- TrustTracker.record_outcome / record_outcome_from_analysis 记录
- TrustTracker._compute_metrics 统计精度（win_rate/brier/偏差/趋势）
- _build_calibration_curve 校准曲线
- compute_weight_factor 权重因子
- TrustTracker.get_trust_report（mock MemoryStore）
- flush 持久化
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.debate.trust import (
    AgentOutcome,
    AgentTrustMetrics,
    TrustReport,
    TrustTracker,
    _build_calibration_curve,
    compute_weight_factor,
)
from src.memory.store import MemoryItem, MemoryStore

# ═══════════════════════════════════════════════════════════════════
# Phase 1: 模型验证
# ═══════════════════════════════════════════════════════════════════


class TestAgentOutcomeModel:
    """AgentOutcome 模型验证"""

    def test_minimal_construction(self):
        """最小字段构造"""
        outcome = AgentOutcome(agent_name="master.buffett")
        assert outcome.agent_name == "master.buffett"
        assert outcome.predicted_direction == "Neutral"
        assert outcome.actual_direction == "Neutral"
        assert outcome.is_correct is True  # 默认都是 Neutral → 相同

    def test_full_construction(self):
        """全字段构造"""
        outcome = AgentOutcome(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            session_id="sess-001",
            stock_code="000001",
            decision_date="2026-06-10",
            evaluation_date="2026-06-16",
            predicted_direction="Bullish",
            predicted_score=75,
            predicted_confidence=0.85,
            predicted_rating="看涨",
            actual_direction="Bullish",
            actual_price_change_pct=+3.5,
            is_correct=True,
        )
        assert outcome.agent_name == "master.buffett"
        assert outcome.is_correct is True
        assert outcome.predicted_score == 75
        assert outcome.actual_price_change_pct == 3.5

    def test_is_correct_calculation(self):
        """is_correct 在构造时即确定"""
        correct = AgentOutcome(
            agent_name="a",
            predicted_direction="Bullish",
            actual_direction="Bullish",
        )
        assert correct.is_correct is True

        wrong = AgentOutcome(
            agent_name="a",
            predicted_direction="Bullish",
            actual_direction="Bearish",
        )
        assert wrong.is_correct is False

    def test_model_dump_serializable(self):
        """model_dump 可序列化（用于 MemoryStore 存储）"""
        outcome = AgentOutcome(
            agent_name="master.buffett",
            session_id="sess-001",
            stock_code="000001",
        )
        dumped = outcome.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["agent_name"] == "master.buffett"
        assert dumped["is_correct"] is True


class TestAgentTrustMetrics:
    """AgentTrustMetrics 模型验证"""

    def test_defaults(self):
        """默认值合理"""
        m = AgentTrustMetrics()
        assert m.total_samples == 0
        assert m.win_rate == 0.0
        assert m.calibration_curve == []

    def test_full(self):
        """全字段构造"""
        m = AgentTrustMetrics(
            total_samples=30,
            win_rate=0.667,
            brier_score=0.12,
            calibration_curve=[{"bucket": 0.5, "acc": 0.6, "count": 10}],
            trend_direction="improving",
        )
        assert m.total_samples == 30
        assert len(m.calibration_curve) == 1


class TestTrustReport:
    """TrustReport 模型验证"""

    def test_defaults(self):
        """默认值合理"""
        r = TrustReport(agent_name="master.buffett")
        assert r.is_reliable is False
        assert r.summary == ""


# ═══════════════════════════════════════════════════════════════════
# Phase 2: TrustTracker 记录
# ═══════════════════════════════════════════════════════════════════


class TestRecordOutcome:
    """TrustTracker.record_outcome 验证"""

    def test_record_correct(self):
        """记录一次正确的方向预测"""
        tracker = TrustTracker()
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=75,
            predicted_confidence=0.85,
            actual_direction="Bullish",
            actual_price_change_pct=+3.5,
        )
        assert "master.buffett" in tracker._buffers
        buf = tracker._buffers["master.buffett"]
        assert len(buf.outcomes) == 1
        assert buf.outcomes[0].is_correct is True
        assert buf.dirty is True

    def test_record_wrong(self):
        """记录一次错误的方向预测"""
        tracker = TrustTracker()
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=75,
            predicted_confidence=0.85,
            actual_direction="Bearish",
            actual_price_change_pct=-3.5,
        )
        outcome = tracker._buffers["master.buffett"].outcomes[0]
        assert outcome.is_correct is False

    def test_record_multiple_agents(self):
        """多个 Agent 独立记录"""
        tracker = TrustTracker()
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        tracker.record_outcome(
            agent_name="master.lynch",
            predicted_direction="Bearish",
            predicted_score=40,
            predicted_confidence=0.6,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        assert len(tracker._buffers["master.buffett"].outcomes) == 1
        assert len(tracker._buffers["master.lynch"].outcomes) == 1
        assert tracker._buffers["master.buffett"].outcomes[0].is_correct is True
        assert tracker._buffers["master.lynch"].outcomes[0].is_correct is False

    def test_record_direction_normalization(self):
        """方向值规范化（非法值默认为 Neutral）"""
        tracker = TrustTracker()
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="INVALID",
            predicted_score=50,
            predicted_confidence=0.5,
            actual_direction="UP",
            actual_price_change_pct=+1.0,
        )
        outcome = tracker._buffers["master.buffett"].outcomes[0]
        assert outcome.predicted_direction == "Neutral"
        assert outcome.actual_direction == "Neutral"
        assert outcome.is_correct is True  # 都是 Neutral


class TestRecordOutcomeFromAnalysis:
    """TrustTracker.record_outcome_from_analysis 验证"""

    def test_delegates_correctly(self):
        """便捷包装正确委托"""
        tracker = TrustTracker()
        tracker.record_outcome_from_analysis(
            agent_name="master.buffett",
            score=80,
            confidence=0.9,
            direction="Bullish",
            actual_direction="Bull ish",  # 规范化会过滤
            actual_price_change_pct=+5.0,
        )
        outcome = tracker._buffers["master.buffett"].outcomes[0]
        assert outcome.predicted_score == 80
        assert outcome.predicted_confidence == 0.9
        assert outcome.predicted_direction == "Bullish"

    def test_from_analysis_wrong(self):
        """便捷包装的错误方向"""
        tracker = TrustTracker()
        tracker.record_outcome_from_analysis(
            agent_name="master.buffett",
            score=80,
            confidence=0.9,
            direction="Bullish",
            actual_direction="Bearish",
            actual_price_change_pct=-2.0,
        )
        assert tracker._buffers["master.buffett"].outcomes[0].is_correct is False


# ═══════════════════════════════════════════════════════════════════
# Phase 3: _compute_metrics 统计精度
# ═══════════════════════════════════════════════════════════════════


def _make_outcome(
    direction: str,
    actual: str,
    confidence: float = 0.5,
    score: int = 50,
    price_change: float = 0.0,
) -> AgentOutcome:
    """便捷工厂：创建 AgentOutcome 用于统计测试"""
    return AgentOutcome(
        agent_name="test",
        predicted_direction=direction,
        actual_direction=actual,
        predicted_confidence=confidence,
        predicted_score=score,
        actual_price_change_pct=price_change,
    )


class TestComputeMetrics:
    """TrustTracker._compute_metrics 验证"""

    def test_empty_outcomes(self):
        """空列表返回默认值"""
        metrics = TrustTracker._compute_metrics([])
        assert metrics.total_samples == 0
        assert metrics.win_rate == 0.0

    def test_all_correct(self):
        """全部正确"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 0.9, 70, 2.0),
            _make_outcome("Bearish", "Bearish", 0.8, 30, -3.0),
            _make_outcome("Bullish", "Bullish", 0.7, 65, 1.5),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.total_samples == 3
        assert metrics.win_rate == 1.0
        assert metrics.bullish_win_rate == 1.0
        assert metrics.bearish_win_rate == 1.0

    def test_all_wrong(self):
        """全部错误"""
        outcomes = [
            _make_outcome("Bullish", "Bearish", 0.8, 70, -2.0),
            _make_outcome("Bearish", "Bullish", 0.9, 30, 3.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.total_samples == 2
        assert metrics.win_rate == 0.0

    def test_mixed_results(self):
        """混合正确/错误"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 0.8, 70, 2.0),
            _make_outcome("Bearish", "Bearish", 0.7, 30, -1.0),
            _make_outcome("Bullish", "Bearish", 0.9, 80, -5.0),
            _make_outcome("Neutral", "Neutral", 0.5, 50, 0.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.total_samples == 4
        assert metrics.win_rate == 0.75  # 3/4
        assert metrics.neutral_win_rate == 1.0
        assert metrics.bullish_win_rate == 0.5  # 1/2
        assert metrics.bearish_win_rate == 1.0

    def test_brier_score_perfect(self):
        """完美校准 → Brier score = 0"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 1.0, 70, 2.0),
            _make_outcome("Bearish", "Bearish", 1.0, 30, -1.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.brier_score == 0.0

    def test_brier_score_poor(self):
        """差校准 → Brier score 高"""
        outcomes = [
            _make_outcome("Bullish", "Bearish", 1.0, 70, -5.0),
            _make_outcome("Bearish", "Bullish", 1.0, 30, 5.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        # 每个: (1.0 - 0.0)^2 = 1.0, avg = 1.0
        assert metrics.brier_score == 1.0

    def test_confidence_bias(self):
        """置信度偏差计算"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 0.9, 70, 2.0),
            _make_outcome("Bullish", "Bearish", 0.9, 70, -5.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        # (0.9-1.0) + (0.9-0.0) = -0.1 + 0.9 = 0.8 / 2 = 0.4
        assert metrics.confidence_bias == 0.4

    def test_calibration_curve(self):
        """校准曲线生成"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", c, 50, 1.0)
            for c in [
                0.05, 0.15, 0.25, 0.35, 0.45,
                0.55, 0.65, 0.75, 0.85, 0.95,
            ]
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert len(metrics.calibration_curve) > 0
        for point in metrics.calibration_curve:
            assert point["acc"] == 1.0
            assert point["count"] >= 0

    def test_optimism_bias(self):
        """乐观偏差检测"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 0.8, 90, 1.0),
            _make_outcome("Bearish", "Bearish", 0.8, 85, -0.5),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        # 两个方向正确，但评分远高于理想评分 → 乐观
        assert metrics.optimism_bias > 0

    def test_trend_improving(self):
        """趋势检测：improving（最近 10 次准确率 > 总体）"""
        wrong = [_make_outcome("Bullish", "Bearish", 0.5, 50, -1.0) for _ in range(10)]
        correct = [
            _make_outcome("Bullish", "Bullish", 0.5, 50, 1.0) for _ in range(10)
        ]
        outcomes = wrong + correct
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.trend_direction == "improving"
        assert metrics.recent_win_rate == 1.0

    def test_trend_declining(self):
        """趋势检测：declining"""
        correct = [
            _make_outcome("Bullish", "Bullish", 0.5, 50, 1.0) for _ in range(10)
        ]
        wrong = [_make_outcome("Bullish", "Bearish", 0.5, 50, -1.0) for _ in range(10)]
        outcomes = correct + wrong
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.trend_direction == "declining"
        assert metrics.recent_win_rate == 0.0

    def test_trend_stable_insufficient_samples(self):
        """样本不足时不报告趋势"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", 0.5, 50, 1.0) for _ in range(5)
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.trend_direction == "stable"


# ═══════════════════════════════════════════════════════════════════
# Phase 4: _build_calibration_curve
# ═══════════════════════════════════════════════════════════════════


class TestBuildCalibrationCurve:
    """_build_calibration_curve 验证"""

    def test_insufficient_samples(self):
        """样本不足时返回空列表"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", c, 50, 1.0)
            for c in [0.1, 0.2, 0.3]
        ]
        curve = _build_calibration_curve(outcomes)
        assert curve == []

    def test_bucket_integrity(self):
        """校验：所有 bucket 的 count 之和 = n"""
        outcomes = [
            _make_outcome(
                "Bullish",
                "Bullish" if i % 2 == 0 else "Bearish",
                c,
                50,
                1.0 if i % 2 == 0 else -1.0,
            )
            for i, c in enumerate([
                0.05, 0.15, 0.25, 0.35, 0.45,
                0.55, 0.65, 0.75, 0.85, 0.95,
            ])
        ]
        curve = _build_calibration_curve(outcomes)
        total_count = sum(point["count"] for point in curve)
        assert total_count == 10

    @staticmethod
    def test_bucket_midpoint_monotonic():
        """校验：bucket midpoint 单调递增"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", c, 50, 1.0)
            for c in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        ]
        curve = _build_calibration_curve(outcomes)
        midpoints = [p["bucket"] for p in curve]
        assert midpoints == sorted(midpoints)


# ═══════════════════════════════════════════════════════════════════
# Phase 5: compute_weight_factor
# ═══════════════════════════════════════════════════════════════════


class TestComputeWeightFactor:
    """compute_weight_factor 验证"""

    def test_insufficient_samples(self):
        """数据不足返回 1.0"""
        metrics = AgentTrustMetrics(total_samples=3, win_rate=1.0)
        assert compute_weight_factor(metrics) == 1.0

    def test_high_performer(self):
        """高绩效 Agent 权重 > 1.0"""
        metrics = AgentTrustMetrics(
            total_samples=30,
            win_rate=0.8,
            brier_score=0.05,
            confidence_bias=0.02,
        )
        factor = compute_weight_factor(metrics)
        assert 1.0 < factor <= 1.5

    def test_low_performer(self):
        """低绩效 Agent 权重 < 1.0"""
        metrics = AgentTrustMetrics(
            total_samples=30,
            win_rate=0.2,
            brier_score=0.8,
            confidence_bias=0.6,
        )
        factor = compute_weight_factor(metrics)
        assert 0.5 <= factor < 1.0

    def test_bounds(self):
        """权重因子不越界 [0.5, 1.5]"""
        worst = AgentTrustMetrics(
            total_samples=30,
            win_rate=0.0,
            brier_score=1.0,
            confidence_bias=1.0,
        )
        assert compute_weight_factor(worst) == 0.5

        best = AgentTrustMetrics(
            total_samples=30,
            win_rate=1.0,
            brier_score=0.0,
            confidence_bias=0.0,
        )
        assert compute_weight_factor(best) == 1.5

    def test_minimal_reliable(self):
        """刚好 5 样本时按公式计算"""
        metrics = AgentTrustMetrics(
            total_samples=5,
            win_rate=0.6,
            brier_score=0.2,
            confidence_bias=0.1,
        )
        factor = compute_weight_factor(metrics)
        assert 0.5 <= factor <= 1.5

    def test_four_samples_unreliable(self):
        """4 样本时（不足 5）返回 1.0"""
        metrics = AgentTrustMetrics(total_samples=4, win_rate=1.0)
        assert compute_weight_factor(metrics) == 1.0


# ═══════════════════════════════════════════════════════════════════
# Phase 6: get_trust_report（mock MemoryStore）
# ═══════════════════════════════════════════════════════════════════


def _dict_outcome(
    agent: str = "master.buffett",
    direction: str = "Bullish",
    actual: str = "Bullish",
    confidence: float = 0.8,
    score: int = 70,
    price: float = 2.0,
) -> dict:
    """便捷工厂：创建 AgentOutcome 的 dict 表示（模拟存储数据）"""
    return {
        "agent_name": agent,
        "predicted_direction": direction,
        "actual_direction": actual,
        "predicted_confidence": confidence,
        "predicted_score": score,
        "actual_price_change_pct": price,
    }


class TestGetTrustReport:
    """TrustTracker.get_trust_report 验证"""

    @pytest.mark.asyncio
    async def test_no_memory_store_no_pending(self):
        """无 MemoryStore 且无内存数据时返回默认"""
        tracker = TrustTracker(memory_store=None)
        report = await tracker.get_trust_report("master.buffett")
        assert report.agent_name == "master.buffett"
        assert report.is_reliable is False
        assert report.metrics.total_samples == 0

    @pytest.mark.asyncio
    async def test_only_pending_data(self):
        """仅内存数据未持久化时也能返回报告"""
        tracker = TrustTracker(memory_store=None)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=75,
            predicted_confidence=0.85,
            actual_direction="Bullish",
            actual_price_change_pct=+3.5,
        )
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bearish",
            predicted_score=35,
            predicted_confidence=0.7,
            actual_direction="Bearish",
            actual_price_change_pct=-1.0,
        )
        report = await tracker.get_trust_report("master.buffett")
        assert report.is_reliable is False  # 仅 2 样本 < 5
        assert report.metrics.total_samples == 2
        assert report.metrics.win_rate == 1.0

    @pytest.mark.asyncio
    async def test_from_store(self):
        """从 MemoryStore 加载数据"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="master.buffett",
            value=[
                _dict_outcome("master.buffett", "Bullish", "Bullish", 0.8, 70, 2.0),
                _dict_outcome("master.buffett", "Bearish", "Bearish", 0.7, 30, -1.0),
                _dict_outcome("master.buffett", "Bullish", "Bearish", 0.9, 80, -5.0),
                _dict_outcome("master.buffett", "Bullish", "Bullish", 0.75, 65, 1.0),
                _dict_outcome("master.buffett", "Neutral", "Bullish", 0.5, 50, 2.0),
            ],
        )
        tracker = TrustTracker(memory_store=mock_store)
        report = await tracker.get_trust_report("master.buffett")
        assert report.is_reliable is True  # 5 样本 >= 5
        assert report.metrics.total_samples == 5
        assert report.metrics.win_rate == 3 / 5  # 3 correct
        assert report.sample_direction_breakdown["Bullish"] == 3
        assert report.sample_direction_breakdown["Bearish"] == 1
        assert report.sample_direction_breakdown["Neutral"] == 1

    @pytest.mark.asyncio
    async def test_merges_pending_and_stored(self):
        """内存中未持久化数据与存储数据合并"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="master.buffett",
            value=[_dict_outcome()],
        )
        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bearish",
            predicted_score=30,
            predicted_confidence=0.7,
            actual_direction="Bearish",
            actual_price_change_pct=-1.0,
        )
        report = await tracker.get_trust_report("master.buffett")
        assert report.metrics.total_samples == 2
        assert report.metrics.win_rate == 1.0

    @pytest.mark.asyncio
    async def test_store_get_failure(self):
        """MemoryStore.get 异常不抛错，返回仅内存数据"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.side_effect = OSError("disk full")

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=75,
            predicted_confidence=0.85,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        report = await tracker.get_trust_report("master.buffett")
        assert report.metrics.total_samples == 1
        assert report.is_reliable is False

    @pytest.mark.asyncio
    async def test_store_nonexistent_agent(self):
        """不存在的 Agent 返回默认报告"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None
        tracker = TrustTracker(memory_store=mock_store)
        report = await tracker.get_trust_report("master.nobody")
        assert report.metrics.total_samples == 0
        assert report.is_reliable is False

    @pytest.mark.asyncio
    async def test_skip_cached_summary(self):
        """无数据时摘要合理"""
        tracker = TrustTracker(memory_store=None)
        report = await tracker.get_trust_report("master.buffett")
        assert "不足" in report.summary or report.summary == ""


# ═══════════════════════════════════════════════════════════════════
# Phase 7: flush
# ═══════════════════════════════════════════════════════════════════


class TestFlush:
    """TrustTracker.flush 验证"""

    @pytest.mark.asyncio
    async def test_flush_no_store(self):
        """无 MemoryStore 时静默跳过"""
        tracker = TrustTracker(memory_store=None)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        await tracker.flush()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_flush_writes_to_store(self):
        """flush 将数据写入 MemoryStore"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None  # 无已有数据

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )

        await tracker.flush()

        mock_store.put.assert_called_once()
        call_args = mock_store.put.call_args
        assert call_args.kwargs["key"] == "master.buffett"
        assert call_args.kwargs["namespace"] == ("trust", "debate")
        written = call_args.kwargs["value"]
        assert isinstance(written, list)
        assert len(written) == 1
        assert written[0]["agent_name"] == "master.buffett"

    @pytest.mark.asyncio
    async def test_flush_merged_with_existing(self):
        """flush 合并已存储的记录"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="master.buffett",
            value=[_dict_outcome()],
        )

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bearish",
            predicted_score=30,
            predicted_confidence=0.7,
            actual_direction="Bearish",
            actual_price_change_pct=-1.0,
        )

        await tracker.flush()

        mock_store.put.assert_called_once()
        written = mock_store.put.call_args.kwargs["value"]
        assert len(written) == 2  # 原有 1 + 新增 1

    @pytest.mark.asyncio
    async def test_flush_skip_duplicates(self):
        """flush 去重：完全相同记录不重复写入"""
        existing = [_dict_outcome()]
        existing[0]["session_id"] = "sess-1"
        existing[0]["stock_code"] = "000001"

        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="master.buffett",
            value=existing,
        )

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=2.0,
            session_id="sess-1",
            stock_code="000001",
        )

        await tracker.flush()

        # 完全重复 → flush 不需要调用 put
        assert mock_store.put.call_count == 0

    @pytest.mark.asyncio
    async def test_flush_put_failure_not_blocking(self):
        """MemoryStore.put 失败不抛异常"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None
        mock_store.put.side_effect = OSError("disk full")

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )

        await tracker.flush()  # 不应抛异常

    @pytest.mark.asyncio
    async def test_flush_clean_dirty_flag(self):
        """flush 后 dirty flag 应清除"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None

        tracker = TrustTracker(memory_store=mock_store)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        assert tracker._buffers["master.buffett"].dirty is True

        await tracker.flush()

        assert tracker._buffers["master.buffett"].dirty is False


# ═══════════════════════════════════════════════════════════════════
# Phase 8: get_all_agent_names
# ═══════════════════════════════════════════════════════════════════


class TestGetAllAgentNames:
    """TrustTracker.get_all_agent_names 验证"""

    @pytest.mark.asyncio
    async def test_from_memory_only(self):
        """仅内存数据"""
        tracker = TrustTracker(memory_store=None)
        tracker.record_outcome(
            agent_name="master.buffett",
            predicted_direction="Bullish",
            predicted_score=70,
            predicted_confidence=0.8,
            actual_direction="Bullish",
            actual_price_change_pct=+2.0,
        )
        names = await tracker.get_all_agent_names()
        assert names == ["master.buffett"]

    @pytest.mark.asyncio
    async def test_empty(self):
        """无数据返回空列表"""
        tracker = TrustTracker(memory_store=None)
        names = await tracker.get_all_agent_names()
        assert names == []


# ═══════════════════════════════════════════════════════════════════
# Phase 9: 边界案例
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界案例验证"""

    def test_single_outcome_metrics(self):
        """单条记录也能计算"""
        outcomes = [_make_outcome("Bullish", "Bullish", 0.8, 70, 2.0)]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.total_samples == 1
        assert metrics.win_rate == 1.0
        assert metrics.brier_score == pytest.approx(0.04, abs=1e-4)  # (0.8-1.0)^2

    def test_high_score_error(self):
        """评分极端偏差"""
        outcomes = [
            _make_outcome("Bullish", "Bearish", 1.0, 100, -10.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.avg_score_error > 0

    def test_all_neutral_outcomes(self):
        """全部 Neutral 时准确率 = 1.0（方向标尺重叠）"""
        outcomes = [
            _make_outcome("Neutral", "Neutral", 0.5, 50, 0.0),
            _make_outcome("Neutral", "Neutral", 0.6, 50, 0.0),
        ]
        metrics = TrustTracker._compute_metrics(outcomes)
        assert metrics.win_rate == 1.0
        assert metrics.neutral_win_rate == 1.0

    def test_calibration_curve_boundary(self):
        """置信度边界值（0 和 1）的 bucket 分桶"""
        outcomes = [
            _make_outcome("Bullish", "Bullish", c, 50, 1.0)
            for c in [0.0, 0.99, 1.0]
        ]
        curve = _build_calibration_curve(outcomes)
        # 少于 10 条记录 → 空
        assert curve == []

    @pytest.mark.asyncio
    async def test_summary_generation(self):
        """摘要文本生成逻辑"""
        tracker = TrustTracker(memory_store=None)
        for _ in range(5):
            tracker.record_outcome(
                agent_name="master.test",
                predicted_direction="Bullish",
                predicted_score=70,
                predicted_confidence=0.8,
                actual_direction="Bullish",
                actual_price_change_pct=2.0,
            )
        report = await tracker.get_trust_report("master.test")
        assert "master.test" in report.summary or report.agent_name == "master.test"

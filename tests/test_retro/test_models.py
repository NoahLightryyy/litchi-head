"""测试交易复盘数据模型和工具函数"""

from datetime import datetime, timedelta

import pytest

from src.retro.models import (
    RetroRecord,
    compute_outcome,
    compute_retro_summary,
)


class TestRetroRecord:
    """RetroRecord 模型基本行为"""

    def test_create_minimal(self):
        """最小字段创建"""
        r = RetroRecord(record_id="test_001", session_id="deb_abc", stock_code="000001")
        assert r.record_id == "test_001"
        assert r.outcome == "pending"
        assert r.user_action is None
        assert r.price_at_debate is None

    def test_create_full(self):
        """全字段创建"""
        r = RetroRecord(
            record_id="test_002",
            session_id="deb_xyz",
            stock_code="600000",
            stock_name="浦发银行",
            consensus="看涨",
            confidence=0.85,
            weighted_score=75.5,
            avg_score=72.0,
            direction_distribution={"Bullish": 4, "Bearish": 1, "Neutral": 0},
            price_at_debate=8.5,
            user_action="buy",
            outcome="pending",
        )
        assert r.stock_name == "浦发银行"
        assert r.confidence == 0.85
        assert r.direction_distribution["Bullish"] == 4

    def test_default_created_at(self):
        """created_at 默认值为当前时间"""
        r = RetroRecord(record_id="t", session_id="s", stock_code="000001")
        assert r.created_at is not None
        now = datetime.now()
        diff = abs((now - r.created_at).total_seconds())
        assert diff < 5  # 5秒以内


class TestComputeOutcome:
    """compute_outcome 方向判定"""

    def test_bullish_correct(self):
        """看涨 → 涨幅 > 阈值 → correct"""
        assert compute_outcome("Bullish", 3.0) == "correct"
        assert compute_outcome("Bullish", 0.6) == "correct"

    def test_bullish_wrong(self):
        """看涨 → 跌幅 → wrong"""
        assert compute_outcome("Bullish", -2.0) == "wrong"
        assert compute_outcome("Bullish", 0.0) == "wrong"

    def test_bearish_correct(self):
        """看跌 → 跌幅 > 阈值 → correct"""
        assert compute_outcome("Bearish", -3.0) == "correct"
        assert compute_outcome("Bearish", -0.6) == "correct"

    def test_bearish_wrong(self):
        """看跌 → 涨幅 → wrong"""
        assert compute_outcome("Bearish", 2.0) == "wrong"

    def test_neutral_correct(self):
        """中性 → 涨跌幅小 → correct"""
        assert compute_outcome("Neutral", 0.3) == "correct"
        assert compute_outcome("Neutral", 0.0) == "correct"
        assert compute_outcome("Neutral", -0.3) == "correct"

    def test_neutral_wrong(self):
        """中性 → 大幅波动 → wrong"""
        assert compute_outcome("Neutral", 3.0) == "wrong"
        assert compute_outcome("Neutral", -3.0) == "wrong"

    def test_custom_threshold(self):
        """自定义阈值"""
        assert compute_outcome("Bullish", 1.0, threshold=0.5) == "correct"
        assert compute_outcome("Bullish", 0.3, threshold=0.5) == "wrong"


class TestComputeRetroSummary:
    """compute_retro_summary 聚合统计"""

    def test_empty(self):
        """空列表"""
        summary = compute_retro_summary([])
        assert summary.total_records == 0
        assert summary.win_rate == 0.0

    def test_all_pending(self):
        """全部待判定"""
        records = [
            RetroRecord(record_id="1", session_id="s", stock_code="000001"),
            RetroRecord(record_id="2", session_id="s", stock_code="000002"),
        ]
        summary = compute_retro_summary(records)
        assert summary.total_records == 2
        assert summary.closed_records == 0
        assert summary.win_rate == 0.0

    def test_mixed_outcomes(self):
        """混合结果"""
        now = datetime.now()
        records = [
            RetroRecord(
                record_id="1",
                session_id="s",
                stock_code="000001",
                outcome="correct",
                confidence=0.8,
                weighted_score=80.0,
                created_at=now,
            ),
            RetroRecord(
                record_id="2",
                session_id="s",
                stock_code="000002",
                outcome="correct",
                confidence=0.7,
                weighted_score=70.0,
                created_at=now,
            ),
            RetroRecord(
                record_id="3",
                session_id="s",
                stock_code="000003",
                outcome="wrong",
                confidence=0.6,
                weighted_score=60.0,
                created_at=now,
            ),
            RetroRecord(
                record_id="4",
                session_id="s",
                stock_code="000004",
                outcome="pending",
                confidence=0.9,
                weighted_score=90.0,
                created_at=now - timedelta(days=2),
            ),
        ]
        summary = compute_retro_summary(records)
        assert summary.total_records == 4
        assert summary.closed_records == 3
        assert summary.win_count == 2
        assert summary.loss_count == 1
        assert summary.win_rate == pytest.approx(2 / 3, abs=0.001)
        assert round(summary.avg_confidence, 2) == round((0.8 + 0.7 + 0.6 + 0.9) / 4, 2)
        assert summary.avg_score == round((80 + 70 + 60 + 90) / 4, 2)

    def test_today_count(self):
        """今日记录数"""
        now = datetime.now()
        records = [
            RetroRecord(
                record_id="1", session_id="s", stock_code="000001",
                created_at=now,
            ),
            RetroRecord(
                record_id="2", session_id="s", stock_code="000002",
                created_at=now - timedelta(days=1),
            ),
        ]
        summary = compute_retro_summary(records)
        assert summary.today_records == 1

    def test_last_record_at(self):
        """最近记录时间"""
        now = datetime.now()
        records = [
            RetroRecord(
                record_id="old", session_id="s", stock_code="000001",
                created_at=now - timedelta(hours=5),
            ),
            RetroRecord(
                record_id="new", session_id="s", stock_code="000002",
                created_at=now,
            ),
        ]
        summary = compute_retro_summary(records)
        assert summary.last_record_at is not None
        assert (now - summary.last_record_at).total_seconds() < 5

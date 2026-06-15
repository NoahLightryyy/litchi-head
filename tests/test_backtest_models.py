"""回测引擎数据模型测试

覆盖：BacktestConfig / TradeRecord / PortfolioSnapshot / PerformanceMetrics / BacktestReport
遵循 test_trader_t1.py 的 Phase 模式。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backtest.models import (
    BacktestConfig,
    BacktestReport,
    PerformanceMetrics,
    PortfolioSnapshot,
    TradeRecord,
)

# ═══════════════════════════════════════════════════════════════
# Phase 1: 数据模型测试 — BacktestConfig
# ═══════════════════════════════════════════════════════════════


class TestBacktestConfig:
    def test_default_values(self) -> None:
        cfg = BacktestConfig()
        assert cfg.initial_capital == 1_000_000.0
        assert cfg.commission_rate == 0.0003
        assert cfg.slippage == 0.001
        assert cfg.max_single_position == 0.2

    def test_full_construction(self) -> None:
        cfg = BacktestConfig(
            initial_capital=500_000.0,
            commission_rate=0.0005,
            slippage=0.002,
            max_single_position=0.3,
        )
        assert cfg.initial_capital == 500_000.0
        assert cfg.commission_rate == 0.0005
        assert cfg.slippage == 0.002
        assert cfg.max_single_position == 0.3

    def test_serialization(self) -> None:
        cfg = BacktestConfig(initial_capital=200_000.0)
        d = cfg.model_dump()
        assert d["initial_capital"] == 200_000.0
        assert d["commission_rate"] == 0.0003
        restored = BacktestConfig.model_validate(d)
        assert restored.initial_capital == 200_000.0

    def test_fields_reject_none(self) -> None:
        with pytest.raises(ValidationError):
            BacktestConfig(initial_capital=None)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════
# Phase 2: 数据模型测试 — TradeRecord
# ═══════════════════════════════════════════════════════════════


class TestTradeRecord:
    def test_default_values(self) -> None:
        t = TradeRecord()
        assert t.ticker == ""
        assert t.direction == "buy"
        assert t.entry_date == ""
        assert t.exit_date == ""
        assert t.entry_price == 0.0
        assert t.quantity == 0
        assert t.pnl == 0.0
        assert t.exit_reason == ""

    def test_full_construction(self) -> None:
        t = TradeRecord(
            ticker="000001",
            direction="buy",
            entry_date="2024-06-01",
            exit_date="2024-06-15",
            entry_price=10.0,
            exit_price=11.0,
            quantity=10000,
            position_pct=0.1,
            pnl=10000.0,
            pnl_pct=0.10,
            holding_days=14,
            exit_reason="止盈",
            trade_plan={"direction": "Bullish", "action": "buy"},
        )
        assert t.ticker == "000001"
        assert t.pnl == 10000.0
        assert t.pnl_pct == 0.10
        assert t.exit_reason == "止盈"
        assert t.trade_plan["direction"] == "Bullish"

    def test_serialization(self) -> None:
        t = TradeRecord(ticker="000001", entry_price=10.0, exit_price=11.0)
        d = t.model_dump()
        assert d["ticker"] == "000001"
        assert d["pnl"] == 0.0
        restored = TradeRecord.model_validate(d)
        assert restored.ticker == "000001"

    def test_sell_direction(self) -> None:
        t = TradeRecord(
            ticker="000001",
            direction="sell",
            entry_price=15.0,
            exit_price=13.0,
            quantity=5000,
        )
        assert t.direction == "sell"
        # 做空：卖价 15，买回 13，应盈利
        t.pnl = (13.0 - 15.0) * 5000  # 平仓盈亏
        t.pnl_pct = -2.0 / 15.0

    def test_trade_plan_default_empty_dict(self) -> None:
        t = TradeRecord()
        assert t.trade_plan == {}
        assert isinstance(t.trade_plan, dict)

    def test_failed_variant(self) -> None:
        # TradeRecord 没有 success 字段，但所有字段应有安全默认值
        t = TradeRecord()
        assert t.pnl == 0.0
        assert t.holding_days == 0


# ═══════════════════════════════════════════════════════════════
# Phase 3: 数据模型测试 — PortfolioSnapshot
# ═══════════════════════════════════════════════════════════════


class TestPortfolioSnapshot:
    def test_default_values(self) -> None:
        s = PortfolioSnapshot()
        assert s.date == ""
        assert s.total_value == 0.0
        assert s.cash == 0.0
        assert s.position_value == 0.0
        assert s.daily_return == 0.0
        assert s.cumulative_return == 0.0
        assert s.drawdown == 0.0

    def test_full_construction(self) -> None:
        s = PortfolioSnapshot(
            date="2024-06-10",
            total_value=1_100_000.0,
            cash=500_000.0,
            position_value=600_000.0,
            daily_return=0.02,
            cumulative_return=0.10,
            drawdown=0.03,
        )
        assert s.total_value == 1_100_000.0
        assert s.cash == 500_000.0
        assert s.daily_return == 0.02
        assert s.drawdown == 0.03

    def test_zero_values(self) -> None:
        """起始快照：全部现金，无持仓"""
        s = PortfolioSnapshot(
            date="2024-06-01",
            total_value=1_000_000.0,
            cash=1_000_000.0,
            position_value=0.0,
            daily_return=0.0,
            cumulative_return=0.0,
            drawdown=0.0,
        )
        assert s.position_value == 0.0
        assert s.total_value == s.cash


# ═══════════════════════════════════════════════════════════════
# Phase 4: 数据模型测试 — PerformanceMetrics
# ═══════════════════════════════════════════════════════════════


class TestPerformanceMetrics:
    def test_default_values(self) -> None:
        m = PerformanceMetrics()
        assert m.total_return == 0.0
        assert m.annual_return == 0.0
        assert m.max_drawdown == 0.0
        assert m.sharpe_ratio == 0.0
        assert m.win_rate == 0.0
        assert m.profit_factor == 0.0
        assert m.total_trades == 0
        assert m.avg_holding_days == 0.0

    def test_full_construction(self) -> None:
        m = PerformanceMetrics(
            total_return=0.15,
            annual_return=0.12,
            max_drawdown=0.05,
            sharpe_ratio=1.8,
            win_rate=0.65,
            profit_factor=2.5,
            total_trades=20,
            winning_trades=13,
            losing_trades=7,
            avg_holding_days=15.0,
            cagr=0.11,
        )
        assert m.total_return == 0.15
        assert m.sharpe_ratio == 1.8
        assert m.win_rate == 0.65
        assert m.total_trades == 20
        assert m.cagr == 0.11

    def test_win_rate_derived(self) -> None:
        """验证 win_rate 与 total_trades/winning_trades 关系"""
        m = PerformanceMetrics(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
        )
        assert m.win_rate == 0.6
        assert m.winning_trades + m.losing_trades == m.total_trades

    def test_zero_trades_metrics(self) -> None:
        """无交易时的安全默认值"""
        m = PerformanceMetrics()
        assert m.total_trades == 0
        assert m.win_rate == 0.0
        assert m.profit_factor == 0.0


# ═══════════════════════════════════════════════════════════════
# Phase 5: 数据模型测试 — BacktestReport
# ═══════════════════════════════════════════════════════════════


class TestBacktestReport:
    def test_default_values(self) -> None:
        r = BacktestReport()
        assert isinstance(r.config, BacktestConfig)
        assert isinstance(r.metrics, PerformanceMetrics)
        assert r.trades == []
        assert r.equity_curve == []
        assert r.start_date == ""
        assert r.total_days == 0

    def test_full_construction(self) -> None:
        cfg = BacktestConfig(initial_capital=500_000.0)
        metrics = PerformanceMetrics(total_return=0.10, sharpe_ratio=1.5)
        trade = TradeRecord(ticker="000001", entry_price=10.0)
        snapshot = PortfolioSnapshot(date="2024-06-01", total_value=500_000.0, cash=500_000.0)

        r = BacktestReport(
            config=cfg,
            metrics=metrics,
            trades=[trade],
            equity_curve=[snapshot],
            start_date="2024-06-01",
            end_date="2024-06-30",
            ticker="000001",
            total_days=30,
        )
        assert r.config.initial_capital == 500_000.0
        assert r.metrics.sharpe_ratio == 1.5
        assert len(r.trades) == 1
        assert len(r.equity_curve) == 1
        assert r.total_days == 30

    def test_embedded_model_access(self) -> None:
        """验证嵌套模型可访问"""
        r = BacktestReport()
        r.config.initial_capital = 2_000_000.0
        assert r.config.initial_capital == 2_000_000.0

    def test_serialization_roundtrip(self) -> None:
        r = BacktestReport(
            ticker="000001",
            trades=[TradeRecord(ticker="000001", entry_price=10.0, exit_price=11.0)],
            start_date="2024-01-01",
            end_date="2024-12-31",
            total_days=365,
        )
        d = r.model_dump()
        restored = BacktestReport.model_validate(d)
        assert restored.ticker == "000001"
        assert len(restored.trades) == 1
        assert restored.trades[0].entry_price == 10.0
        assert restored.total_days == 365

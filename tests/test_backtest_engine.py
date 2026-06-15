"""回测引擎测试

覆盖：BacktestEngine 完整交易模拟 + PerformanceMetrics 指标验证
Phase 模式：模型测试在 test_backtest_models.py，这里集中测试引擎和指标。

场景：
1. 简单买入持有（盈利）
2. 简单买入持有（亏损）
3. 多笔交易（综合场景）
4. 分批建仓
5. 指标计算验证（已知结果）
6. 边界情况
"""

from __future__ import annotations

import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.metrics import (
    calculate_annual_return,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe,
    calculate_win_rate,
)
from src.backtest.models import (
    BacktestConfig,
    PortfolioSnapshot,
    TradeRecord,
)
from src.data.models import KLine

# ── 测试辅助：生成模拟 KLine 数据 ──────────────────────────


def _make_kline(
    date: str,
    close: float,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: int = 1_000_000,
) -> KLine:
    return KLine(
        date=date,
        open=open_ if open_ is not None else close,
        close=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        volume=volume,
        amount=close * volume,
    )


def _make_rising_klines(
    start_price: float = 10.0,
    days: int = 10,
    daily_change: float = 0.01,
) -> list[KLine]:
    """生成持续上涨的 K 线序列"""
    klines: list[KLine] = []
    price = start_price
    for i in range(days):
        klines.append(_make_kline(f"2024-06-{i+1:02d}", close=round(price, 2)))
        price *= 1.0 + daily_change
    return klines


def _make_falling_klines(
    start_price: float = 10.0,
    days: int = 10,
    daily_change: float = -0.01,
) -> list[KLine]:
    """生成持续下跌的 K 线序列"""
    klines: list[KLine] = []
    price = start_price
    for i in range(days):
        klines.append(_make_kline(f"2024-06-{i+1:02d}", close=round(price, 2)))
        price *= 1.0 + daily_change
    return klines


def _make_volatile_klines() -> list[KLine]:
    """生成先涨后跌的 K 线序列（用于测试回撤）"""
    prices = [10.0, 10.5, 11.0, 11.5, 12.0, 11.5, 11.0, 10.5, 10.0, 9.5]
    return [_make_kline(f"2024-06-{i+1:02d}", close=p) for i, p in enumerate(prices)]


# ═══════════════════════════════════════════════════════════════
# Phase 1: BacktestEngine — 简单盈利场景
# ═══════════════════════════════════════════════════════════════


class TestSimpleProfit:
    """测试简单买入→持有→卖出的盈利回测"""

    async def test_buy_and_hold_profit(self) -> None:
        """买入 10 元 → 持有 5 天 → 卖出 10.5 元，应盈利"""
        klines = _make_rising_klines(start_price=10.0, days=10, daily_change=0.01)
        trades = [
            TradeRecord(
                ticker="000001",
                direction="buy",
                entry_date="2024-06-01",
                entry_price=10.0,
                quantity=50000,  # 50 万股
                position_pct=0.5,
            ),
            TradeRecord(
                ticker="000001",
                direction="sell",
                entry_date="2024-06-01",
                exit_date="2024-06-05",
                exit_price=10.51,  # 约 5 天涨 ~5%
                quantity=50000,
                position_pct=0.5,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        assert report.ticker == "000001"
        assert report.metrics.total_trades >= 1
        # 100 万资金投 50% = 50 万买 50000 股 × 10 元 = 50 万
        # 涨 ~5% → 50000 × (10.51 - 10.0) = 25,500 收益
        # 去掉 0 费用，总资产 = 1,025,500
        assert report.metrics.total_return > 0
        assert report.metrics.win_rate > 0
        assert len(report.equity_curve) > 0

    async def test_buy_and_hold_loss(self) -> None:
        """买入 10 元 → 持有 5 天 → 卖出 9.5 元，应亏损"""
        klines = _make_falling_klines(start_price=10.0, days=10, daily_change=-0.01)
        trades = [
            TradeRecord(
                ticker="000001",
                direction="buy",
                entry_date="2024-06-01",
                entry_price=10.0,
                quantity=50000,
                position_pct=0.5,
            ),
            TradeRecord(
                ticker="000001",
                direction="sell",
                entry_date="2024-06-01",
                exit_date="2024-06-05",
                exit_price=9.51,
                quantity=50000,
                position_pct=0.5,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        assert report.metrics.total_return < 0
        assert report.metrics.win_rate == 0.0  # 亏损交易

    async def test_full_position_profit(self) -> None:
        """全仓买入 10 元 → 涨 10% → 卖出，验证精确收益率 ~10%"""
        klines = _make_rising_klines(start_price=10.0, days=10, daily_change=0.0)
        # 改为手动构造：第 1 天 10 元，第 10 天 11 元
        klines = [
            _make_kline("2024-06-01", close=10.0),
            _make_kline("2024-06-02", close=10.0),
            _make_kline("2024-06-10", close=11.0),
        ]
        trades = [
            TradeRecord(
                ticker="000001",
                direction="buy",
                entry_date="2024-06-01",
                entry_price=10.0,
                quantity=100000,  # 全仓 100 万买 10 万股
                position_pct=1.0,
            ),
            TradeRecord(
                ticker="000001",
                direction="sell",
                entry_date="2024-06-01",
                exit_date="2024-06-10",
                exit_price=11.0,
                quantity=100000,
                position_pct=1.0,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        # 不考虑费用：收益率应为 10%
        assert report.metrics.total_return == pytest.approx(0.10, rel=0.01)


# ═══════════════════════════════════════════════════════════════
# Phase 2: BacktestEngine — 多笔交易 + 复杂场景
# ═══════════════════════════════════════════════════════════════


class TestMultipleTrades:
    """测试多笔交易的汇总指标"""

    async def test_two_profit_trades(self) -> None:
        """两笔盈利交易的胜率和盈亏比"""
        klines = _make_rising_klines(start_price=10.0, days=20, daily_change=0.0)
        # 10 天涨 5%，后 10 天再涨 5%
        klines = [
            _make_kline("2024-06-01", close=10.0),
            _make_kline("2024-06-05", close=10.5),
            _make_kline("2024-06-10", close=10.0),
            _make_kline("2024-06-15", close=10.5),
            _make_kline("2024-06-20", close=11.0),
        ]

        trades = [
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-01", entry_price=10.0,
                exit_date="2024-06-05", exit_price=10.5,
                quantity=50000, pnl=25000.0, pnl_pct=0.05,
                holding_days=4,
            ),
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-10", entry_price=10.0,
                exit_date="2024-06-20", exit_price=11.0,
                quantity=50000, pnl=50000.0, pnl_pct=0.10,
                holding_days=10,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        assert report.metrics.total_trades == 2
        assert report.metrics.winning_trades == 2
        assert report.metrics.win_rate == 1.0

    async def test_win_and_loss_trades(self) -> None:
        """一盈一亏：验证胜率 50%，profit_factor = 盈利/亏损"""
        klines = [
            _make_kline("2024-06-01", close=10.0),
            _make_kline("2024-06-05", close=11.0),
            _make_kline("2024-06-10", close=10.0),
            _make_kline("2024-06-15", close=9.0),
            _make_kline("2024-06-20", close=10.0),
        ]

        trades = [
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-01", entry_price=10.0,
                exit_date="2024-06-05", exit_price=11.0,
                quantity=50000, pnl=50000.0, pnl_pct=0.10,
                holding_days=4,
            ),
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-10", entry_price=10.0,
                exit_date="2024-06-15", exit_price=9.0,
                quantity=50000, pnl=-50000.0, pnl_pct=-0.10,
                holding_days=5,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        assert report.metrics.win_rate == 0.5
        assert report.metrics.winning_trades == 1
        assert report.metrics.losing_trades == 1
        # profit_factor = 50000 / 50000 = 1.0
        assert report.metrics.profit_factor == pytest.approx(1.0, rel=0.01)


# ═══════════════════════════════════════════════════════════════
# Phase 3: PerformanceMetrics — 指标计算验证
# ═══════════════════════════════════════════════════════════════


class TestMetricsCalculation:
    """绩效指标纯函数验证"""

    def test_sharpe_constant_returns(self) -> None:
        """每日收益恒定时夏普应为 0（无波动 = 无超额风险调整后收益）"""
        daily_returns = [0.001] * 100
        sharpe = calculate_sharpe(daily_returns, risk_free_rate=0.02)
        # 方差 = 0 → 夏普应为 0
        assert sharpe == 0.0

    def test_sharpe_positive(self) -> None:
        """持续正收益 → 夏普为正"""
        daily_returns = [0.001] * 100
        daily_returns[50] = 0.002  # 加一点波动
        sharpe = calculate_sharpe(daily_returns, risk_free_rate=0.02)
        assert sharpe > 0

    def test_sharpe_insufficient_data(self) -> None:
        """不足 2 个数据点 → 返回 0"""
        assert calculate_sharpe([]) == 0.0
        assert calculate_sharpe([0.001]) == 0.0

    def test_max_drawdown_simple(self) -> None:
        """先涨 20%，再跌 10% → 最大回撤应为 10%（从峰值 120 跌到 108）"""
        snap = PortfolioSnapshot
        curve = [
            snap(date="d1", total_value=100.0, cash=100.0),
            snap(date="d2", total_value=120.0, cash=120.0),
            snap(date="d3", total_value=108.0, cash=108.0),
        ]
        dd = calculate_max_drawdown(curve)
        # (120 - 108) / 120 = 0.10
        assert dd == pytest.approx(0.10, rel=0.01)

    def test_max_drawdown_no_drawdown(self) -> None:
        """持续上涨 → 回撤 0"""
        snap = PortfolioSnapshot
        curve = [
            snap(date="d1", total_value=100.0, cash=100.0),
            snap(date="d2", total_value=110.0, cash=110.0),
            snap(date="d3", total_value=121.0, cash=121.0),
        ]
        assert calculate_max_drawdown(curve) == 0.0

    def test_max_drawdown_insufficient_data(self) -> None:
        """不足 2 个快照 → 返回 0"""
        assert calculate_max_drawdown([]) == 0.0

    def test_win_rate_all_win(self) -> None:
        trades = [
            TradeRecord(ticker="000001", pnl=100.0),
            TradeRecord(ticker="000001", pnl=200.0),
        ]
        win, lose, rate = calculate_win_rate(trades)
        assert win == 2
        assert lose == 0
        assert rate == 1.0

    def test_win_rate_all_loss(self) -> None:
        trades = [
            TradeRecord(ticker="000001", pnl=-100.0),
            TradeRecord(ticker="000001", pnl=-200.0),
        ]
        win, lose, rate = calculate_win_rate(trades)
        assert win == 0
        assert lose == 2
        assert rate == 0.0

    def test_win_rate_zero_trades(self) -> None:
        assert calculate_win_rate([]) == (0, 0, 0.0)

    def test_profit_factor(self) -> None:
        trades = [
            TradeRecord(ticker="000001", pnl=1000.0),
            TradeRecord(ticker="000001", pnl=-500.0),
        ]
        pf = calculate_profit_factor(trades)
        # 1000 / 500 = 2.0
        assert pf == pytest.approx(2.0, rel=0.01)

    def test_profit_factor_no_trades(self) -> None:
        assert calculate_profit_factor([]) == 0.0

    def test_cagr(self) -> None:
        """100 万 → 121 万，2 年 → CAGR = 10%"""
        cagr = calculate_cagr(1_000_000.0, 1_210_000.0, 730)
        # (1.21) ^ (1/2) - 1 = 0.10
        assert cagr == pytest.approx(0.10, rel=0.01)

    def test_cagr_invalid(self) -> None:
        assert calculate_cagr(0, 100, 365) == 0.0
        assert calculate_cagr(100, 100, 0) == 0.0

    def test_annual_return(self) -> None:
        """半年收益率 5% → 年化约 10.25%"""
        ar = calculate_annual_return(0.05, 183)
        expected = (1.05 ** (365.0 / 183.0)) - 1.0
        assert ar == pytest.approx(expected, rel=0.01)

    def test_annual_return_zero_days(self) -> None:
        assert calculate_annual_return(0.10, 0) == 0.0


# ═══════════════════════════════════════════════════════════════
# Phase 4: BacktestEngine — 边界情况
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试"""

    async def test_empty_trades(self) -> None:
        """空交易列表 → 收益率 0，但净值曲线只含初始状态"""
        klines = _make_rising_klines(days=5)
        engine = BacktestEngine()
        report = await engine.run([], klines)

        assert report.metrics.total_return == 0.0
        assert report.metrics.total_trades == 0
        # 即使无交易，也应有初始快照
        assert len(report.equity_curve) >= 1

    async def test_empty_klines(self) -> None:
        """空 K 线列表 → 无法模拟，报告应含基本字段但有默认值"""
        engine = BacktestEngine()
        report = await engine.run([], [])

        assert report.metrics.total_return == 0.0
        assert report.metrics.total_trades == 0
        assert report.total_days == 0

    async def test_with_commission_and_slippage(self) -> None:
        """含手续费和滑点的回测 → 收益率应低于无费用版本"""
        klines = [
            _make_kline("2024-06-01", close=10.0),
            _make_kline("2024-06-10", close=11.0),
        ]
        trades = [
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-01", entry_price=10.0,
                exit_date="2024-06-10", exit_price=11.0,
                quantity=100000, position_pct=1.0,
            ),
        ]

        # 无费用
        cfg_no_fee = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine_no_fee = BacktestEngine(cfg_no_fee)
        report_no_fee = await engine_no_fee.run(trades, klines)

        # 有费用
        cfg_with_fee = BacktestConfig(
            initial_capital=1_000_000.0, commission_rate=0.003, slippage=0.001,
        )
        engine_with_fee = BacktestEngine(cfg_with_fee)
        report_with_fee = await engine_with_fee.run(trades, klines)

        # 有费用的收益率应更低
        assert report_with_fee.metrics.total_return < report_no_fee.metrics.total_return

    async def test_multiple_different_stocks(self) -> None:
        """多只股票交易→报告应汇总所有交易"""
        klines = [_make_kline(f"2024-06-{i+1:02d}", close=10.0 + i * 0.5) for i in range(5)]

        trades = [
            TradeRecord(
                ticker="000001", direction="buy",
                entry_date="2024-06-01", entry_price=10.0,
                exit_date="2024-06-05", exit_price=12.0,
                quantity=50000, pnl=100000.0, pnl_pct=0.20,
                holding_days=4,
            ),
            TradeRecord(
                ticker="000002", direction="buy",
                entry_date="2024-06-01", entry_price=20.0,
                exit_date="2024-06-05", exit_price=18.8,
                quantity=25000, pnl=-30000.0, pnl_pct=-0.06,
                holding_days=4,
            ),
        ]

        cfg = BacktestConfig(initial_capital=1_000_000.0, commission_rate=0.0, slippage=0.0)
        engine = BacktestEngine(cfg)
        report = await engine.run(trades, klines)

        assert report.metrics.total_trades == 2
        # 总的收益率应为正（盈利 > 亏损）
        assert report.metrics.total_return > 0

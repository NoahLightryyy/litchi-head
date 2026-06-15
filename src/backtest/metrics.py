"""回测绩效指标计算 —— 纯函数模块

提供所有绩效指标的独立计算函数，以及一个聚合入口 calculate_metrics()。
所有函数为纯函数（无状态、无副作用），方便测试和组合。

指标清单：
- Sharpe Ratio（夏普比率）
- Max Drawdown（最大回撤）
- Win Rate（胜率）
- Profit Factor（盈亏比）
- CAGR（复合年增长率）
- Daily Returns（日收益率序列，为上述指标的基础）
"""

from __future__ import annotations

import math

from src.backtest.models import (
    BacktestConfig,
    PerformanceMetrics,
    PortfolioSnapshot,
    TradeRecord,
)


def calculate_daily_returns(
    equity_curve: list[PortfolioSnapshot],
) -> list[float]:
    """从净值曲线提取日收益率序列

    跳过 equity_curve 中第一天（日收益率为 0）。
    """
    if len(equity_curve) < 2:
        return []
    return [s.daily_return for s in equity_curve[1:]]


def calculate_sharpe(
    daily_returns: list[float],
    risk_free_rate: float = 0.02,
    trading_days: int = 252,
) -> float:
    """计算年化夏普比率

    Sharpe = (mean(Rp) - Rf) / std(Rp) * sqrt(trading_days)

    Args:
        daily_returns: 日收益率序列
        risk_free_rate: 年化无风险利率（默认 2%）
        trading_days: 年化交易天数（默认 252）

    Returns:
        年化夏普比率。不足 2 个数据点时返回 0.0。
    """
    if len(daily_returns) < 2:
        return 0.0

    mean_return = sum(daily_returns) / len(daily_returns)
    if len(daily_returns) < 2:
        return 0.0

    variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    if variance == 0:
        return 0.0

    std_dev = math.sqrt(variance)
    daily_rf = risk_free_rate / trading_days
    excess_return = mean_return - daily_rf

    if std_dev == 0:
        return 0.0

    return (excess_return / std_dev) * math.sqrt(trading_days)


def calculate_max_drawdown(
    equity_curve: list[PortfolioSnapshot],
) -> float:
    """计算最大回撤

    遍历净值曲线，追踪峰值，计算从峰值到当前的最大跌幅。

    Returns:
        最大回撤（0.0–1.0，如 0.05 = 回撤 5%）。不足 2 个数据点时返回 0.0。
    """
    if len(equity_curve) < 2:
        return 0.0

    peak: float = 0.0
    max_dd: float = 0.0

    for snap in equity_curve:
        if snap.total_value > peak:
            peak = snap.total_value
        if peak > 0:
            dd = (peak - snap.total_value) / peak
            if dd > max_dd:
                max_dd = dd

    return max_dd


def calculate_win_rate(trades: list[TradeRecord]) -> tuple[int, int, float]:
    """计算胜率

    Args:
        trades: 交易记录列表

    Returns:
        (winning_trades, losing_trades, win_rate) 元组。
        win_rate 为 0.0–1.0。无交易时返回 (0, 0, 0.0)。
    """
    winning = sum(1 for t in trades if t.pnl > 0)
    losing = sum(1 for t in trades if t.pnl <= 0)
    total = winning + losing

    if total == 0:
        return 0, 0, 0.0

    return winning, losing, winning / total


def calculate_profit_factor(trades: list[TradeRecord]) -> float:
    """计算盈亏比（Profit Factor）

    Profit Factor = 总盈利 / abs(总亏损)

    Returns:
        盈亏比。无亏损时返回 0.0（无意义）。无交易时返回 0.0。
    """
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if gross_loss == 0:
        return 0.0

    return gross_profit / gross_loss if gross_loss > 0 else 0.0


def calculate_cagr(
    start_value: float,
    end_value: float,
    total_days: int,
) -> float:
    """计算复合年增长率（CAGR）

    CAGR = (end_value / start_value) ^ (365 / total_days) - 1

    Returns:
        年化复合增长率。参数无效时返回 0.0。
    """
    if start_value <= 0 or total_days <= 0:
        return 0.0

    ratio = end_value / start_value
    if ratio <= 0:
        return -1.0

    years = total_days / 365.0
    if years <= 0:
        return 0.0

    return ratio ** (1.0 / years) - 1.0


def calculate_avg_holding_days(trades: list[TradeRecord]) -> float:
    """计算平均持仓天数"""
    if not trades:
        return 0.0
    total_days = sum(t.holding_days for t in trades)
    return total_days / len(trades)


def calculate_annual_return(
    total_return: float,
    total_days: int,
) -> float:
    """根据总收益率和天数计算年化收益率"""
    if total_days <= 0:
        return 0.0
    years = total_days / 365.0
    if years <= 0:
        return 0.0
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def calculate_metrics(
    trades: list[TradeRecord],
    equity_curve: list[PortfolioSnapshot],
    config: BacktestConfig,
    total_days: int,
) -> PerformanceMetrics:
    """聚合计算全部绩效指标

    Args:
        trades: 交易记录列表
        equity_curve: 每日净值曲线
        config: 回测配置
        total_days: 回测总天数

    Returns:
        填充所有的 PerformanceMetrics 实例
    """
    # 从净值曲线提取日收益率
    daily_returns = calculate_daily_returns(equity_curve)

    # 胜率
    winning_trades, losing_trades, win_rate = calculate_win_rate(trades)

    # 总收益率
    total_return = 0.0
    if equity_curve and config.initial_capital > 0:
        total_return = (
            equity_curve[-1].total_value - config.initial_capital
        ) / config.initial_capital

    return PerformanceMetrics(
        total_return=total_return,
        annual_return=calculate_annual_return(total_return, total_days),
        max_drawdown=calculate_max_drawdown(equity_curve),
        sharpe_ratio=calculate_sharpe(daily_returns),
        win_rate=win_rate,
        profit_factor=calculate_profit_factor(trades),
        total_trades=len(trades),
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_holding_days=calculate_avg_holding_days(trades),
        cagr=calculate_cagr(
            start_value=config.initial_capital,
            end_value=equity_curve[-1].total_value if equity_curve else config.initial_capital,
            total_days=total_days,
        ),
    )

"""回测引擎 —— 策略历史表现评估

支持简单策略回测、收益计算、风险指标。
纯计算模块，不涉及 LLM 调用。

用法:
    from src.backtest.models import BacktestConfig, TradeRecord, BacktestReport
    from src.backtest.engine import BacktestEngine
    from src.data.models import KLine

    engine = BacktestEngine(BacktestConfig(initial_capital=1_000_000))
    report = await engine.run(trades, klines)
    print(report.metrics.sharpe_ratio, report.metrics.max_drawdown)
"""

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
    BacktestReport,
    PerformanceMetrics,
    PortfolioSnapshot,
    TradeRecord,
)

__all__ = [
    "BacktestConfig",
    "BacktestReport",
    "BacktestEngine",
    "PerformanceMetrics",
    "PortfolioSnapshot",
    "TradeRecord",
    "calculate_sharpe",
    "calculate_max_drawdown",
    "calculate_win_rate",
    "calculate_profit_factor",
    "calculate_cagr",
    "calculate_annual_return",
]

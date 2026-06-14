"""交易员模块 —— T1 交易执行规划层

T1 交易员层：
    PM 投资决策 → Trader 制定多步执行计划 → PM 最终审批

交易员职责将 PM 决策翻译为具体的、分步的、可执行的交易指令。
每步需要明确的价格条件或技术信号触发，避免一次性投入带来市场冲击。

执行纪律：
    - 单票 ≤20% / 首次 ≤50%目标仓位 / 现金 ≥10%
    - 硬止损 8% / ATR 动态止损
    - 盈利加仓 ≤50% / 连亏 3 笔熔断 3 日

用法:
    from src.trader.models import TradePlan, ExecutionStep, TraderRoundResult
    from src.trader.profiles import get_default_trader, TraderProfile
    from src.trader.orchestrator import make_trader_round_node
"""

from src.trader.models import ExecutionStep, TradePlan, TraderRoundResult
from src.trader.orchestrator import make_trader_round_node
from src.trader.profiles import TraderProfile, get_default_trader

__all__ = [
    "ExecutionStep",
    "TradePlan",
    "TraderRoundResult",
    "TraderProfile",
    "get_default_trader",
    "make_trader_round_node",
]

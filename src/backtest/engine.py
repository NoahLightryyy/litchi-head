"""回测引擎 —— BacktestEngine

核心流程：
  输入 TradeRecord 列表 + KLine 历史数据
  → 按时间顺序回放交易（入场建仓 → 逐日盯市 → 出场结算）
  → 追踪持仓变化 + 现金余额
  → 逐日记录 PortfolioSnapshot 净值曲线
  → 计算 PerformanceMetrics
  → 输出 BacktestReport

设计原则：
  - 每个 TradeRecord 代表一笔完整交易（同时含入场和出场信息）
  - 无状态引擎（方法不修改外部状态）
  - 纯计算模块，不涉及 LLM 调用
  - 与 debate/trader 模块解耦，只依赖 data.models.KLine
"""

from __future__ import annotations

import logging

from src.backtest.metrics import calculate_metrics
from src.backtest.models import (
    BacktestConfig,
    BacktestReport,
    PortfolioSnapshot,
    TradeRecord,
)
from src.data.models import KLine

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎

    模拟在历史 K 线数据上执行一组完整交易的完整过程，
    生成净值曲线和绩效指标。

    每个 TradeRecord 视为一笔完整交易（entry_date 建仓、exit_date 平仓）。
    引擎按日期顺序遍历 K 线：
      1. 入场日 → 按 entry_price 买入 quantity 股（扣除现金 + 费用）
      2. 持仓期间 → 每日按 close 价格计算持仓市值
      3. 出场日 → 按 exit_price 卖出 quantity 股（现金到账 + 记录 P&L）

    Usage:
        engine = BacktestEngine(config)
        report = await engine.run(trades, klines)
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    async def run(
        self,
        trades: list[TradeRecord],
        klines: list[KLine],
    ) -> BacktestReport:
        """执行回测

        Args:
            trades: 完整交易记录列表（每个 TradeRecord 含 entry + exit 信息）
            klines: 历史 K 线数据（用于市值计算和净值曲线）

        Returns:
            完整的 BacktestReport
        """
        if not klines:
            return BacktestReport(
                config=self.config,
                start_date="",
                end_date="",
                total_days=0,
            )

        # 按日期排序数据
        sorted_klines = sorted(klines, key=lambda k: k.date)
        sorted_trades = sorted(trades, key=lambda t: t.entry_date)

        start_date = sorted_klines[0].date
        end_date = sorted_klines[-1].date
        total_days = len(sorted_klines)

        # 初始化状态
        cash: float = self.config.initial_capital
        position_quantity: int = 0
        position_cost_basis: float = 0.0  # 持仓的总成本金额（用于计算平均成本）
        realized_trades: list[TradeRecord] = []
        equity_curve: list[PortfolioSnapshot] = []

        # 建立事件索引
        # direction="buy" → 入场事件（建仓）
        # direction="sell" → 出场事件（平仓）
        # 如果 buy 交易有关联 exit_date，也注册为出场事件
        entry_map: dict[str, list[TradeRecord]] = {}
        exit_map: dict[str, list[TradeRecord]] = {}
        ticker: str = ""

        for t in sorted_trades:
            if not ticker and t.ticker:
                ticker = t.ticker
            if t.direction == "buy":
                entry_map.setdefault(t.entry_date, []).append(t)
                # 如果买入交易自带了出场日期，注册一个出场事件
                if t.exit_date:
                    exit_map.setdefault(t.exit_date, []).append(t)
            elif t.direction == "sell" and t.exit_date:
                # 卖出交易只注册出场事件（入场信息在对应的买入交易中）
                exit_map.setdefault(t.exit_date, []).append(t)

        # 前一次总资产（用于日收益率计算）
        prev_total: float | None = None
        peak_value: float = 0.0

        # 逐日回放
        for kline in sorted_klines:
            date = kline.date
            current_price = kline.close

            # --- 入场事件 ---
            for trade in entry_map.get(date, []):
                entry_cost = trade.entry_price * trade.quantity * (
                    1.0 + self.config.commission_rate + self.config.slippage
                )
                if cash >= entry_cost:
                    cash -= entry_cost
                    position_quantity += trade.quantity
                    position_cost_basis += trade.entry_price * trade.quantity

            # --- 出场事件 ---
            for trade in exit_map.get(date, []):
                exit_proceeds = trade.exit_price * trade.quantity * (
                    1.0 - self.config.commission_rate - self.config.slippage
                )
                sell_qty = min(trade.quantity, position_quantity)
                if sell_qty > 0 and position_quantity > 0:
                    # 使用加权平均成本计算 P&L
                    avg_entry_price = position_cost_basis / position_quantity
                    cost_of_sold = avg_entry_price * sell_qty
                    realized_pnl = exit_proceeds - cost_of_sold

                    realized_trades.append(
                        TradeRecord(
                            ticker=trade.ticker,
                            direction="sell",
                            entry_date=trade.entry_date,
                            exit_date=trade.exit_date,
                            entry_price=round(avg_entry_price, 4),
                            exit_price=trade.exit_price,
                            quantity=sell_qty,
                            position_pct=trade.position_pct,
                            pnl=round(realized_pnl, 2),
                            pnl_pct=round(
                                realized_pnl / cost_of_sold, 6
                            ) if cost_of_sold > 0 else 0.0,
                            holding_days=_calc_holding_days(
                                trade.entry_date, trade.exit_date
                            ),
                            exit_reason=trade.exit_reason,
                        )
                    )

                    cash += exit_proceeds
                    position_quantity -= sell_qty
                    position_cost_basis -= avg_entry_price * sell_qty

            # --- 计算当前持仓市值和总资产 ---
            position_value = position_quantity * current_price
            total_value = cash + position_value

            # 追踪峰值（用于回撤）
            if total_value > peak_value:
                peak_value = total_value
            drawdown = (peak_value - total_value) / peak_value if peak_value > 0 else 0.0

            # 日收益率
            daily_return = 0.0
            if prev_total is not None and prev_total > 0:
                daily_return = (total_value - prev_total) / prev_total
            prev_total = total_value

            # 累计收益率
            cumulative_return = (
                (total_value - self.config.initial_capital) / self.config.initial_capital
                if self.config.initial_capital > 0
                else 0.0
            )

            equity_curve.append(
                PortfolioSnapshot(
                    date=date,
                    total_value=round(total_value, 2),
                    cash=round(cash, 2),
                    position_value=round(position_value, 2),
                    daily_return=round(daily_return, 6),
                    cumulative_return=round(cumulative_return, 6),
                    drawdown=round(drawdown, 6),
                )
            )

        # 计算绩效指标
        metrics = calculate_metrics(
            trades=realized_trades,
            equity_curve=equity_curve,
            config=self.config,
            total_days=total_days,
        )

        return BacktestReport(
            config=self.config,
            metrics=metrics,
            trades=realized_trades,
            equity_curve=equity_curve,
            start_date=start_date,
            end_date=end_date,
            ticker=ticker,
            total_days=total_days,
        )


def _calc_holding_days(entry_date: str, exit_date: str) -> int:
    """计算持仓天数（YYYY-MM-DD 格式的简化计算）"""
    if not entry_date or not exit_date:
        return 0
    try:
        parts_e = entry_date.split("-")
        parts_x = exit_date.split("-")
        if len(parts_e) == 3 and len(parts_x) == 3:
            days_e = int(parts_e[0]) * 365 + int(parts_e[1]) * 30 + int(parts_e[2])
            days_x = int(parts_x[0]) * 365 + int(parts_x[1]) * 30 + int(parts_x[2])
            return max(0, days_x - days_e)
    except (ValueError, IndexError) as e:
        logger.warning("持仓天数计算失败: entry=%s exit=%s, err=%s", entry_date, exit_date, e)
    return 0

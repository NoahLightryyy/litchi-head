"""TradePlan → TradeRecord 桥接转换

将 trader 模块产出的 TradePlan（含执行步骤、时机策略）转换为
backtest 模块可消费的 TradeRecord 列表。

设计原则：
  - 桥在产出方（trader/），消费方（backtest/）保持纯净
  - 纯函数，无 LLM 调用，无外部状态
  - 时机策略映射到 K 线数据是唯一非平凡的转换逻辑

用法:
    from src.trader.bridge import trade_plan_to_records

    records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
    report = await engine.run(records, klines)
"""

from __future__ import annotations

from src.backtest.models import TradeRecord
from src.data.models import KLine
from src.trader.models import TradePlan


def trade_plan_to_records(
    plan: TradePlan,
    klines: list[KLine],
    capital: float = 1_000_000.0,
) -> list[TradeRecord]:
    """将 TradePlan 转换为 TradeRecord 列表

    对 execution_steps 中的每一步：
      1. 按时机策略（"立即"/"等回调"/"等突破确认"）从 K 线中定位入场日期和价格
      2. 按 total_position_pct × step.quantity_pct 折算实际买入股数
      3. 以 time_horizon_days 为持有期计算出场日期和价格
      4. 生成一条完整的 TradeRecord（含入场+出场信息）

    Args:
        plan: trader 模块产出的交易计划
        klines: 历史 K 线数据（按日期排序）
        capital: 初始资金（用于将仓位比例折算为股数）

    Returns:
        TradeRecord 列表，可供 BacktestEngine.run() 直接消费
    """
    if not plan.success or not plan.execution_steps:
        return []

    if not klines:
        return []

    sorted_klines = sorted(klines, key=lambda k: k.date)
    target_capital = capital * plan.total_position_pct

    records: list[TradeRecord] = []

    for step in plan.execution_steps:
        if step.action == "hold":
            continue

        # 按时机策略定位入场
        entry_idx, entry_date, entry_price = _resolve_entry(
            step.timing, sorted_klines, {r.entry_date for r in records},
        )
        if entry_idx < 0:
            continue

        # 折算股数（整百股）
        step_capital = target_capital * step.quantity_pct
        quantity = int(step_capital / entry_price / 100) * 100
        if quantity <= 0:
            continue

        # 计算出场日期和价格
        exit_idx = entry_idx + plan.time_horizon_days
        if exit_idx >= len(sorted_klines):
            exit_idx = len(sorted_klines) - 1
        exit_date = sorted_klines[exit_idx].date
        exit_price = sorted_klines[exit_idx].close

        records.append(TradeRecord(
            ticker=plan.ticker,
            direction="buy",
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=round(entry_price, 4),
            exit_price=round(exit_price, 4),
            quantity=quantity,
            position_pct=round(plan.total_position_pct * step.quantity_pct, 4),
            exit_reason="持有到期",
        ))

    return records


def _resolve_entry(
    timing: str,
    klines: list[KLine],
    used_dates: set[str],
) -> tuple[int, str, float]:
    """按时机策略解析入场点和价格

    Args:
        timing: 时机策略（"立即"/"等回调"/"等突破确认"）
        klines: 排序后的 K 线数据
        used_dates: 已使用的日期集合（避免同一天重复入场）

    Returns:
        (index_in_klines, date_str, price)，找不到时 index 为 -1
    """
    if timing == "等回调":
        for i in range(1, len(klines)):
            if klines[i].close < klines[i - 1].close and klines[i].date not in used_dates:
                return i, klines[i].date, klines[i].close

    elif timing == "等突破确认":
        for i in range(2, len(klines)):
            prev_high = max(klines[i - 1].high, klines[i - 2].high)
            if klines[i].close > prev_high and klines[i].date not in used_dates:
                return i, klines[i].date, klines[i].close

    # "立即" 和兜底：取未使用的最早日期
    for i, k in enumerate(klines):
        if k.date not in used_dates:
            return i, k.date, k.close

    return -1, "", 0.0

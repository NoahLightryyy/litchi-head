"""回测 ←→ 辩论桥接适配器

在 TradePlan（交易员输出的执行计划）和 TradeRecord（回测引擎消费的交易记录）之间转换。
让辩论产生的交易计划可以直接喂入回测引擎验证绩效。

用法:
    from src.backtest.bridge import trade_plan_to_records, backtest_trade_plan

    records = trade_plan_to_records(trade_plan, klines)
    report = await backtest_trade_plan(trade_plan, klines)
    print(report.metrics.sharpe_ratio, report.metrics.max_drawdown)
"""

from __future__ import annotations

from src.backtest.engine import BacktestEngine
from src.backtest.models import BacktestConfig, BacktestReport, TradeRecord
from src.data.models import KLine


def trade_plan_to_records(
    trade_plan: object,
    klines: list[KLine] | None = None,
    entry_price: float | None = None,
    exit_price: float | None = None,
) -> list[TradeRecord]:
    """将 TradePlan 转换为 TradeRecord 列表

    把交易员的执行计划展开为回测引擎可消费的交易记录：
    1. direction 映射：Bullish → buy, Bearish → sell
    2. 每个 execution_step 展开为一条独立的 TradeRecord
    3. 入场/出场价格优先使用显式传入值，其次从 K 线推导

    Args:
        trade_plan: TraderPlan Pydantic 模型实例
        klines: 历史 K 线数据（用于推算默认价格和日期）
        entry_price: 入场价格，None 则取第一根 K 线 close
        exit_price: 出场价格，None 则取最后一根 K 线 close

    Returns:
        TradeRecord 列表（每步一条）

    Raises:
        ValueError: trade_plan 无执行步骤时
    """
    # 延迟导入，解耦运行时依赖
    from src.trader.models import TradePlan

    if not isinstance(trade_plan, TradePlan):
        raise TypeError(f"预期 TradePlan，收到 {type(trade_plan).__name__}")

    if not trade_plan.execution_steps:
        raise ValueError("TradePlan 没有执行步骤，无法生成 TradeRecord")

    # ── 方向映射 ────────────────────────────────────
    direction_map = {"Bullish": "buy", "Bearish": "sell", "Neutral": "hold"}
    direction = direction_map.get(trade_plan.direction, "hold")
    if direction == "hold":
        return []  # 无操作，不生成交易

    # ── 价格推导 ────────────────────────────────────
    resolved_entry_price: float | None = entry_price
    resolved_exit_price: float | None = exit_price

    if resolved_entry_price is None and klines:
        resolved_entry_price = klines[0].close
    if resolved_exit_price is None and klines:
        resolved_exit_price = klines[-1].close

    if resolved_entry_price is None:
        resolved_entry_price = 0.0
    if resolved_exit_price is None:
        resolved_exit_price = 0.0

    # ── 日期推导 ────────────────────────────────────
    entry_date: str = klines[0].date if klines else ""

    # 出场日期：按 time_horizon_days 从 K 线中找
    exit_date: str = ""
    if klines and trade_plan.time_horizon_days > 0:
        target_idx = min(trade_plan.time_horizon_days, len(klines) - 1)
        exit_date = klines[target_idx].date
    elif klines:
        exit_date = klines[-1].date

    # ── 展开执行步骤 → TradeRecord ──────────────────
    records: list[TradeRecord] = []
    total_position_pct = trade_plan.total_position_pct

    for step in trade_plan.execution_steps:
        step_action = step.action
        # 跳过 hold
        if step_action == "hold":
            continue

        # 每步仓位占比：相对总仓位的比例
        step_pct = total_position_pct * step.quantity_pct

        # 估算股数（基于入场价格）
        quantity = 0
        if resolved_entry_price > 0:
            # 假设初始资金 1M，仅用于估算数量
            notional = 1_000_000 * step_pct
            quantity = int(notional / resolved_entry_price)

        record = TradeRecord(
            ticker=trade_plan.ticker,
            direction=direction,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=round(resolved_entry_price, 4),
            exit_price=round(resolved_exit_price, 4),
            quantity=max(quantity, 0),
            position_pct=round(step_pct, 6),
            holding_days=trade_plan.time_horizon_days,
            exit_reason="持有到期",
            trade_plan={
                "action": step.action,
                "step": step.step,
                "timing": step.timing,
                "stop_loss_pct": step.stop_loss_pct,
                "price_condition": step.price_condition,
                "rationale": step.rationale,
                "time_horizon_days": trade_plan.time_horizon_days,
                "risk_reward_ratio": trade_plan.risk_reward_ratio,
                "contingency_plan": trade_plan.contingency_plan,
                "max_drawdown_limit": trade_plan.max_drawdown_limit,
                "position_sizing_method": trade_plan.position_sizing_method,
                "trader_notes": trade_plan.trader_notes,
            },
        )
        records.append(record)

    return records


def debate_result_to_records(
    debate_result: object,
    klines: list[KLine] | None = None,
) -> list[TradeRecord]:
    """从 DebateResult 中提取 TradePlan 并转换为 TradeRecord 列表

    高级封装 — 自动从辩论结果中提取交易员计划和推荐参数，
    适合端到端场景：一次辩论 → 直接回测。

    Args:
        debate_result: DebateResult Pydantic 模型实例
        klines: 历史 K 线数据
        config: 回测配置（仅用于提取入场/出场价格信号）

    Returns:
        TradeRecord 列表

    Raises:
        ValueError: DebateResult 中没有交易计划
    """
    from src.debate.models import DebateResult

    if not isinstance(debate_result, DebateResult):
        raise TypeError(
            f"预期 DebateResult，收到 {type(debate_result).__name__}"
        )

    # 从 trader_round 提取 TradePlan
    trader_round = debate_result.trader_round
    if not trader_round:
        raise ValueError("DebateResult 中没有 trader_round（交易计划）")

    trade_plan_data = trader_round.get("trade_plan")
    if not trade_plan_data:
        raise ValueError("trader_round 中没有 trade_plan")

    # 反序列化为 TradePlan
    from src.trader.models import TradePlan

    trade_plan = TradePlan(**trade_plan_data)

    # 优先使用 trade_recommendation 中的价格信号
    entry_price: float | None = None
    exit_price: float | None = None

    tr = debate_result.trade_recommendation or {}
    if tr:
        # 从推荐参数推导入场/出场价格
        if tr.get("stop_loss_pct"):
            # 取 klines 首根 close 作为参考
            if klines:
                base_price = klines[0].close
                entry_price = base_price
                stop_loss_pct = float(tr["stop_loss_pct"])  # type: ignore[arg-type]
                exit_price = round(base_price * (1.0 - stop_loss_pct), 4)

    return trade_plan_to_records(trade_plan, klines, entry_price, exit_price)


async def backtest_trade_plan(
    trade_plan: object,
    klines: list[KLine],
    config: BacktestConfig | None = None,
) -> BacktestReport:
    """将 TradePlan 直接喂入回测引擎

    一个函数完成「转换 + 回测」全流程：
    TradePlan → trade_plan_to_records → BacktestEngine.run → BacktestReport

    Args:
        trade_plan: TradePlan Pydantic 模型实例
        klines: 历史 K 线数据
        config: 回测配置，None 则使用默认

    Returns:
        完整的回测报告
    """
    records = trade_plan_to_records(trade_plan, klines)
    if not records:
        return BacktestReport(
            config=config or BacktestConfig(),
            start_date=klines[0].date if klines else "",
            end_date=klines[-1].date if klines else "",
            total_days=len(klines) if klines else 0,
        )
    engine = BacktestEngine(config)
    return await engine.run(records, klines)


async def backtest_debate_result(
    debate_result: object,
    klines: list[KLine],
    config: BacktestConfig | None = None,
) -> BacktestReport:
    """从 DebateResult 到回测的一步到位

    辩论结果 → 提取交易计划 → 回测 → 绩效报告

    Args:
        debate_result: DebateResult 实例
        klines: 历史 K 线数据
        config: 回测配置

    Returns:
        完整的回测报告
    """
    records = debate_result_to_records(debate_result, klines)
    if not records:
        return BacktestReport(
            config=config or BacktestConfig(),
            start_date=klines[0].date if klines else "",
            end_date=klines[-1].date if klines else "",
            total_days=len(klines) if klines else 0,
        )
    engine = BacktestEngine(config)
    return await engine.run(records, klines)


__all__ = [
    "backtest_debate_result",
    "backtest_trade_plan",
    "debate_result_to_records",
    "trade_plan_to_records",
]

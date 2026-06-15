"""src.trader.bridge 桥接层测试

覆盖场景：
1. 单步 "立即" → 正常转换
2. 多步分批建仓 → 每步在不同日期入场
3. 时机策略 — "等回调" 和 "等突破确认"
4. 边界 — 失败 plan、空 steps、空 klines、hold 指令
5. 端到端 — bridge → backtest engine 全链路
"""

from __future__ import annotations

import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.models import BacktestConfig
from src.data.models import KLine
from src.trader.bridge import trade_plan_to_records
from src.trader.models import ExecutionStep, TradePlan

# ── 测试辅助 ──────────────────────────────────────────


def _k(day: int, close: float, high: float | None = None) -> KLine:
    d = f"2024-06-{day:02d}"
    return KLine(date=d, open=close, close=close, high=high or close, low=close, volume=1_000_000)


def _klines(days: int = 10, base: float = 10.0) -> list[KLine]:
    return [_k(i + 1, base + i * 0.5) for i in range(days)]


# ══════════════════════════════════════════════════════
# 核心转换
# ══════════════════════════════════════════════════════


class TestBasicConversion:
    """基础转换场景"""

    def test_single_step_immediate(self) -> None:
        """单步立即执行 → 生成一条 TradeRecord"""
        plan = TradePlan(
            ticker="600519",
            direction="Bullish",
            action="buy",
            total_position_pct=0.5,
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="立即")],
            time_horizon_days=5,
        )
        klines = _klines(10)

        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)

        assert len(records) == 1
        r = records[0]
        assert r.ticker == "600519"
        assert r.direction == "buy"
        assert r.entry_date == "2024-06-01"
        assert r.entry_price == 10.0
        # 50 万买 10 元股 = 50000 股 → 整百 = 50000
        assert r.quantity == 50000
        assert r.position_pct == 0.5
        # 持有 5 天 → exit_date = 2024-06-06
        assert r.exit_date == "2024-06-06"
        assert r.exit_price == 12.5  # day 6 = 10+5*0.5 = 12.5
        assert r.exit_reason == "持有到期"

    def test_multi_step_dca(self) -> None:
        """三步分批建仓 → 三条记录，各自不同入场日期"""
        plan = TradePlan(
            ticker="600519",
            direction="Bullish",
            action="buy",
            total_position_pct=0.6,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=0.5, timing="立即"),
                ExecutionStep(step=2, action="buy", quantity_pct=0.3, timing="立即"),
                ExecutionStep(step=3, action="buy", quantity_pct=0.2, timing="立即"),
            ],
            time_horizon_days=3,
        )
        klines = _klines(10)

        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)

        assert len(records) == 3
        # 日期不应重复
        dates = [r.entry_date for r in records]
        assert len(set(dates)) == 3
        assert dates == ["2024-06-01", "2024-06-02", "2024-06-03"]
        # 总仓位 = 0.6
        total_pct = sum(r.position_pct for r in records)
        assert total_pct == pytest.approx(0.6, rel=0.01)
        # 每步仓位递减
        assert records[0].quantity > records[1].quantity > records[2].quantity

    def test_hold_action_skipped(self) -> None:
        """hold 指令的步骤跳过"""
        plan = TradePlan(
            ticker="600519",
            direction="Neutral",
            action="hold",
            total_position_pct=0.3,
            execution_steps=[
                ExecutionStep(step=1, action="hold", quantity_pct=1.0),
            ],
            time_horizon_days=5,
        )
        records = trade_plan_to_records(plan, _klines(), capital=1_000_000.0)
        assert len(records) == 0


# ══════════════════════════════════════════════════════
# 时机策略
# ══════════════════════════════════════════════════════


class TestTimingStrategies:
    """不同时机策略的入场点解析"""

    def test_immediate_uses_first_date(self) -> None:
        """"立即" → 取首个 K 线日"""
        plan = TradePlan(
            ticker="000001",
            total_position_pct=0.5,
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="立即")],
            time_horizon_days=3,
        )
        records = trade_plan_to_records(plan, _klines(5), capital=1_000_000.0)
        assert records[0].entry_date == "2024-06-01"

    def test_pullback_finds_dip(self) -> None:
        """等回调 → 找到收盘价比前一日低的日期"""
        klines = [
            _k(1, 10.0),
            _k(2, 11.0),
            _k(3, 10.5),  # 回调
            _k(4, 12.0),
            _k(5, 11.8),  # 回调
        ]
        plan = TradePlan(
            ticker="000001",
            total_position_pct=0.5,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="等回调"),
            ],
            time_horizon_days=2,
        )
        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        assert len(records) == 1
        # 首个回调日在 day 3: 10.5 < 11.0
        assert records[0].entry_date == "2024-06-03"
        assert records[0].entry_price == 10.5

    def test_breakout_finds_breakout(self) -> None:
        """等突破确认 → 找到收盘价突破前两日高点的日期"""
        klines = [
            _k(1, 10.0, high=10.0),
            _k(2, 10.2, high=10.3),
            _k(3, 10.1, high=10.2),  # 不突破
            _k(4, 10.5, high=10.6),  # 突破前两日高点 10.3
        ]
        plan = TradePlan(
            ticker="000001",
            total_position_pct=0.5,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="等突破确认"),
            ],
            time_horizon_days=2,
        )
        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        assert len(records) == 1
        assert records[0].entry_date == "2024-06-04"

    def test_fallback_when_strategy_no_match(self) -> None:
        """回调策略但无回调 → 兜底到最早可用日期"""
        klines = [_k(i, 10.0 + i) for i in range(1, 6)]  # 严格上涨，无回调
        plan = TradePlan(
            ticker="000001",
            total_position_pct=0.5,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="等回调"),
            ],
            time_horizon_days=2,
        )
        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        assert len(records) == 1
        # 兜底到最早可用日期
        assert records[0].entry_date == "2024-06-01"


# ══════════════════════════════════════════════════════
# 边界情况
# ══════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况"""

    def test_failed_plan(self) -> None:
        """success=False → 空列表"""
        plan = TradePlan(ticker="600519", success=False, error="超时")
        assert trade_plan_to_records(plan, _klines()) == []

    def test_no_steps(self) -> None:
        """空 execution_steps → 空列表"""
        plan = TradePlan(ticker="600519", execution_steps=[])
        assert trade_plan_to_records(plan, _klines()) == []

    def test_empty_klines(self) -> None:
        """空 K 线 → 空列表"""
        plan = TradePlan(
            ticker="600519",
            total_position_pct=0.5,
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0)],
        )
        assert trade_plan_to_records(plan, []) == []

    def test_quantity_rounding(self) -> None:
        """小资金 + 高价 → 股数不足一手 → 该步跳过"""
        plan = TradePlan(
            ticker="600519",
            total_position_pct=0.1,  # 10 万
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="立即")],
            time_horizon_days=5,
        )
        klines = [_k(1, 1000.0)]  # 1000 元/股
        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        # 10 万 / 1000 = 100 股 → 整百 = 100，刚好一手
        assert len(records) == 1
        assert records[0].quantity == 100

    def test_exit_beyond_klines(self) -> None:
        """exit 超出 K 线范围 → 截断到最后一日"""
        plan = TradePlan(
            ticker="000001",
            total_position_pct=0.5,
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="立即")],
            time_horizon_days=100,  # 远超 K 线长度
        )
        records = trade_plan_to_records(plan, _klines(5), capital=1_000_000.0)
        assert records[0].exit_date == "2024-06-05"  # 最后一日


# ══════════════════════════════════════════════════════
# 端到端
# ══════════════════════════════════════════════════════


class TestEndToEnd:
    """bridge → backtest engine 全链路"""

    async def test_bridge_to_engine_full(self) -> None:
        """桥接输出直接喂回测引擎 → 产出正确指标"""
        klines = [_k(i, 10.0) for i in range(1, 11)]  # 横盘
        plan = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=1.0,
            execution_steps=[ExecutionStep(step=1, action="buy", quantity_pct=1.0, timing="立即")],
            time_horizon_days=5,
        )

        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        assert len(records) == 1

        engine = BacktestEngine(BacktestConfig(commission_rate=0.0, slippage=0.0))
        report = await engine.run(records, klines)

        assert report.metrics.total_trades >= 1
        assert report.ticker == "000001"

    async def test_multi_step_in_engine(self) -> None:
        """三步分批 → 回测引擎正确追踪每步入场"""
        klines = [_k(i, 10.0) for i in range(1, 15)]  # 14 天
        plan = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=0.6,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=0.5, timing="立即"),
                ExecutionStep(step=2, action="buy", quantity_pct=0.3, timing="立即"),
                ExecutionStep(step=3, action="buy", quantity_pct=0.2, timing="立即"),
            ],
            time_horizon_days=3,
        )

        records = trade_plan_to_records(plan, klines, capital=1_000_000.0)
        engine = BacktestEngine(BacktestConfig(commission_rate=0.0, slippage=0.0))
        report = await engine.run(records, klines)

        assert report.metrics.total_trades == 3
        # 每笔独立清算
        assert report.metrics.winning_trades + report.metrics.losing_trades == 3

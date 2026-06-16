"""回测—辩论桥接适配器测试

覆盖 trade_plan_to_records / debate_result_to_records / backtest_trade_plan
三种接口的单元测试，含边界条件（空步骤、Neutral 方向、无价格数据）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from src.backtest.bridge import debate_result_to_records, trade_plan_to_records
from src.backtest.models import BacktestConfig, TradeRecord
from src.data.models import KLine

# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def sample_trade_plan() -> Any:
    """构建一个标准 TradePlan 实例"""
    from src.trader.models import ExecutionStep, TradePlan

    return TradePlan(
        ticker="000001",
        direction="Bullish",
        action="buy",
        total_position_pct=0.5,
        time_horizon_days=20,
        risk_reward_ratio=2.5,
        max_drawdown_limit=0.08,
        position_sizing_method="fixed_fraction",
        contingency_plan="若大盘单日跌超3%则暂停加仓",
        trader_notes="测试交易计划",
        confidence=0.8,
        execution_steps=[
            ExecutionStep(
                step=1,
                action="buy",
                quantity_pct=0.4,
                timing="立即",
                price_condition="市价",
                rationale="首批建仓",
            ),
            ExecutionStep(
                step=2,
                action="buy",
                quantity_pct=0.3,
                timing="等回调",
                price_condition="跌幅达2%",
                rationale="回调加仓",
            ),
            ExecutionStep(
                step=3,
                action="buy",
                quantity_pct=0.3,
                timing="等突破确认",
                price_condition="突破20日均线",
                rationale="突破确认加仓",
            ),
        ],
    )


@pytest.fixture
def neutral_trade_plan() -> Any:
    """Neutral 方向（应返回空列表）"""
    from src.trader.models import ExecutionStep, TradePlan

    return TradePlan(
        ticker="000001",
        direction="Neutral",
        action="hold",
        total_position_pct=0.0,
        execution_steps=[
            ExecutionStep(step=1, action="hold", quantity_pct=0.0, timing="观望"),
        ],
    )


@pytest.fixture
def empty_steps_trade_plan() -> Any:
    """无执行步骤的 TradePlan（应报错）"""
    from src.trader.models import TradePlan

    return TradePlan(
        ticker="000001",
        direction="Bullish",
        action="buy",
        total_position_pct=0.5,
        execution_steps=[],
    )


@pytest.fixture
def sample_klines() -> list[KLine]:
    """构建 30 根日 K 线"""
    klines: list[KLine] = []
    base_date = datetime(2025, 1, 2)
    price = 10.0
    for i in range(30):
        date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        klines.append(
            KLine(
                date=date_str,
                open=price,
                close=price + 0.05 * (i % 3 - 1),
                high=price + 0.1,
                low=price - 0.1,
                volume=1_000_000,
            )
        )
        price += 0.1
    return klines


# ── trade_plan_to_records ────────────────────────────────


class TestTradePlanToRecords:
    """测试 TradePlan → TradeRecord 转换"""

    def test_basic_conversion(self, sample_trade_plan: Any, sample_klines: list[KLine]) -> None:
        """基本转换：Bullish → 3 条 buy 记录"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)

        assert len(records) == 3  # 3 步展开
        assert all(r.direction == "buy" for r in records)
        assert all(r.ticker == "000001" for r in records)
        assert all(r.exit_reason == "持有到期" for r in records)

    def test_entry_price_from_klines(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """入场价格取第一根 K 线 close"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        expected_price = round(sample_klines[0].close, 4)
        assert all(r.entry_price == expected_price for r in records)

    def test_exit_date_from_time_horizon(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """出场日期 = time_horizon_days 偏移"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        expected_date = sample_klines[20].date  # time_horizon_days=20
        assert records[0].exit_date == expected_date

    def test_position_pct_multiplication(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """仓位比例 = total_position_pct × 每步 quantity_pct"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        # step1: 0.5 * 0.4 = 0.2
        assert records[0].position_pct == pytest.approx(0.2, rel=1e-6)

    def test_exit_price_override(self, sample_trade_plan: Any, sample_klines: list[KLine]) -> None:
        """显式传 exit_price 生效"""
        records = trade_plan_to_records(
            sample_trade_plan, sample_klines, exit_price=12.5
        )
        assert all(r.exit_price == 12.5 for r in records)

    def test_entry_price_override(self, sample_trade_plan: Any, sample_klines: list[KLine]) -> None:
        """显式传 entry_price 生效"""
        records = trade_plan_to_records(
            sample_trade_plan, sample_klines, entry_price=9.5
        )
        assert all(r.entry_price == 9.5 for r in records)

    def test_no_klines(self, sample_trade_plan: Any) -> None:
        """无 K 线数据：价格为 0，日期为空"""
        records = trade_plan_to_records(sample_trade_plan)
        assert len(records) == 3
        assert records[0].entry_price == 0.0
        assert records[0].entry_date == ""

    def test_neutral_returns_empty(self, neutral_trade_plan: Any) -> None:
        """Neutral 方向不生成交易记录"""
        records = trade_plan_to_records(neutral_trade_plan)
        assert records == []

    def test_empty_steps_raises(self, empty_steps_trade_plan: Any) -> None:
        """无执行步骤时抛出 ValueError"""
        with pytest.raises(ValueError, match="没有执行步骤"):
            trade_plan_to_records(empty_steps_trade_plan)

    def test_invalid_type_raises(self) -> None:
        """传入非 TradePlan 类型抛出 TypeError"""
        with pytest.raises(TypeError, match="预期 TradePlan"):
            trade_plan_to_records({"not": "a trade plan"})  # type: ignore[arg-type]

    def test_all_fields_transferred(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """trade_plan 中所有元数据写入 trade_plan 字典字段"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        tp = records[0].trade_plan
        assert tp["time_horizon_days"] == 20
        assert tp["risk_reward_ratio"] == 2.5
        assert tp["contingency_plan"] == "若大盘单日跌超3%则暂停加仓"
        assert tp["position_sizing_method"] == "fixed_fraction"
        assert float(tp["max_drawdown_limit"]) == 0.08
        assert tp["step"] == 1
        assert tp["rationale"] == "首批建仓"

    def test_quantity_estimation(self, sample_trade_plan: Any, sample_klines: list[KLine]) -> None:
        """quantity 按仓位 × 1M / entry_price 估算"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        entry = records[0].entry_price
        expected_qty = int(1_000_000 * 0.2 / entry)
        assert records[0].quantity == expected_qty

    def test_returns_trade_record_list(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """返回类型正确"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        assert all(isinstance(r, TradeRecord) for r in records)

    def test_holding_days_filled(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """holding_days = time_horizon_days"""
        records = trade_plan_to_records(sample_trade_plan, sample_klines)
        assert all(r.holding_days == 20 for r in records)


# ── debate_result_to_records ─────────────────────────


class TestDebateResultToRecords:
    """测试 DebateResult → TradeRecord 转换"""

    @pytest.fixture
    def debate_result_with_trader_round(self, sample_trade_plan: Any) -> Any:
        """构建含交易员输出的 DebateResult"""
        from src.debate.models import DebateResult

        return DebateResult(
            session_id="test-session-bridge",
            stock_code="000001",
            stock_name="测试股票",
            question="测试桥接",
            trader_round={
                "trade_plan": sample_trade_plan.model_dump(),
                "execution_summary": "测试执行",
            },
            trade_recommendation={
                "stop_loss_pct": 0.05,
                "action": "buy",
                "risk_level": "中等风险",
            },
        )

    def test_extract_trade_plan(
        self, debate_result_with_trader_round: Any, sample_klines: list[KLine]
    ) -> None:
        """从 DebateResult 提取 TradePlan 并正确转换"""
        records = debate_result_to_records(
            debate_result_with_trader_round, sample_klines
        )
        assert len(records) == 3
        assert records[0].ticker == "000001"
        assert records[0].direction == "buy"

    def test_no_trader_round_raises(self, sample_klines: list[KLine]) -> None:
        """没有 trader_round 时抛出 ValueError"""
        from src.debate.models import DebateResult

        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="测试",
            question="测试",
        )
        with pytest.raises(ValueError, match="没有 trader_round"):
            debate_result_to_records(result, sample_klines)

    def test_invalid_type_raises(self, sample_klines: list[KLine]) -> None:
        """传入非 DebateResult 类型抛出 TypeError"""
        with pytest.raises(TypeError, match="预期 DebateResult"):
            debate_result_to_records({"not": "debate result"}, sample_klines)  # type: ignore[arg-type]


# ── backtest_trade_plan（集成方向）────────────────────


class TestBacktestTradePlan:
    """测试 bridge 到回测引擎的连通"""

    @pytest.mark.asyncio
    async def test_backtest_trade_plan(
        self, sample_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """TradePlan → backtest_trade_plan() → BacktestReport"""
        from src.backtest.bridge import backtest_trade_plan

        report = await backtest_trade_plan(
            sample_trade_plan, sample_klines, BacktestConfig(initial_capital=1_000_000)
        )
        assert report.metrics.total_trades > 0
        assert report.ticker == "000001"
        assert report.total_days == 30
        assert report.config.initial_capital == 1_000_000

    @pytest.mark.asyncio
    async def test_backtest_neutral_returns_empty_report(
        self, neutral_trade_plan: Any, sample_klines: list[KLine]
    ) -> None:
        """Neutral 方向回测返回空报告（0 交易）"""
        from src.backtest.bridge import backtest_trade_plan

        report = await backtest_trade_plan(neutral_trade_plan, sample_klines)
        assert report.metrics.total_trades == 0


class TestBacktestDebateResult:
    """测试辩论结果直接回测"""

    @pytest.mark.asyncio
    async def test_backtest_debate_result(
        self, sample_klines: list[KLine]
    ) -> None:
        """DebateResult → backtest_debate_result() → BacktestReport"""
        from src.backtest.bridge import backtest_debate_result
        from src.debate.models import DebateResult
        from src.trader.models import ExecutionStep, TradePlan

        # 内联构建
        tp = TradePlan(
            ticker="600519",
            direction="Bullish",
            action="buy",
            total_position_pct=0.8,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=0.5, timing="立即"),
                ExecutionStep(step=2, action="buy", quantity_pct=0.5, timing="分批"),
            ],
        )
        result = DebateResult(
            session_id="e2e-test",
            stock_code="600519",
            stock_name="贵州茅台",
            question="测试",
            trader_round={"trade_plan": tp.model_dump()},
        )
        report = await backtest_debate_result(result, sample_klines)
        assert report.metrics.total_trades > 0
        assert report.ticker == "600519"

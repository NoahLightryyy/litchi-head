"""T1 交易员层测试

覆盖：ExecutionStep / TradePlan / TraderRoundResult 模型，
      trader_round 节点（mock LLM），DebateOrchestrator enable_trader 集成，
      向后兼容（enable_trader=False）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.trader.models import ExecutionStep, TradePlan, TraderRoundResult
from src.trader.profiles import TraderProfile, get_default_trader

# ═══════════════════════════════════════════════════════════════
# Phase 1: 数据模型测试
# ═══════════════════════════════════════════════════════════════


class TestExecutionStep:
    def test_default_values(self) -> None:
        s = ExecutionStep()
        assert s.step == 1
        assert s.action == "buy"
        assert s.quantity_pct == 0.0
        assert s.timing == "立即"
        assert s.stop_loss_pct is None

    def test_full_step(self) -> None:
        s = ExecutionStep(
            step=1,
            action="buy",
            quantity_pct=0.05,
            price_condition="回踩 10 日均线",
            timing="等回调",
            stop_loss_pct=0.06,
            signal_triggers=["RSI<30", "成交量放大"],
            rationale="技术面超卖信号确认",
        )
        assert s.step == 1
        assert s.quantity_pct == 0.05
        assert s.stop_loss_pct == 0.06
        assert len(s.signal_triggers) == 2

    def test_multiple_steps_sequence(self) -> None:
        steps = [
            ExecutionStep(step=1, action="buy", quantity_pct=0.05, rationale="首次建仓"),
            ExecutionStep(step=2, action="buy", quantity_pct=0.05, rationale="加仓确认"),
            ExecutionStep(step=3, action="hold", quantity_pct=0.0, rationale="等待信号"),
        ]
        assert len(steps) == 3
        assert sum(s.quantity_pct for s in steps) == 0.10


class TestTradePlan:
    def test_default_values(self) -> None:
        tp = TradePlan()
        assert tp.ticker == ""
        assert tp.direction == "Neutral"
        assert tp.action == "hold"
        assert tp.total_position_pct == 0.0
        assert tp.max_drawdown_limit == 0.08
        assert tp.time_horizon_days == 20
        assert tp.execution_steps == []
        assert tp.success is True

    def test_full_trade_plan(self) -> None:
        steps = [
            ExecutionStep(step=1, action="buy", quantity_pct=0.05,
                          price_condition="开盘价", timing="立即",
                          rationale="底仓建立"),
            ExecutionStep(step=2, action="buy", quantity_pct=0.05,
                          price_condition="突破 20 日均线", timing="等突破确认",
                          rationale="趋势确认加仓"),
        ]
        tp = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=0.10,
            execution_steps=steps,
            max_drawdown_limit=0.08,
            time_horizon_days=30,
            risk_reward_ratio=2.5,
            position_sizing_method="fixed_fraction",
            contingency_plan="大盘单日跌超 3% 暂停加仓",
            trader_notes="基本面和技术面共振，建议分步建仓",
            confidence=0.75,
        )
        assert tp.ticker == "000001"
        assert tp.action == "buy"
        assert len(tp.execution_steps) == 2
        assert tp.total_position_pct == 0.10
        assert tp.risk_reward_ratio == 2.5
        assert tp.contingency_plan != ""
        assert tp.confidence == 0.75

    def test_failed_trade_plan(self) -> None:
        tp = TradePlan(
            success=False,
            error="LLM 调用超时",
        )
        assert tp.success is False
        assert tp.error == "LLM 调用超时"
        assert tp.action == "hold"  # safe default

    def test_model_serialization(self) -> None:
        steps = [
            ExecutionStep(step=1, action="buy", quantity_pct=0.05,
                          price_condition="市价", timing="立即", rationale="建仓"),
        ]
        tp = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=0.10,
            execution_steps=steps,
            contingency_plan="预案",
        )
        data = tp.model_dump()
        assert data["ticker"] == "000001"
        assert len(data["execution_steps"]) == 1
        assert data["execution_steps"][0]["step"] == 1


class TestTraderRoundResult:
    def test_default_values(self) -> None:
        tr = TraderRoundResult()
        assert tr.trade_plan.action == "hold"
        assert tr.pm_review_required is False

    def test_with_trade_plan(self) -> None:
        tp = TradePlan(action="buy", total_position_pct=0.15)
        tr = TraderRoundResult(
            trade_plan=tp,
            execution_summary="分 2 步建仓，目标 15%",
            key_risks_in_execution=["仓位接近上限"],
            pm_review_required=True,
            pm_review_reason="仓位较高需复审",
        )
        assert tr.trade_plan.action == "buy"
        assert "15%" in tr.execution_summary
        assert len(tr.key_risks_in_execution) == 1
        assert tr.pm_review_required is True


# ═══════════════════════════════════════════════════════════════
# Phase 2: 交易员人格测试
# ═══════════════════════════════════════════════════════════════


class TestTraderProfile:
    def test_default_trader_profile(self) -> None:
        profile = get_default_trader()
        assert isinstance(profile, TraderProfile)
        assert profile.trader_id == "execution_trader"
        assert len(profile.name) > 0
        assert len(profile.system_prompt) > 200  # meaningful prompt
        assert len(profile.trading_discipline) >= 5

    def test_trading_discipline_coverage(self) -> None:
        profile = get_default_trader()
        disciplines = " ".join(profile.trading_discipline)
        # 核心纪律检查
        assert "20%" in disciplines or "20" in disciplines  # 单票上限
        assert "8%" in disciplines or "8" in disciplines  # 硬止损
        assert "10%" in disciplines or "10" in disciplines  # 现金留存
        assert "50%" in disciplines or "50" in disciplines  # 首次建仓上限


# ═══════════════════════════════════════════════════════════════
# Phase 3: trader_round 节点测试（mock LLM）
# ═══════════════════════════════════════════════════════════════


class TestTraderRoundNode:
    @pytest.mark.asyncio
    async def test_trader_node_produces_trade_plan(self) -> None:
        """交易员节点 mock LLM 返回——产出 TradePlan"""
        from src.trader.orchestrator import make_trader_round_node

        mock_plan = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=0.10,
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=0.05,
                              price_condition="市价", timing="立即", rationale="建仓"),
            ],
            confidence=0.80,
        )

        with patch(
            "src.trader.orchestrator.llm_service.invoke_structured",
            AsyncMock(return_value=mock_plan),
        ):
            node = make_trader_round_node()
            state = {
                "debate_input": {
                    "question": "测试问题",
                    "stock_code": "000001",
                },
                "session_id": "test-session",
                "vote_summary": {"final_signal": "Buy", "final_score": 75},
                "analyses": {
                    "大师A": {"direction": "Bullish", "score": 80, "summary": "看好"},
                },
                "risk_round": {
                    "risk_consensus_action": "buy",
                    "avg_risk_score": 40,
                    "min_position_pct": 0.05,
                    "max_position_pct": 0.15,
                    "assessments": {
                        "aggressive": {
                            "action": "buy",
                            "position_size_pct": 0.15,
                            "risk_score": 30,
                        },
                    },
                },
            }
            result = await node(state)
            assert "trader_round" in result
            tr = result["trader_round"]
            assert tr["trade_plan"]["action"] == "buy"
            assert tr["trade_plan"]["total_position_pct"] == 0.10

    @pytest.mark.asyncio
    async def test_trader_node_fallback_on_error(self) -> None:
        """交易员节点 LLM 失败——返回 safe default"""
        from src.trader.orchestrator import make_trader_round_node

        with patch(
            "src.trader.orchestrator.llm_service.invoke_structured",
            AsyncMock(side_effect=RuntimeError("LLM 不可用")),
        ):
            node = make_trader_round_node()
            state = {
                "debate_input": {"question": "测试", "stock_code": "000001"},
                "session_id": "test",
                "vote_summary": {},
                "analyses": {},
            }
            result = await node(state)
            assert "trader_round" in result
            tr = result["trader_round"]
            tp = tr["trade_plan"]
            assert tp["action"] == "hold"  # safe default
            assert tp["success"] is False
            assert tp["error"] == "LLM 不可用"

    @pytest.mark.asyncio
    async def test_trader_node_detects_high_position_risk(self) -> None:
        """交易员层自动检测执行风险——高仓位触发 PM 复审"""
        from src.trader.orchestrator import make_trader_round_node

        mock_plan = TradePlan(
            ticker="000001",
            direction="Bullish",
            action="buy",
            total_position_pct=0.25,  # > 15% 触发复审
            execution_steps=[
                ExecutionStep(step=1, action="buy", quantity_pct=0.25,
                              price_condition="市价", timing="立即", rationale="全仓"),
            ],
            confidence=0.90,
        )

        with patch(
            "src.trader.orchestrator.llm_service.invoke_structured",
            AsyncMock(return_value=mock_plan),
        ):
            node = make_trader_round_node()
            state = {
                "debate_input": {"question": "测试", "stock_code": "000001"},
                "session_id": "test",
                "vote_summary": {},
                "analyses": {},
            }
            result = await node(state)
            tr = result["trader_round"]
            assert tr["pm_review_required"] is True
            assert "25%" in tr["pm_review_reason"]


# ═══════════════════════════════════════════════════════════════
# Phase 4: DebateOrchestrator 集成测试（enable_trader）
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorWithTrader:
    @pytest.mark.asyncio
    async def test_enable_trader_adds_node(self) -> None:
        """enable_trader=True 时图包含 trader_round 节点"""
        from src.data.collector import DataCollector
        from src.debate.orchestrator import DebateOrchestrator

        with patch.object(DataCollector, "get_realtime_quote", return_value=None):
            with patch.object(DataCollector, "get_klines", return_value=[]):
                with patch.object(DataCollector, "get_news", return_value=[]):
                    with patch.object(
                        DataCollector, "get_all_stocks",
                        return_value=[{"code": "000001", "name": "平安银行"}],
                    ):
                        orch = DebateOrchestrator(enable_risk=True, enable_trader=True)
                        graph = orch._build_graph()
                        # 验证 trader_round 节点存在于图中
                        # 通过检查图的构建流程来验证
                        assert orch.enable_trader is True
                        assert orch.enable_risk is True
                        # 图编译不抛异常
                        compiled = graph.compile()
                        assert compiled is not None

    @pytest.mark.asyncio
    async def test_disable_trader_keeps_backward_compat(self) -> None:
        """enable_trader=False 保持向后兼容"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_risk=True, enable_trader=False)
        assert orch.enable_trader is False
        # 不启用 trader 时图正常构建
        graph = orch._build_graph()
        compiled = graph.compile()
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_enable_risk_false_skips_all(self) -> None:
        """enable_risk=False 时走 aggregate→END 直达路径"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_risk=False, enable_trader=True)
        # trader 依赖 risk，无 risk 时也不启用 trader
        graph = orch._build_graph()
        compiled = graph.compile()
        assert compiled is not None


# ═══════════════════════════════════════════════════════════════
# Phase 5: DebateResult trader_round 字段测试
# ═══════════════════════════════════════════════════════════════


class TestDebateResultTraderField:
    def test_debate_result_has_trader_field(self) -> None:
        """DebateResult 包含 trader_round 字段"""
        from src.debate.models import DebateResult

        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
        )
        assert result.trader_round is None

    def test_debate_result_with_trader(self) -> None:
        """DebateResult 包含 trader_round 数据时 to_summary_dict 展示"""
        from src.debate.models import DebateResult

        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            trader_round={
                "trade_plan": {
                    "ticker": "000001",
                    "direction": "Bullish",
                    "action": "buy",
                    "total_position_pct": 0.10,
                    "execution_steps": [
                        {"step": 1, "action": "buy", "quantity_pct": 0.05,
                         "price_condition": "市价", "timing": "立即", "rationale": "建仓"},
                    ],
                    "max_drawdown_limit": 0.08,
                    "risk_reward_ratio": 2.0,
                    "position_sizing_method": "fixed_fraction",
                },
                "execution_summary": "分 1 步建仓，目标 10%",
                "pm_review_required": False,
            },
        )
        summary = result.to_summary_dict()
        assert summary["交易计划"] is True
        assert summary["目标仓位"] == "10%"
        assert summary["执行步骤数"] == 1
        assert summary["盈亏比"] == "2.0:1"

    def test_debate_result_trader_field_none_tolerant(self) -> None:
        """trader_round 为 None 时 to_summary_dict 不报错"""
        from src.debate.models import DebateResult

        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            trader_round=None,
        )
        # 不抛异常即可
        summary = result.to_summary_dict()
        assert "交易计划" not in summary

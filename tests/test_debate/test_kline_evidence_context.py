"""KR-4A debate consumption of the frozen four-layer K-line result."""

from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.data.evidence import SourceStatus
from src.data.intraday import IntradayBarState
from src.data.kline import MarketCode
from src.data.kline_adjustment import AdjustedDailyBar, AdjustedKlineSeries
from src.data.kline_business import (
    FinalMinuteBar,
    KlineBusinessEnvelope,
    KlineBusinessFailure,
    KlineBusinessLayer,
    KlineLayerDiagnostic,
    KlineRetryDisposition,
    KlineSourceDiagnostic,
    LiveRawQuote,
    ProvisionalSessionBar,
    TradingPhase,
)
from src.debate.evidence_gate import EvidenceIncompleteError
from src.debate.kline_context import (
    classify_kline_business_result,
    format_kline_business_context,
    kline_evidence_reference,
    kline_failure_limitation,
)
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    DebateInput,
    IndependentReview,
    RebuttalAnalysis,
)
from src.debate.orchestrator import (
    DebateOrchestrator,
    DebateState,
    _route_after_collection,
    collect_data_node,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
AS_OF = datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI)


@pytest.fixture(autouse=True)
def isolate_live_review_calls() -> Iterator[None]:
    """Evidence tests must never call a paid model using local credentials."""
    with (
        patch("src.debate.orchestrator._run_independent_review",
              new_callable=AsyncMock, return_value=IndependentReview()),
        patch("src.debate.orchestrator._run_review_for_master",
              new_callable=AsyncMock,
              return_value=RebuttalAnalysis(agent_name="master.test")),
    ):
        yield


def _complete_result() -> KlineBusinessEnvelope:
    daily_at = datetime(2026, 8, 3, 15, 5, tzinfo=SHANGHAI)
    return KlineBusinessEnvelope(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=AdjustedKlineSeries(
            raw_snapshot_id="raw:000001:2026-08-03",
            factor_source_ids=("cninfo", "sina-qfq"),
            factor_version="factor-v1",
            reference_date=date(2026, 8, 3),
            raw_snapshot_as_of=daily_at,
            raw_completed_through=date(2026, 8, 3),
            as_of=daily_at,
            bars=(
                AdjustedDailyBar(
                    code="000001",
                    market=MarketCode.SZSE,
                    trade_date=date(2026, 8, 3),
                    open=Decimal("10.00"),
                    high=Decimal("10.30"),
                    low=Decimal("9.90"),
                    close=Decimal("10.20"),
                    volume=Decimal("1000000"),
                    amount=Decimal("10100000.00"),
                ),
            ),
        ),
        daily_upstream_ids=("sina", "tencent"),
        final_minute_bars=(
            FinalMinuteBar(
                code="000001",
                timestamp=datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI),
                open=10.20,
                high=10.25,
                low=10.19,
                close=10.24,
                volume=20_000,
                amount=204_500.0,
                state=IntradayBarState.FINAL,
            ),
        ),
        intraday_upstream_ids=("eastmoney", "tencent"),
        live_quote=LiveRawQuote(
            code="000001",
            name="平安银行",
            price=10.25,
            change=0.05,
            change_pct=0.49,
            volume=1_200_000,
            amount=12_250_000.0,
            high=10.30,
            low=10.10,
            open_=10.20,
            prev_close=10.20,
            fetched_at=AS_OF,
        ),
        quote_upstream_ids=("eastmoney", "sina"),
        provisional_session_bar=ProvisionalSessionBar(
            code="000001",
            market=MarketCode.SZSE,
            trading_date=date(2026, 8, 4),
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            open=Decimal("10.20"),
            high=Decimal("10.30"),
            low=Decimal("10.10"),
            close=Decimal("10.25"),
            cumulative_volume=1_200_000,
            cumulative_amount=Decimal("12250000.00"),
            upstream_ids=("eastmoney", "sina"),
        ),
    )


def _failure(*, blocked: bool) -> KlineBusinessFailure:
    retry = (
        KlineRetryDisposition.OPERATOR_ACTION
        if blocked
        else KlineRetryDisposition.RETRY_FRESH
    )
    status = SourceStatus.CONFLICTED if blocked else SourceStatus.STALE
    code = "instrument_identity_conflict" if blocked else "kline_source_window_not_covered"
    failed_daily = KlineLayerDiagnostic(
        layer=KlineBusinessLayer.FINAL_DAILY,
        complete=False,
        upstream_ids=("sina",),
        error_code=code,
        error_message="unsafe payload" if blocked else "daily window is stale",
        retry_disposition=retry,
        source_diagnostics=(
            KlineSourceDiagnostic(
                source_id="tencent_kline",
                upstream_id="tencent",
                status=status,
                error_code=code,
                error_message="unsafe payload" if blocked else "daily window is stale",
                fetched_at=AS_OF,
            ),
        ),
    )
    complete = lambda layer, upstreams: KlineLayerDiagnostic(  # noqa: E731
        layer=layer,
        complete=True,
        upstream_ids=upstreams,
    )
    return KlineBusinessFailure(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        error_codes=(code,),
        layer_diagnostics=(
            failed_daily,
            complete(KlineBusinessLayer.FINAL_MINUTE, ("eastmoney", "tencent")),
            complete(KlineBusinessLayer.LIVE_QUOTE, ("eastmoney", "sina")),
            complete(KlineBusinessLayer.PROVISIONAL, ("eastmoney", "sina")),
        ),
    )


def _state() -> DebateState:
    return {
        "session_id": "kr4a",
        "debate_input": {"stock_code": "000001", "stock_name": "平安银行"},
        "current_round": 0,
        "analyses": {},
        "market_data": {},
        "vote_summary": {},
        "review_round": {},
        "review_report": {},
        "errors": [],
        "history_context": "",
        "reflection_context": "",
        "analyst_reports": {},
        "risk_round": {},
        "trader_round": {},
        "trade_recommendation": {},
        "trust_weight_factors": {},
        "calibration_map": {},
        "mirror_report": {},
        "evidence_envelope": {},
        "evidence_limitations": [],
        "evidence_references": [],
        "evidence_failure_kind": "",
    }


def test_complete_result_formats_four_layers_without_mixing_price_coordinates() -> None:
    result = _complete_result()

    assert classify_kline_business_result(result) == "complete"
    context = format_kline_business_context(result)
    reference = kline_evidence_reference(result)

    assert "FINAL_DAILY（QFQ，仅用于历史结构）" in context
    assert "FINAL_MINUTE（RAW，已结束分钟）" in context
    assert "LIVE_QUOTE（RAW，成交/订单价格坐标）" in context
    assert "PROVISIONAL（RAW，未确认收盘）" in context
    assert reference["raw_snapshot_id"] == "raw:000001:2026-08-03"
    assert reference["factor_version"] == "factor-v1"
    assert reference["price_basis"] == "raw"


def test_stale_failure_becomes_structured_limitation() -> None:
    failure = _failure(blocked=False)

    assert classify_kline_business_result(failure) == "limited"
    limitation = kline_failure_limitation(failure)

    assert limitation["capability"] == "kline_business"
    assert limitation["error_codes"] == ["kline_source_window_not_covered"]
    assert limitation["affected_layers"] == ["FINAL_DAILY"]
    assert limitation["missing_upstream_ids"] == ["tencent"]


def test_conflict_or_operator_action_failure_blocks_before_reasoning() -> None:
    failure = _failure(blocked=True)

    assert classify_kline_business_result(failure) == "blocked"


def test_collect_node_uses_only_complete_business_result_for_kline_and_quote() -> None:
    collector = MagicMock()
    collector.get_news.return_value = []
    collector.get_financials.return_value = []
    collector.get_dynamic_indicators.return_value = {}
    collector.get_cached_market_sentiment.return_value = None

    result = collect_data_node(
        _state(),
        collector,
        kline_business_provider=lambda _code: _complete_result(),
    )

    assert _route_after_collection(cast(DebateState, result)) == "continue"
    assert result["market_data"]["kline_business"]["complete"] is True
    assert result["market_data"]["quote"]["price_basis"] == "raw"
    assert result["market_data"]["klines"] == []
    assert result["evidence_references"][0]["factor_version"] == "factor-v1"
    collector.get_klines.assert_not_called()
    collector.get_realtime_quotes.assert_not_called()


def test_collect_node_discloses_stale_failure_without_partial_kline_payload() -> None:
    collector = MagicMock()
    collector.get_realtime_quotes.return_value = []
    collector.get_news.return_value = []
    collector.get_financials.return_value = []
    collector.get_dynamic_indicators.return_value = {}
    collector.get_cached_market_sentiment.return_value = None

    result = collect_data_node(
        _state(),
        collector,
        kline_business_provider=lambda _code: _failure(blocked=False),
    )

    assert _route_after_collection(cast(DebateState, result)) == "continue"
    assert result["market_data"]["kline_business"] is None
    assert result["evidence_limitations"][0]["affected_layers"] == ["FINAL_DAILY"]
    assert "K 线四层证据不可用" in result["market_data"]["brief"]
    collector.get_klines.assert_not_called()


def test_collect_node_blocks_corrupted_failure_and_does_not_collect_fallbacks() -> None:
    collector = MagicMock()

    result = collect_data_node(
        _state(),
        collector,
        kline_business_provider=lambda _code: _failure(blocked=True),
    )

    assert _route_after_collection(cast(DebateState, result)) == "stop"
    assert result["errors"] == ["EVIDENCE_INCOMPLETE"]
    assert result["evidence_envelope"]["complete"] is False
    collector.get_klines.assert_not_called()
    collector.get_realtime_quotes.assert_not_called()


def _collector() -> MagicMock:
    collector = MagicMock()
    collector.get_news.return_value = []
    collector.get_financials.return_value = []
    collector.get_dynamic_indicators.return_value = {}
    collector.get_cached_market_sentiment.return_value = None
    return collector


def _analyst_report() -> AnalystReport:
    return AnalystReport(
        analyst_type="technical",
        key_findings=["分层数据已核验"],
        confidence=0.7,
        summary="仅按冻结上下文分析",
        score=60,
        direction_hint="Neutral",
    )


def _master_analysis() -> AgentAnalysis:
    return AgentAnalysis(
        agent_name="master.buffett",
        skill_id="buffett",
        skill_name="巴菲特",
        rating="中性",
        score=60,
        summary="基于冻结证据",
        analysis="未混用价格坐标",
        confidence=0.6,
    )


@pytest.mark.asyncio
async def test_complete_result_reaches_llm_and_persists_version_reference() -> None:
    memory = MagicMock()
    memory.search = AsyncMock(return_value=[])
    memory.put = AsyncMock()
    orchestrator = DebateOrchestrator(
        data_collector=_collector(),
        memory_store=memory,
        skill_ids=["buffett"],
        news_evidence_service=None,
        quote_evidence_service=None,
        kline_business_provider=lambda _symbol: _complete_result(),
    )

    with patch(
        "src.debate.orchestrator._run_single_analyst",
        new_callable=AsyncMock,
        return_value=_analyst_report(),
    ) as analyst, patch(
        "src.debate.orchestrator._run_single_master",
        new_callable=AsyncMock,
        return_value=_master_analysis(),
    ):
        result = await orchestrator.run(DebateInput(stock_code="000001"))

    assert analyst.await_count > 0
    analyst_call = analyst.await_args
    assert analyst_call is not None
    prompt_data = analyst_call.kwargs["market_data"]["brief"]
    assert "FINAL_DAILY（QFQ，仅用于历史结构）" in prompt_data
    assert "PROVISIONAL（RAW，未确认收盘）" in prompt_data
    assert result.evidence_references[0].raw_snapshot_id == "raw:000001:2026-08-03"
    saved_call = memory.put.await_args
    assert saved_call is not None
    saved = saved_call.kwargs["value"]
    assert saved["evidence_references"][0]["factor_version"] == "factor-v1"


@pytest.mark.asyncio
async def test_retryable_kline_failure_runs_research_but_skips_execution_chain() -> None:
    orchestrator = DebateOrchestrator(
        data_collector=_collector(),
        skill_ids=["buffett"],
        news_evidence_service=None,
        quote_evidence_service=None,
        kline_business_provider=lambda _symbol: _failure(blocked=False),
        enable_risk=True,
        enable_trader=True,
    )

    with patch(
        "src.debate.orchestrator._run_single_analyst",
        new_callable=AsyncMock,
        return_value=_analyst_report(),
    ) as analyst, patch(
        "src.debate.orchestrator._run_single_master",
        new_callable=AsyncMock,
        return_value=_master_analysis(),
    ) as master:
        result = await orchestrator.run(DebateInput(stock_code="000001"))

    assert analyst.await_count > 0
    assert master.await_count > 0
    assert result.evidence_limitations[0].affected_layers == ["FINAL_DAILY"]
    assert result.risk_round is None
    assert result.trader_round is None
    assert result.trade_recommendation is None


@pytest.mark.asyncio
async def test_corrupted_kline_failure_invokes_no_analyst_or_master_llm() -> None:
    orchestrator = DebateOrchestrator(
        data_collector=_collector(),
        skill_ids=["buffett"],
        news_evidence_service=None,
        quote_evidence_service=None,
        kline_business_provider=lambda _symbol: _failure(blocked=True),
    )

    with patch(
        "src.debate.orchestrator._run_single_analyst",
        new_callable=AsyncMock,
    ) as analyst, patch(
        "src.debate.orchestrator._run_single_master",
        new_callable=AsyncMock,
    ) as master, pytest.raises(EvidenceIncompleteError) as raised:
        await orchestrator.run(DebateInput(stock_code="000001"))

    analyst.assert_not_awaited()
    master.assert_not_awaited()
    assert raised.value.detail()["error_codes"] == ["instrument_identity_conflict"]

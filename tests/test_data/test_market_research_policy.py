"""Single-source research must be real availability, not a presentation-only bypass."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.technical_research import build_technical_research
from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceResult,
    SourceStatus,
)
from src.data.kline_calendar import official_a_share_calendar_2026
from src.data.kline_runtime import KLINE_RAW_EVIDENCE_POLICY, RawDailyKlineEvidenceService
from src.data.quote_runtime import REALTIME_QUOTE_EVIDENCE_POLICY, RealtimeQuoteEvidenceService
from src.data.research_policy import (
    MARKET_RESEARCH_PROMPT,
    RESEARCH_KLINE_POLICY,
    RESEARCH_QUOTE_POLICY,
)
from src.debate.orchestrator import collect_data_node
from src.debate.research_scope import scope_prompt
from tests.test_data.test_kline_evidence import StubKlineSource, _bar
from tests.test_data.test_kline_evidence import _result as daily_result
from tests.test_data.test_quote_evidence import NOW, REQUEST, StubQuoteSource, _quote, _result


def quote_service(usable: str, *, conflict: bool = False) -> RealtimeQuoteEvidenceService:
    registry = EvidenceSourceRegistry()
    for source in ("sina", "eastmoney", "tencent"):
        good = source == usable or (conflict and source == "eastmoney")
        result = _result(
            source,
            source,
            quote=_quote(price=12 if conflict and source == "eastmoney" else 11.28),
            status=SourceStatus.SUCCESS_DATA if good else SourceStatus.FAILED,
            error_message=None if good else "timeout",
        )
        registry.register(StubQuoteSource(source, source, result))
    return RealtimeQuoteEvidenceService(registry, now_provider=lambda: NOW)


@pytest.mark.parametrize("source", ["sina", "eastmoney", "tencent"])
def test_any_valid_source_reaches_actual_debate_without_source_count_limitation(
    source, monkeypatch
):
    monkeypatch.setattr("src.debate.archive_research.research_context", lambda *_: ("", []))
    service = quote_service(source)
    evidence = service.collect(REQUEST, RESEARCH_QUOTE_POLICY)
    assert evidence.complete and evidence.items[0].price == 11.28
    assert evidence.assessment.successful_upstream_ids == {source}
    collector = MagicMock()
    collector.get_klines.return_value = []
    collector.get_news.return_value = []
    collector.get_financials.return_value = []
    collector.get_dynamic_indicators.return_value = None
    collector.get_cached_market_sentiment.return_value = None
    result = collect_data_node(
        {"debate_input": {"stock_code": "000001", "stock_name": "平安银行"}},
        collector,
        quote_evidence_service=service,
    )
    assert result["market_data"]["quote"]["price"] == 11.28
    assert not result.get("evidence_limitations")
    assert not result.get("errors")


def test_all_failed_or_real_price_conflict_remain_unavailable():
    assert not quote_service("none").collect(REQUEST, RESEARCH_QUOTE_POLICY).complete
    conflicted = quote_service("sina", conflict=True).collect(REQUEST, RESEARCH_QUOTE_POLICY)
    assert not conflicted.complete and not conflicted.items
    assert any(r.error_code == "quote_price_conflict" for r in conflicted.source_results)


@pytest.mark.parametrize(
    "change",
    [
        {"price": 0},
        {"price": float("nan")},
        {"code": "002885"},
        {"fetched_at": NOW + timedelta(minutes=1)},
        {"fetched_at": None},
        {"fetched_at": NOW - timedelta(minutes=10)},
    ],
)
def test_single_source_does_not_bypass_identity_price_or_time(change):
    registry = EvidenceSourceRegistry()
    registry.register(
        StubQuoteSource(
            "sina", "sina", _result("sina", "sina", quote=_quote().model_copy(update=change))
        )
    )
    result = RealtimeQuoteEvidenceService(registry, now_provider=lambda: NOW).collect(
        REQUEST, RESEARCH_QUOTE_POLICY
    )
    assert not result.complete and not result.items


def test_empty_quote_is_not_a_successful_market_source():
    registry = EvidenceSourceRegistry()
    registry.register(
        StubQuoteSource("sina", "sina", _result("sina", "sina", status=SourceStatus.SUCCESS_EMPTY))
    )
    assert (
        not RealtimeQuoteEvidenceService(registry, now_provider=lambda: NOW)
        .collect(REQUEST, RESEARCH_QUOTE_POLICY)
        .complete
    )


def daily_envelope(*, omit: bool = False):
    start, end = date(2026, 3, 2), date(2026, 7, 28)
    dates = official_a_share_calendar_2026().open_dates("SZSE", start, end)
    bars = [_bar(day) for day in dates]
    registry = EvidenceSourceRegistry()
    for source in ("sina", "tencent"):
        result = (
            daily_result(source, source, bars[1:] if omit else bars)
            if source == "tencent"
            else SourceResult(
                source_id=source,
                upstream_id=source,
                capability=EvidenceCapability.KLINE,
                status=SourceStatus.FAILED,
                items=[],
                error_message="timeout",
            )
        )
        registry.register(StubKlineSource(source, source, result))
    request = EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code="000001",
        start_at=NOW.replace(month=3, day=2),
        end_at=NOW.replace(day=28),
    )
    return RawDailyKlineEvidenceService(
        registry, calendar=official_a_share_calendar_2026(), now_provider=lambda: NOW
    ).collect(request, RESEARCH_KLINE_POLICY)


def test_one_valid_daily_source_calculates_ma60_and_keeps_provenance():
    evidence = daily_envelope()
    result = build_technical_research("000001", evidence)
    assert evidence.complete and result.status == "available"
    assert result.sources == ["tencent"] and result.indicators[-1].ma["ma60"] is not None
    assert len(result.bars) > 60


def test_single_daily_source_still_checks_missing_trading_dates():
    evidence = daily_envelope(omit=True)
    assert not evidence.complete
    assert any(r.error_code == "expected_trading_date_missing" for r in evidence.source_results)


def test_scope_and_execution_policy_are_separate():
    assert MARKET_RESEARCH_PROMPT in scope_prompt(NOW.date())
    assert "降低评分/置信度" in MARKET_RESEARCH_PROMPT
    assert REALTIME_QUOTE_EVIDENCE_POLICY.min_independent_upstreams == 2
    assert KLINE_RAW_EVIDENCE_POLICY.min_independent_upstreams == 2


def test_research_keeps_newest_valid_quote_when_vendor_update_times_differ():
    registry = EvidenceSourceRegistry()
    for source, lag, price in [("sina", 0, 11.28), ("eastmoney", 8, 11.25)]:
        registry.register(
            StubQuoteSource(
                source,
                source,
                _result(
                    source,
                    source,
                    quote=_quote(price=price).model_copy(
                        update={"fetched_at": NOW - timedelta(seconds=lag)}
                    ),
                ),
            )
        )
    service = RealtimeQuoteEvidenceService(registry, now_provider=lambda: NOW)
    result = service.collect(REQUEST, RESEARCH_QUOTE_POLICY)
    assert result.complete and result.items[0].price == 11.28
    assert result.assessment.successful_upstream_ids == {"sina"}
    assert any(r.error_code == "quote_timestamp_unaligned" for r in result.source_results)
    assert not service.collect(REQUEST, REALTIME_QUOTE_EVIDENCE_POLICY).complete


@pytest.mark.parametrize("stage", ["analyst", "peer", "independent"])
async def test_all_model_stages_receive_single_source_policy(stage, monkeypatch):
    from src.debate import orchestrator
    from src.debate.models import AgentAnalysis

    call = AsyncMock(side_effect=RuntimeError("offline prompt capture"))
    monkeypatch.setattr(orchestrator.llm_service, "invoke_structured", call)
    identity = MagicMock(
        analyst_type="fundamental", skill_id="buffett", name="巴菲特", system_prompt="Persona"
    )
    opinion = AgentAnalysis(
        agent_name="master.buffett",
        skill_id="buffett",
        skill_name="巴菲特",
        rating="看跌",
        score=30,
        summary="已有观点",
        analysis="旧单源限制",
        confidence=0.5,
    )
    if stage == "analyst":
        await orchestrator._run_single_analyst(
            identity, "offline", "研究", "000001", "平安银行", {}
        )
    elif stage == "peer":
        await orchestrator._run_review_for_master(identity, "offline", "研究", opinion, [], {})
    else:
        await orchestrator._run_independent_review("offline", "研究", [opinion], [], {})
    call.assert_awaited_once()
    assert MARKET_RESEARCH_PROMPT in call.await_args.kwargs["system_prompt"]

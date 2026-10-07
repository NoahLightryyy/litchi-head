"""Research reuse must not weaken live evidence or transaction gates."""

from datetime import datetime

import pytest

from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    SourceResult,
    SourceStatus,
)
from src.data.models import NewsItem, StockQuote
from src.debate.orchestrator import _route_after_reasoning
from src.debate.research_evidence import closing_research_quotes, partial_research_news


def envelope(capability, results):
    return EvidenceEnvelope(
        request=EvidenceRequest(
            capability=capability,
            stock_code="920344",
            stock_name="三元基因",
            start_at=datetime.fromisoformat("2026-10-03T16:00:00+08:00"),
            end_at=datetime.fromisoformat("2026-10-06T16:00:00+08:00"),
        ),
        policy=EvidencePolicy(capability=capability, min_independent_upstreams=2),
        source_results=results,
        assessment=EvidenceAssessment(
            capability=capability, complete=False, missing_independent_upstreams=1
        ),
        complete=False,
    )


def quote_result(stamp="2026-09-30T15:30:00+08:00", price=24.35, source="sina"):
    return SourceResult(
        source_id=source,
        upstream_id=source,
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=SourceStatus.STALE,
        error_code="market_not_in_continuous_auction",
        items=[
            StockQuote(
                code="920344",
                name="三元基因",
                price=price,
                change=3.32,
                change_pct=15.79,
                volume=100,
                fetched_at=datetime.fromisoformat(stamp),
            )
        ],
    )


def test_holiday_last_close_is_research_only():
    env = envelope(EvidenceCapability.REALTIME_QUOTE, [quote_result()])
    result = closing_research_quotes(env, datetime.fromisoformat("2026-10-06T16:00:00+08:00"))
    assert result.quotes[0].price == 24.35
    assert "单源" in result.note and "2026-09-30" in result.note
    assert not env.complete and not env.items
    assert (
        _route_after_reasoning({"evidence_limitations": [{"capability": "realtime_quote"}]})
        == "stop"
    )


@pytest.mark.parametrize(
    "stamp,now",
    [
        ("2026-09-29T15:30:00+08:00", "2026-10-06T16:00:00+08:00"),
        ("2026-09-30T14:30:00+08:00", "2026-10-06T16:00:00+08:00"),
        ("2026-09-30T15:30:00+08:00", "2026-09-30T15:00:00+08:00"),
        ("2026-09-30T15:30:00+08:00", "2026-10-08T09:30:00+08:00"),
        ("2026-09-30T15:30:00+08:00", "2026-10-08T12:00:00+08:00"),
        ("2026-09-30T15:30:00+08:00", "2026-10-08T15:30:00+08:00"),
        ("2026-09-30T15:30:00+08:00", "2027-01-02T15:30:00+08:00"),
    ],
)
def test_invalid_session_cannot_be_reused(stamp, now):
    result = closing_research_quotes(
        envelope(EvidenceCapability.REALTIME_QUOTE, [quote_result(stamp)]),
        datetime.fromisoformat(now),
    )
    assert not result.quotes


def test_closing_sources_ignore_skew_but_reject_price_conflict():
    results = [quote_result(), quote_result("2026-09-30T16:12:00+08:00", source="eastmoney")]
    env = envelope(EvidenceCapability.REALTIME_QUOTE, results)
    now = datetime.fromisoformat("2026-10-06T16:00:00+08:00")
    assert "2 源价格一致" in closing_research_quotes(env, now).note
    env.source_results[1].items[0].price += 1
    rejected = closing_research_quotes(env, now)
    assert not rejected.quotes and "冲突" in rejected.note


def test_partial_news_keeps_window_and_identity():
    start = datetime.fromisoformat("2026-10-05T12:00:00+08:00")
    end = datetime.fromisoformat("2026-10-06T15:00:00+08:00")
    items = [
        NewsItem(code="920344", title="三元基因公告", date="2026-10-05", published_at=start),
        NewsItem(code="000001", title="别的股票", date="2026-10-05", published_at=start),
    ]
    source = SourceResult(
        source_id="sina",
        upstream_id="sina",
        capability=EvidenceCapability.NEWS,
        status=SourceStatus.STALE,
        error_code="rolling_window_not_fully_covered",
        coverage_start_at=start,
        coverage_end_at=end,
        items=items,
    )
    result = partial_research_news(envelope(EvidenceCapability.NEWS, [source]))
    assert len(result.items) == 1
    assert "匹配 1 条" in result.note and "未覆盖完整近 3 天" in result.note


def test_collection_brief_uses_closing_quote_and_preserves_transaction_stop():
    from unittest.mock import MagicMock, patch

    from src.debate.orchestrator import collect_data_node

    env = envelope(EvidenceCapability.REALTIME_QUOTE, [quote_result()])
    service = MagicMock()
    service.collect.return_value = env
    collector = MagicMock()
    for method in ("get_klines", "get_financials"):
        getattr(collector, method).return_value = []
    collector.get_dynamic_indicators.return_value = {}
    collector.get_cached_market_sentiment.return_value = None
    collector.get_news.return_value = []
    real_selection = closing_research_quotes(
        env, datetime.fromisoformat("2026-10-06T16:00:00+08:00")
    )
    with patch("src.debate.orchestrator.closing_research_quotes", return_value=real_selection):
        result = collect_data_node(
            {"debate_input": {"stock_code": "920344", "stock_name": "三元基因"}},
            collector,
            quote_evidence_service=service,
        )
    assert result["market_data"]["quote"]["price"] == 24.35
    assert "休市研究" in result["market_data"]["brief"]
    assert "成交量 100 股" in result["market_data"]["brief"]
    assert "单源" in result["evidence_limitations"][0]["research_note"]
    assert _route_after_reasoning(result) == "stop"
    collector.get_realtime_quotes.assert_not_called()


def test_channel_samples_reach_actual_debate_brief_with_all_citations():
    from unittest.mock import MagicMock

    from src.debate.orchestrator import collect_data_node

    stamp = datetime.fromisoformat("2026-10-05T12:00:00+08:00")
    sources = [SourceResult(
        source_id=f"{channel}-latest-sample", upstream_id=channel,
        capability=EvidenceCapability.NEWS, status=SourceStatus.STALE,
        error_code="latest_sample_only", coverage_start_at=stamp, coverage_end_at=stamp,
        items=[NewsItem(code="920344", title="三元基因研发进展", date="2026-10-05",
                        published_at=stamp, source=channel, source_id=f"{channel}-latest-sample",
                        url=f"https://example.com/{channel}")],
    ) for channel in ("cls", "ths", "futu")]
    service = MagicMock()
    service.collect.return_value = envelope(EvidenceCapability.NEWS, sources)
    collector = MagicMock()
    for method in ("get_klines", "get_financials", "get_realtime_quotes"):
        getattr(collector, method).return_value = []
    collector.get_dynamic_indicators.return_value = {}
    collector.get_cached_market_sentiment.return_value = None
    result = collect_data_node(
        {"debate_input": {"stock_code": "920344", "stock_name": "三元基因"}}, collector,
        news_evidence_service=service,
    )
    brief = result["market_data"]["brief"]
    assert len(result["market_data"]["news"]) == 3
    assert all(f"https://example.com/{channel}" in brief for channel in ("cls", "ths", "futu"))
    assert "合并为 1 组" in brief
    assert _route_after_reasoning(result) == "stop"
    collector.get_news.assert_not_called()

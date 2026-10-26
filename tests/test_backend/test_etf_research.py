"""ETF debate material is bounded, identity-scoped and independent of corporate data."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend import etf_research
from backend.etf_contract import EtfCatalog, EtfDetail, EtfIdentity, EtfKlineDisplay, EtfQuote
from backend.related_research_contract import RelatedResearchResult

NOW = datetime(2026, 10, 26, 18, tzinfo=UTC)
IDENTITY = EtfIdentity(code="560780", symbol="sh560780", exchange="SH", name="半导体设备ETF广发")
CATALOG = EtfCatalog(items=(IDENTITY,), fetched_at=NOW)


def quote():
    return EtfDetail(
        identity=IDENTITY,
        quote=EtfQuote(price=0.749, previous_close=0.781, change=-0.032, change_pct=-4.097,
                       open=0.781, high=0.790, low=0.747, quoted_at=NOW,
                       source_name=IDENTITY.name),
        status="ready", source_url="https://finance.sina.com.cn/",
        catalog_fetched_at=NOW, fetched_at=NOW, limitations=["新浪单源场内报价"],
    )


def daily():
    return EtfKlineDisplay(
        identity=IDENTITY, status="ready", source="tencent", fetched_at=NOW,
        requested_start="2026-07-26", requested_end="2026-10-26",
        data_start="2026-10-26", data_end="2026-10-26",
        bars=[dict(date="2026-10-26", open=0.781, close=0.749, high=0.790, low=0.747,
                   volume=516826000)],
        diagnostics=[dict(source="tencent", status="success")], limitations=["未复权"],
    )


def related():
    return RelatedResearchResult(
        subject_kind="etf", subject_id=IDENTITY.code, subject_name=IDENTITY.name, query="",
        status="ready", keywords=[dict(term="半导体", origin="expanded")],
        data=[dict(id="news:test", title="半导体产业政策报道", url="https://example.com/policy",
                   publisher="新闻来源", published_at="2026-10-20", excerpt="支持产业研究",
                   source="news_archive", category="policy", relevance="topic",
                   matched_keywords=["半导体"], reason="主题相关：半导体")],
        sources=[dict(source="company_profile", status="not_requested"),
                 dict(source="news_archive", status="ok")],
        searched_at=NOW, limitations=["关键词关联不是核验结论"],
    )


@pytest.fixture
def sources(monkeypatch):
    mocks = {
        "detail": AsyncMock(return_value=quote()),
        "get_etf_kline": AsyncMock(return_value=daily()),
        "related_research": AsyncMock(return_value=related()),
    }
    for key, value in mocks.items():
        monkeypatch.setattr(etf_research, key, value)
    return mocks


async def test_context_preserves_fund_prices_units_dates_and_source_links(sources):
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert result.instrument_type == "etf" and result.stock_code == "560780"
    assert result.stock_name == IDENTITY.name
    assert "0.749" in result.brief and '"volume":516826000' in result.brief
    assert "fund_units" in result.brief and "2026-10-20" in result.brief
    assert "https://example.com/policy" in result.brief
    assert "data_end" in result.brief and "fetched_at仅为采集时间" in result.brief
    assert "本模块未计算MA/RSI/MACD" in result.brief
    assert result.evidence_limitations[0].capability == "etf_research_scope"
    assert "净值" in result.evidence_limitations[0].research_note
    sources["detail"].assert_awaited_once_with(IDENTITY, CATALOG)
    sources["get_etf_kline"].assert_awaited_once_with(IDENTITY, days=90)
    # ETF related research bypasses company-profile fetching by construction.
    sources["related_research"].assert_awaited_once_with("etf", "560780", IDENTITY.name, "")


async def test_sources_start_concurrently(monkeypatch):
    started = []
    together = asyncio.Event()

    def operation(label, value):
        async def call(*args, **kwargs):
            started.append(label)
            if len(started) == 3:
                together.set()
            await asyncio.wait_for(together.wait(), timeout=0.5)
            return value
        return call

    monkeypatch.setattr(etf_research, "detail", operation("quote", quote()))
    monkeypatch.setattr(etf_research, "get_etf_kline", operation("daily", daily()))
    monkeypatch.setattr(etf_research, "related_research", operation("related", related()))
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert set(started) == {"quote", "daily", "related"}
    assert len(result.evidence_limitations) == 1


async def test_failed_daily_keeps_quote_and_related_material(sources):
    sources["get_etf_kline"].side_effect = OSError("upstream private detail")
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert "0.749" in result.brief and "https://example.com/policy" in result.brief
    assert "历史日线未取得" in result.brief
    assert "upstream private detail" not in result.brief
    assert {item.capability for item in result.evidence_limitations} == {
        "etf_research_scope", "etf_daily",
    }


async def test_timeout_is_bounded_and_preserves_other_sources(sources, monkeypatch):
    async def slow(*args, **kwargs):
        await asyncio.sleep(60)

    sources["detail"].side_effect = slow
    monkeypatch.setattr(etf_research, "SOURCE_TIMEOUT_SECONDS", 0.01)
    result = await asyncio.wait_for(etf_research.collect_etf_research(IDENTITY, CATALOG), 0.5)
    assert "报价未取得" in result.brief
    assert "https://example.com/policy" in result.brief and "516826000" in result.brief


async def test_foreign_material_is_discarded_instead_of_attached_to_etf(sources):
    other = EtfIdentity(code="510300", symbol="sh510300", exchange="SH", name="其他ETF")
    sources["detail"].return_value = quote().model_copy(update={"identity": other})
    sources["get_etf_kline"].return_value = daily().model_copy(update={"identity": other})
    sources["related_research"].return_value = related().model_copy(
        update={"subject_kind": "stock"},
    )
    with pytest.raises(etf_research.NoUsableEtfResearchError):
        await etf_research.collect_etf_research(IDENTITY, CATALOG)


async def test_missing_catalog_identity_stops_before_source_calls(sources):
    with pytest.raises(ValueError, match="absent"):
        await etf_research.collect_etf_research(
            IDENTITY, EtfCatalog(items=(), fetched_at=NOW),
        )
    for mock in sources.values():
        mock.assert_not_called()


async def test_all_empty_results_stop_before_an_identity_only_paid_debate(sources):
    sources["detail"].return_value = quote().model_copy(update={"quote": None, "status": "partial"})
    sources["get_etf_kline"].return_value = daily().model_copy(update={
        "status": "empty", "source": None, "bars": [], "data_start": None, "data_end": None,
    })
    sources["related_research"].return_value = related().model_copy(
        update={"status": "empty", "data": []},
    )
    with pytest.raises(etf_research.NoUsableEtfResearchError):
        await etf_research.collect_etf_research(IDENTITY, CATALOG)


async def test_all_source_failures_stop_before_an_identity_only_paid_debate(sources):
    for mock in sources.values():
        mock.side_effect = TimeoutError
    with pytest.raises(etf_research.NoUsableEtfResearchError):
        await etf_research.collect_etf_research(IDENTITY, CATALOG)


@pytest.mark.parametrize("usable_source", ["detail", "get_etf_kline", "related_research"])
async def test_one_usable_material_class_is_enough(sources, usable_source):
    for name, mock in sources.items():
        if name != usable_source:
            mock.side_effect = TimeoutError
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert result.stock_code == IDENTITY.code
    assert len(result.evidence_limitations) == 3


async def test_unavailable_source_keeps_failure_classification(sources):
    sources["get_etf_kline"].return_value = daily().model_copy(update={
        "status": "unavailable", "source": None, "bars": [], "data_start": None, "data_end": None,
    })
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    limitation = next(
        item for item in result.evidence_limitations if item.capability == "etf_daily"
    )
    assert limitation.source_statuses == {"历史日线": "unavailable"}

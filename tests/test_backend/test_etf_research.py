"""ETF debate material is bounded, identity-scoped and independent of corporate data."""

import asyncio
from datetime import UTC, datetime
from threading import get_ident
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend import etf_research
from backend.etf_contract import EtfCatalog, EtfDetail, EtfIdentity, EtfKlineDisplay, EtfQuote
from backend.related_research_contract import RelatedResearchResult

NOW = datetime(2026, 10, 26, 18, tzinfo=UTC)
IDENTITY = EtfIdentity(code="560780", symbol="sh560780", exchange="SH", name="半导体设备ETF广发")
CATALOG = EtfCatalog(items=(IDENTITY,), fetched_at=NOW)


@pytest.fixture(autouse=True)
def saved_interpretation(monkeypatch):
    read = Mock(return_value="")
    monkeypatch.setattr(etf_research, "format_saved_interpretation", read)
    return read


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


def daily_observations(observations):
    payload = daily().model_dump()
    payload.update(
        data_start=observations[0][0], data_end=observations[-1][0],
        bars=[dict(date=date, open=close, high=close, low=close, close=close, volume=volume)
              for date, close, volume in observations],
    )
    return EtfKlineDisplay.model_validate(payload)


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


def test_daily_facts_use_decimal_price_changes_and_same_date_volume_basis():
    series = daily_observations([
        ("2026-10-22", 0.784, 600000000),
        ("2026-10-23", 0.792, 847322400),
        ("2026-10-26", 0.749, 516826000),
    ])
    facts = etf_research.etf_daily_facts(series)
    first, rebound, latest = facts["recent"]
    assert first["change_cny"] is None and first["change_pct"] is None
    assert first["volume_ratio"] is None and first["close_direction"] is None
    assert rebound["close_direction"] == "up" and rebound["change_pct"] == "1.02"
    assert latest["close_direction"] == "down" and latest["previous_available_date"] == "2026-10-23"
    assert latest["change_cny"] == "-0.043" and latest["change_pct"] == "-5.43"
    assert latest["volume_ratio"] == "0.61" and latest["volume_fund_units"] == 516826000
    assert facts["sample_count"] == 3 and facts["sample_min_close_cny"] == "0.749"
    assert facts["sample_start"] == "2026-10-22" and facts["sample_end"] == "2026-10-26"
    assert facts["sample_min_close_dates"] == ["2026-10-26"]
    assert "不是上市以来最低" in facts["comparison_basis"]


def test_daily_facts_zero_volume_is_not_an_invented_ratio():
    series = daily_observations([
        ("2026-10-22", 0.784, 0),
        ("2026-10-23", 0.784, 100),
    ])
    latest = etf_research.etf_daily_facts(series)["recent"][-1]
    assert latest["volume_ratio"] is None and latest["previous_volume_fund_units"] == 0
    assert latest["change_cny"] == "0.000" and latest["close_direction"] == "flat"


def test_daily_facts_cover_full_sample_but_only_return_five_recent_rows():
    series = daily_observations([
        ("2026-10-08", 1.000, 100),
        ("2026-10-09", 0.500, 100),
        ("2026-10-12", 0.510, 100),
        ("2026-10-13", 0.520, 100),
        ("2026-10-14", 0.530, 100),
        ("2026-10-15", 0.540, 100),
        ("2026-10-16", 0.550, 100),
    ])
    facts = etf_research.etf_daily_facts(series)
    assert facts["sample_count"] == 7 and len(facts["recent"]) == 5
    assert facts["recent"][0]["previous_available_date"] == "2026-10-09"
    assert facts["largest_abs_observation_change"] == {
        "date": "2026-10-09", "previous_available_date": "2026-10-08",
        "previous_close_cny": "1.000", "close_cny": "0.500", "change_pct": "-50.00",
    }
    assert "不能反推已经发生分红或份额折算" in facts["comparison_basis"]


def test_daily_facts_missing_history_keeps_null_and_empty_is_not_summarized():
    facts = etf_research.etf_daily_facts(daily())
    assert facts["largest_abs_observation_change"] is None
    assert facts["recent"][0]["previous_close_cny"] is None
    assert etf_research.etf_daily_facts(daily().model_copy(update={"bars": []})) is None


async def test_prepared_brief_includes_facts_only_when_history_exists(sources):
    result = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert "【确定性日线比较摘要】" in result.brief
    assert '"sample_count":1' in result.brief
    sources["get_etf_kline"].return_value = daily().model_copy(update={
        "status": "empty", "source": None, "bars": [], "data_start": None, "data_end": None,
    })
    empty = await etf_research.collect_etf_research(IDENTITY, CATALOG)
    assert "【确定性日线比较摘要】" not in empty.brief


@pytest.mark.parametrize("saved_state", ["present", "missing", "failed"])
async def test_saved_interpretation_stays_separate_from_etf_raw_material(
    sources, saved_interpretation, saved_state, caplog
):
    event_thread = get_ident()
    read_threads = []
    saved_text = (
        "【已保存AI解读，非原始事实】版本test-etf-1，生成于2026-10-26；"
        "来源https://example.com/policy，报道日期2026-10-20。"
    )

    def read(*args):
        read_threads.append(get_ident())
        if saved_state == "failed":
            raise ValueError("private corrupt record")
        return saved_text if saved_state == "present" else ""

    saved_interpretation.side_effect = read
    with patch("src.utils.llm.llm_service.invoke_structured", new_callable=AsyncMock) as generate:
        result = await etf_research.collect_etf_research(IDENTITY, CATALOG)

    saved_interpretation.assert_called_once_with("etf", "560780", "")
    assert len(read_threads) == 1 and read_threads[0] != event_thread
    generate.assert_not_called()
    assert "0.749" in result.brief and "https://example.com/policy" in result.brief
    assert "【确定性日线比较摘要】" in result.brief
    assert [item.capability for item in result.evidence_limitations] == ["etf_research_scope"]
    assert (saved_text in result.brief) == (saved_state == "present")
    assert ("已保存的政策与新闻解读】读取失败" in result.brief) == (saved_state == "failed")
    assert "private corrupt record" not in result.brief
    if saved_state == "failed":
        assert "Saved related interpretation read failed: kind=etf code=560780" in caplog.text


async def test_saved_ai_interpretation_does_not_replace_missing_original_etf_material(
    sources, saved_interpretation,
):
    saved_interpretation.return_value = "【已保存AI解读】半导体政策可能影响市场预期"
    for source in sources.values():
        source.side_effect = TimeoutError
    with pytest.raises(etf_research.NoUsableEtfResearchError):
        await etf_research.collect_etf_research(IDENTITY, CATALOG)
    saved_interpretation.assert_not_called()

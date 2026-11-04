"""Adjustment basis and volume facts must not become invented buy confirmations."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.technical_supplement import build_adjusted_evidence, build_volume_evidence
from src.data.kline import RawDailyBar
from src.data.providers.tencent_qfq import ProviderQfqBar, parse_qfq_daily


def bars(count=61):
    return [
        RawDailyBar(
            code="002885",
            market="SZSE",
            trade_date=date(2026, 6, 1) + timedelta(days=i),
            open=20,
            high=21,
            low=19,
            close=20,
            volume=1000,
        )
        for i in range(count)
    ]


def payload(items):
    return {"code": 0, "data": {"sz002885": {"qfqday": items}}}


def rows(data):
    return [[str(b.trade_date), "19.125", "19.625", "20.125", "18.125", "10"] for b in data]


def parse(value):
    return parse_qfq_daily(
        value, "002885", date(2026, 6, 1), date(2026, 8, 30), datetime(2026, 8, 31, tzinfo=UTC)
    )


def test_adjusted_prices_not_rounded_to_raw_tick_or_labelled_official():
    raw = bars()
    adjusted = parse(payload(rows(raw)))
    assert adjusted[0].close == Decimal("19.625")
    result = build_adjusted_evidence(raw, adjusted, datetime(2026, 8, 31, tzinfo=UTC), "a" * 64)
    assert result.status == "available" and result.price_basis == "provider_qfq_current"
    assert result.indicators[-1].ma["ma60"] == pytest.approx(19.625)
    assert result.bar_count == 61 and result.data_end == raw[-1].trade_date
    assert raw[-1].close == 20 and raw[-1].volume == 1000


@pytest.mark.parametrize(
    "mutation", ["foreign", "raw", "nan", "negative", "ohlc", "duplicate", "unordered", "future"]
)
def test_bad_qfq_payloads_rejected(mutation):
    data = rows(bars(3))
    value = payload(data)
    if mutation == "foreign":
        value["data"]["sz000001"] = value["data"].pop("sz002885")
    if mutation == "raw":
        value["data"]["sz002885"]["day"] = value["data"]["sz002885"].pop("qfqday")
    if mutation == "nan":
        data[0][2] = "NaN"
    if mutation == "negative":
        data[0][2] = "-1"
    if mutation == "ohlc":
        data[0][2] = "999"
    if mutation == "duplicate":
        data.append(data[-1])
    if mutation == "unordered":
        data.reverse()
    if mutation == "future":
        data[-1][0] = "2027-01-01"
    with pytest.raises(ValueError):
        parse(value)


def test_mismatched_qfq_coverage_and_identity_never_mixes_bases():
    raw = bars()
    adjusted = parse(payload(rows(raw)))
    with pytest.raises(ValueError):
        build_adjusted_evidence(raw, adjusted[:-1], datetime.now(UTC), "a" * 64)
    with pytest.raises(ValueError):
        build_adjusted_evidence(
            raw,
            [b.model_copy(update={"code": "000001"}) for b in adjusted],
            datetime.now(UTC),
            "a" * 64,
        )


def test_volume_averages_exclude_today_and_use_raw_shares():
    raw = bars(21)
    raw[-1] = raw[-1].model_copy(update={"volume": 2000})
    result = build_volume_evidence(raw)
    assert result.status == "available"
    assert result.latest_shares == 2000 and result.previous5_mean_shares == 1000
    assert result.previous20_mean_shares == 1000
    assert result.ratio_to_previous5 == 2 and result.ratio_to_previous20 == 2
    assert result.comparison == "above_both"
    raw[-1] = raw[-1].model_copy(update={"volume": 500})
    assert build_volume_evidence(raw).comparison == "below_both"


def test_short_zero_and_mixed_windows_are_not_faked_as_confirmation():
    assert build_volume_evidence([]).status == "unavailable"
    assert build_volume_evidence(bars(5)).ratio_to_previous5 is None
    assert build_volume_evidence(bars(6)).ratio_to_previous5 == 1
    assert build_volume_evidence(bars(6)).comparison == "insufficient"
    zero = [b.model_copy(update={"volume": 0}) for b in bars(21)]
    result = build_volume_evidence(zero)
    assert result.ratio_to_previous20 is None and result.comparison == "insufficient"
    mixed = bars(21)
    mixed[-6:-1] = [b.model_copy(update={"volume": 2000}) for b in mixed[-6:-1]]
    mixed[-1] = mixed[-1].model_copy(update={"volume": 1500})
    assert build_volume_evidence(mixed).comparison == "mixed"


def test_partial_adjustment_failure_preserves_volume(monkeypatch):
    from types import SimpleNamespace

    import backend.technical_research as module
    from tests.test_backend.test_technical_research import envelope

    monkeypatch.setattr(
        module,
        "get_raw_daily_kline_runtime",
        lambda: SimpleNamespace(
            service=SimpleNamespace(collect=lambda *args: envelope(code="002885"))
        ),
    )

    def fail(*args):
        raise ValueError("upstream missing qfqday")

    monkeypatch.setattr(module, "fetch_qfq_daily", fail)
    result = module._collect_technical_research("002885")
    assert result.status == "available" and result.volume.status == "available"
    assert result.adjusted.status == "unavailable"
    assert "未复权" in result.limitations[0]


def test_qfq_success_and_prompt_basis_are_explicit(monkeypatch):
    from types import SimpleNamespace

    import backend.technical_research as module
    from tests.test_backend.test_technical_research import envelope

    source = envelope(code="002885")
    monkeypatch.setattr(
        module,
        "get_raw_daily_kline_runtime",
        lambda: SimpleNamespace(service=SimpleNamespace(collect=lambda *args: source)),
    )
    from src.data.providers.tencent_qfq import ProviderQfqBar

    adjusted = [
        ProviderQfqBar(code=b.code, trade_date=b.trade_date, open=9, high=9, low=9, close=9)
        for b in source.items
    ]
    monkeypatch.setattr(
        module, "fetch_qfq_daily", lambda *args: (adjusted, datetime.now(UTC), "a" * 64)
    )
    result = module._collect_technical_research("002885")
    assert result.adjusted.status == "available"
    assert result.indicators[-1].ma["ma60"] == 10
    assert result.adjusted.indicators[-1].ma["ma60"] == 9
    assert "已补充" in result.limitations[0]


def test_single_flight_cache_returns_copies_and_expires(monkeypatch):
    import backend.technical_research as module
    from tests.test_backend.test_technical_research import envelope

    calls = []
    clock = [1000.0]
    module._cache_entry.cache_clear()
    result = module.build_technical_research("002885", envelope(code="002885"))

    def collect(code):
        calls.append(code)
        return result

    monkeypatch.setattr(module, "_collect_technical_research", collect)
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    first = module.get_technical_research("002885")
    first.bars.clear()
    assert module.get_technical_research("002885").bars and len(calls) == 1
    clock[0] += 31
    module.get_technical_research("002885")
    assert len(calls) == 2
    module._cache_entry.cache_clear()


def test_read_only_route_contract(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routers import stocks
    from backend.technical_research import build_technical_research
    from tests.test_backend.test_technical_research import envelope

    monkeypatch.setattr(
        stocks,
        "get_technical_research",
        lambda code: build_technical_research(code, envelope(code=code)),
    )
    app = FastAPI()
    app.include_router(stocks.router)
    with TestClient(app) as client:
        data = client.get("/api/stocks/002885/technical-research").json()
        assert data["stock_code"] == "002885" and data["volume"]["volume_basis"] == "raw_shares"
        assert data["adjusted"]["price_basis"] == "provider_qfq_current"
        assert client.get("/api/stocks/not-a-code/technical-research").status_code == 422


@pytest.mark.asyncio
async def test_future_debate_receives_adjusted_and_volume_facts_without_llm(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from backend import debate_research as module
    from backend.technical_research import build_technical_research
    from tests.test_backend.test_technical_research import envelope

    result = build_technical_research("002885", envelope(code="002885"))
    result.adjusted = build_adjusted_evidence(
        result.bars,
        [
            ProviderQfqBar(code=b.code, trade_date=b.trade_date, open=9, high=9, low=9, close=9)
            for b in result.bars
        ],
        datetime.now(UTC),
        "a" * 64,
    )
    monkeypatch.setattr(module, "fetch_evidence", AsyncMock(side_effect=ValueError("offline")))
    monkeypatch.setattr(module, "collect_display", AsyncMock(side_effect=ValueError("offline")))
    monkeypatch.setattr(module, "get_fundamental_research", Mock(side_effect=ValueError("offline")))
    monkeypatch.setattr(module, "format_saved_interpretation", lambda *args: "")
    monkeypatch.setattr(module, "get_technical_research", lambda code: result)
    text = await module.collect_research_context("002885")
    assert '"adjusted":{"status":"available"' in text
    assert '"volume":{"status":"available"' in text
    assert '"bars":[' not in text
    assert "数据缺失与条件未满足" in text and "不混用均线" in text

"""ETF daily charts use fund precision and independently usable sources."""

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI

from backend import etf_kline
from backend.etf_contract import EtfCatalog, EtfIdentity
from backend.routers import etfs

NOW = datetime(2026, 10, 27, 3, tzinfo=ZoneInfo("Asia/Shanghai"))
IDENTITY = EtfIdentity(code="560780", symbol="sh560780", exchange="SH", name="半导体设备ETF广发")
ROW = ["2026-10-26", "0.781", "0.749", "0.790", "0.747", "5168260.000"]


def tencent(rows=None, symbol="sh560780"):
    return {"code": 0, "data": {symbol: {"day": [ROW] if rows is None else rows}}}


def sina(rows=None, symbol="sh560780"):
    import json

    if rows is None:
        rows = [{"day": "2026-10-26", "open": "0.781", "close": "0.749", "high": "0.790",
                 "low": "0.747", "volume": "516825982"}]
    return f"var _{symbol}_240_200=({json.dumps(rows)});"


async def fetch(handler, **kwargs):
    return await etf_kline.get_etf_kline(
        IDENTITY, transport=httpx.MockTransport(handler), now=NOW, **kwargs,
    )


@pytest.mark.asyncio
async def test_tencent_etf_precision_units_and_completed_dates():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=tencent())

    result = await fetch(handler)
    assert result.status == "ready" and result.source == "tencent"
    assert result.bars[0].close == 0.749 and result.bars[0].volume == 516826000
    assert result.price_tick == 0.001 and result.volume_unit == "fund_units"
    assert result.data_end.isoformat() == "2026-10-26"
    assert result.requested_end.isoformat() == "2026-10-26"
    assert result.requested_start.isoformat() == "2026-07-29"
    assert len(calls) == 1 and calls[0].url.params["param"].startswith("sh560780,day,")
    assert calls[0].url.params["param"].endswith(",")


@pytest.mark.asyncio
@pytest.mark.parametrize("upstream", [
    "http_error", "wrong_identity", "bad_price", "duplicate", "shape",
])
async def test_sina_fallback_preserves_price_and_whole_fund_units(upstream):
    def handler(request):
        if request.url.host == "web.ifzq.gtimg.cn":
            if upstream == "http_error":
                return httpx.Response(502)
            if upstream == "wrong_identity":
                return httpx.Response(200, json=tencent(symbol="sh510300"))
            if upstream == "bad_price":
                return httpx.Response(200, json=tencent([[*ROW[:2], "0.7495", *ROW[3:]]]))
            if upstream == "shape":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=tencent([ROW, ROW]))
        return httpx.Response(200, text=sina())

    result = await fetch(handler)
    assert result.status == "ready" and result.source == "sina"
    assert result.bars[0].volume == 516825982
    assert result.diagnostics[0].status == "failed"
    assert result.diagnostics[-1].status == "success"


@pytest.mark.asyncio
async def test_sina_skips_current_day_and_old_tail_without_requiring_prelisting_coverage():
    rows = [
        {"day": day, "open": "1.001", "close": "1.002", "high": "1.003",
         "low": "1.000", "volume": "100"}
        for day in ("2025-01-01", "2026-10-26", "2026-10-27")
    ]

    def handler(request):
        return (httpx.Response(200, json=tencent([])) if request.url.host == "web.ifzq.gtimg.cn"
                else httpx.Response(200, text=sina(rows)))

    result = await fetch(handler)
    assert result.status == "ready" and result.source == "sina"
    assert [bar.date.isoformat() for bar in result.bars] == ["2026-10-26"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("first", "second", "expected"), [
    ("empty", "empty", "empty"), ("error", "empty", "unavailable"),
    ("error", "error", "unavailable"),
])
async def test_empty_and_unavailable_are_distinct(first, second, expected):
    def handler(request):
        is_tencent = request.url.host == "web.ifzq.gtimg.cn"
        status = first if is_tencent else second
        return (httpx.Response(502) if status == "error" else
                httpx.Response(200, json=tencent([])) if is_tencent else
                httpx.Response(200, text=sina([])))

    result = await fetch(handler)
    assert result.status == expected and not result.bars and result.source is None
    assert result.data_start is None and result.data_end is None


@pytest.mark.asyncio
async def test_wrong_sina_identity_and_future_prices_rejected():
    def handler(request):
        return (httpx.Response(200, json=tencent([["2026-10-28", *ROW[1:]]]))
                if request.url.host == "web.ifzq.gtimg.cn" else
                httpx.Response(200, text=sina(symbol="sh510300")))

    result = await fetch(handler)
    assert result.status == "unavailable" and not result.bars


@pytest.mark.asyncio
async def test_route_validates_directory_and_days(monkeypatch):
    async def catalog():
        return EtfCatalog(items=(IDENTITY,), fetched_at=NOW)

    async def history(identity, days=90, *, include_today=False):
        assert identity == IDENTITY and days == 730 and include_today
        return await fetch(lambda request: httpx.Response(200, json=tencent()), days=days)

    monkeypatch.setattr(etfs, "get_catalog", catalog)
    monkeypatch.setattr(etfs, "get_etf_kline", history)
    app = FastAPI()
    app.include_router(etfs.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/api/etfs/560780/kline?days=730")
        assert response.status_code == 200 and response.json()["identity"]["symbol"] == "sh560780"
        assert (await client.get("/api/etfs/600000/kline")).status_code == 404
        for path in ["/api/etfs/abc/kline", "/api/etfs/560780/kline?days=731"]:
            assert (await client.get(path)).status_code == 422

        async def broken_catalog():
            raise TimeoutError("upstream private details")

        monkeypatch.setattr(etfs, "get_catalog", broken_catalog)
        response = await client.get("/api/etfs/560780/kline")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ETF_CATALOG_UNAVAILABLE"
        assert "private" not in response.text


@pytest.mark.asyncio
async def test_outer_deadline_returns_bounded_unavailable(monkeypatch):
    import asyncio

    async def handler(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=tencent())

    monkeypatch.setattr(etf_kline, "TOTAL_TIMEOUT", 0.01)
    result = await fetch(handler)
    assert result.status == "unavailable" and not result.bars
    assert any(item.error_code == "request_timeout" for item in result.diagnostics)


@pytest.mark.asyncio
async def test_shenzhen_identity_and_stock_precision_are_preserved():
    from src.data.kline import RawDailyBar

    identity = EtfIdentity(code="159915", symbol="sz159915", exchange="SZ", name="创业板ETF")

    def handler(request):
        assert request.url.params["param"].startswith("sz159915,day,")
        return httpx.Response(200, json=tencent(symbol="sz159915"))

    result = await etf_kline.get_etf_kline(
        identity, transport=httpx.MockTransport(handler), now=NOW,
    )
    assert result.status == "ready" and result.identity.exchange == "SZ"
    assert str(RawDailyBar.model_fields["price_tick"].default) == "0.01"


@pytest.mark.asyncio
@pytest.mark.parametrize("clock", [
    "2026-11-04T10:30:00+08:00", "2026-11-04T15:35:00+08:00",
    "2026-11-03T16:30:00+00:00",
])
async def test_display_includes_provider_today_in_beijing_without_synthetic_bars(clock):
    identity = EtfIdentity(code="588110", symbol="sh588110", exchange="SH", name="科创成长ETF广发")
    rows = [
        ["2026-11-03", "0.409", "0.385", "0.410", "0.382", "1703511.000"],
        ["2026-11-04", "0.386", "0.426", "0.429", "0.382", "2438380.000"],
    ]
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["param"] == "sh588110,day,2024-11-05,2026-11-04,740,"
        return httpx.Response(200, json=tencent(rows, symbol=identity.symbol))

    result = await etf_kline.get_etf_kline(
        identity, days=730, include_today=True, now=datetime.fromisoformat(clock),
        transport=httpx.MockTransport(handler),
    )
    assert result.status == "ready" and len(calls) == 1
    assert result.data_end.isoformat() == "2026-11-04"
    assert result.bars[-1].model_dump(mode="json") == {
        "date": "2026-11-04", "open": 0.386, "close": 0.426, "high": 0.429,
        "low": 0.382, "volume": 243838000,
    }
    assert "未收盘" in " ".join(result.limitations)


@pytest.mark.asyncio
async def test_display_tries_existing_fallback_for_newer_whole_series():
    def handler(request):
        if request.url.host == "web.ifzq.gtimg.cn":
            return httpx.Response(200, json=tencent())
        return httpx.Response(200, text=sina([
            {"day": "2026-10-27", "open": "0.751", "close": "0.752", "high": "0.755",
             "low": "0.750", "volume": "120001"},
        ]))

    result = await fetch(handler, include_today=True)
    assert result.source == "sina" and result.status == "ready"
    assert [bar.date.isoformat() for bar in result.bars] == ["2026-10-27"]
    assert result.bars[0].volume == 120001  # No cross-source concatenation or lot conversion.
    assert [item.status for item in result.diagnostics] == ["success", "success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", ["http_error", "empty", "older", "timeout"])
async def test_display_keeps_usable_history_when_fallback_cannot_improve_it(monkeypatch, fallback):
    import asyncio

    async def handler(request):
        if request.url.host == "web.ifzq.gtimg.cn":
            return httpx.Response(200, json=tencent())
        if fallback == "timeout":
            await asyncio.sleep(0.1)
        if fallback == "http_error":
            return httpx.Response(502)
        rows = [] if fallback == "empty" else [
            {"day": "2026-10-23", "open": "0.781", "close": "0.749", "high": "0.790",
             "low": "0.747", "volume": "100"},
        ]
        return httpx.Response(200, text=sina(rows))

    monkeypatch.setattr(etf_kline, "TOTAL_TIMEOUT", 0.02)
    result = await fetch(handler, include_today=True)
    assert result.status == "ready" and result.source == "tencent"
    assert result.data_end.isoformat() == "2026-10-26"
    assert len(result.bars) == 1  # Never fill missing sessions with quote/zero placeholders.
    assert len(result.diagnostics) == 2
    if fallback == "timeout":
        assert result.diagnostics[-1].error_code == "request_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [
    [["2026-10-28", *ROW[1:]]],
    [["2026-10-27", *ROW[1:]], ["2026-10-27", *ROW[1:]]],
    [["2026-10-27", "0.781", "0.999", "0.790", "0.747", "100"]],
])
async def test_today_permission_does_not_relax_future_order_or_ohlc_validation(rows):
    def handler(request):
        if request.url.host == "web.ifzq.gtimg.cn":
            return httpx.Response(200, json=tencent(rows))
        return httpx.Response(200, text=sina([]))

    result = await fetch(handler, include_today=True)
    assert result.status == "unavailable" and not result.bars
    assert result.diagnostics[0].error_code == "invalid_upstream_payload"

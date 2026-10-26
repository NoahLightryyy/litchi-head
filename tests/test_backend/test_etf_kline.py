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

    async def history(identity, days=90):
        assert identity == IDENTITY and days == 730
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

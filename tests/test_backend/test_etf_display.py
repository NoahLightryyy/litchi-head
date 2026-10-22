from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend import etf_display as provider
from backend.etf_contract import EtfCatalog, EtfIdentity
from backend.routers.discovery import search
from src.data.providers.quotes import SHANGHAI

IDENTITY = EtfIdentity(code="510050", symbol="sh510050", exchange="SH", name="上证50ETF")
NOW = datetime(2026, 10, 9, 16, tzinfo=SHANGHAI)


def quote_raw(symbol="sh510050", day="2026-10-09", price="2.919"):
    fields = ["上证50ETF华夏", "2.907", "2.918", price, "2.930", "2.883"] + ["0"] * 24
    return f'var hq_str_{symbol}="' + ",".join(fields + [day, "15:34:59", "00"]) + '";'


def test_quote_preserves_source_day_and_three_decimal_price():
    quote = provider.parse_quote(quote_raw(day="2026-10-08"), IDENTITY, NOW)
    assert quote.price == 2.919
    assert quote.quoted_at.date().isoformat() == "2026-10-08"
    assert quote.change_pct == pytest.approx((2.919 - 2.918) / 2.918 * 100)


@pytest.mark.parametrize(
    "raw",
    [
        quote_raw(symbol="sz159915"),
        quote_raw(day="2099-01-01"),
        quote_raw(price="nan"),
        quote_raw(price="0"),
        'var hq_str_sh510050="";',
    ],
)
def test_bad_quote_is_not_displayed(raw):
    with pytest.raises(ValueError):
        provider.parse_quote(raw, IDENTITY, NOW)


def test_catalog_checks_count_pagination_and_identity():
    rows = [
        {"symbol": f"sh{510000 + i}", "code": str(510000 + i), "name": f"基金{i}"}
        for i in range(101)
    ]

    def handler(request):
        if "StockCount" in request.url.path:
            return httpx.Response(200, json="101")
        page = int(request.url.params["page"])
        return httpx.Response(200, json=rows[(page - 1) * 100 : page * 100])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with patch.object(provider.httpx, "Client", return_value=client):
        snapshot = provider.fetch_catalog()
    assert len(snapshot.items) == 101
    assert snapshot.items[-1].code == "510100"


@pytest.mark.parametrize("mode", ["truncated", "repeat", "extra", "count_changed"])
def test_incomplete_catalog_is_rejected(mode):
    calls = 0
    row = {"symbol": "sh510050", "code": "510050", "name": "50ETF"}

    def handler(request):
        nonlocal calls
        if "StockCount" in request.url.path:
            calls += 1
            return httpx.Response(
                200, json=str(2 if mode == "repeat" or mode == "count_changed" and calls > 1 else 1)
            )
        page = int(request.url.params["page"])
        data = [row] if page == 1 or mode == "extra" else []
        if mode == "repeat" and page == 1:
            data = [row, row]
        if mode == "truncated":
            data = []
        return httpx.Response(200, json=data)

    with patch.object(
        provider.httpx, "Client", return_value=httpx.Client(transport=httpx.MockTransport(handler))
    ):
        with pytest.raises(ValueError):
            provider.fetch_catalog()


@pytest.mark.asyncio
async def test_etf_category_search_survives_stock_directory_failure():
    snapshot = EtfCatalog(items=(IDENTITY,), fetched_at=NOW)
    with (
        patch("backend.routers.discovery.get_catalog", new=AsyncMock(return_value=snapshot)),
        patch("backend.routers.discovery.stock_catalog", side_effect=ValueError),
        patch("backend.routers.discovery.board_catalog", return_value=[]),
    ):
        result = await search(" ETF ")
    assert [(hit.code, hit.kind) for hit in result.data] == [("510050", "etf")]
    assert result.failed_sources == ["股票目录"]


def test_detail_never_treats_unknown_stock_as_etf(client):
    snapshot = EtfCatalog(items=(IDENTITY,), fetched_at=NOW)
    with (
        patch("backend.routers.etfs.get_catalog", new=AsyncMock(return_value=snapshot)),
        patch("backend.etf_display.fetch_quote", side_effect=ValueError),
    ):
        assert client.get("/api/etfs/600000").status_code == 404
        result = client.get("/api/etfs/510050")
    assert result.status_code == 200
    assert result.json()["quote"] is None
    assert result.json()["status"] == "partial"


def test_catalog_failure_is_not_unknown_identity(client):
    with patch("backend.routers.etfs.get_catalog", new=AsyncMock(side_effect=ValueError)):
        result = client.get("/api/etfs/510050")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "ETF_CATALOG_UNAVAILABLE"

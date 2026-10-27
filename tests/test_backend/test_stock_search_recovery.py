"""Exact-code recovery does not require the all-market directory or an LLM."""

from unittest.mock import AsyncMock, patch

from backend.quote_display import DisplayQuote
from src.data.models import StockInfo
from src.data.providers.stock_catalog import StockCatalogSnapshot


def test_partial_directory_returns_matches_but_not_false_empty_success(client):
    partial = StockCatalogSnapshot(
        items=[StockInfo(code="002885", name="京泉华")], failed_markets=["沪市"],
    )
    with patch("backend.routers.stocks.collector.get_stock_catalog", return_value=partial):
        found = client.get("/api/stocks/search", params={"q": "京泉华"})
        absent = client.get("/api/stocks/search", params={"q": "沪市公司"})
    assert found.status_code == 200
    assert found.json()["data"][0]["code"] == "002885"
    assert absent.status_code == 503


def test_empty_directory_recovers_checked_company(client, mock_collector):
    mock_collector._stocks = []
    with (
        patch("backend.routers.stocks.collector", mock_collector),
        patch(
            "backend.routers.stocks.company_context",
            AsyncMock(return_value=("中邮科技股份有限公司", "公司资料")),
        ) as identity,
        patch("backend.routers.stocks.get_display_quote", return_value=None),
    ):
        response = client.get("/api/stocks/search", params={"q": "688648"})
    assert response.status_code == 200
    assert response.json()["data"] == [
        {"code": "688648", "name": "中邮科技股份有限公司", "market": ""}
    ]
    identity.assert_awaited_once_with("688648")


def test_directory_error_uses_profile_then_matching_short_name(client, mock_collector):
    quote = DisplayQuote(
        code="688648",
        name="中邮科技",
        price=34,
        change=1,
        change_pct=3,
        high=34,
        low=33,
        prev_close=33,
        volume=1,
        amount=34,
        fetched_at="2026-10-26T15:00:00+08:00",
        source="sina",
    )
    with (
        patch("backend.routers.stocks.collector.get_stock_catalog", side_effect=TimeoutError),
        patch(
            "backend.routers.stocks.company_context",
            AsyncMock(return_value=("中邮科技股份有限公司", "公司资料")),
        ),
        patch("backend.routers.stocks.get_display_quote", return_value=quote),
    ):
        response = client.get("/api/stocks/search", params={"q": "688648"})
    assert response.json()["data"][0]["name"] == "中邮科技"


def test_unavailable_directory_is_not_successful_empty_search(client, mock_collector):
    mock_collector._stocks = []
    with (
        patch("backend.routers.stocks.collector", mock_collector),
        patch(
            "backend.routers.stocks.company_context",
            AsyncMock(side_effect=ValueError("not corporate identity")),
        ) as identity,
        patch("backend.routers.stocks.get_display_quote") as quote,
    ):
        name = client.get("/api/stocks/search", params={"q": "中邮科技"})
        assert name.status_code == 503
        identity.assert_not_called()
        response = client.get("/api/stocks/search", params={"q": "560780"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STOCK_SEARCH_UNAVAILABLE"
    quote.assert_not_called()

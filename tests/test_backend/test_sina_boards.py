from datetime import datetime
from unittest.mock import patch

from tests.test_data.test_sina_boards import provider


def test_api_never_labels_total_flow_as_main_or_service_time_as_quote(client):
    from backend.routers import market
    with patch.object(market.sina_boards, "fetch", return_value=provider().fetch()):
        response = client.get("/api/market/sectors?source=sina&sort=net_flow")
    assert response.status_code == 200
    body = response.json()
    item = body["data"][0]
    assert item["source"] == "sina" and item["id"].startswith("sina:")
    assert item["fund_flow"] is None and item["net_flow"] == 1
    assert item["as_of"] is None
    assert datetime.fromisoformat(item["service_updated_at"]).year == 2026
    assert body["meta"]["sort_applied"] == "net_flow"
    assert body["meta"]["status"] == "partial"


def test_preview_frontend_cors_preflight(client):
    response = client.options("/api/market/sectors", headers={
        "Origin": "http://localhost:3001", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_member_api_contract_errors_and_bounds(client):
    from backend.routers import market
    from tests.test_data.test_sina_members import provider as members_provider
    result = members_provider()[0].fetch("new_swzz", 2)
    with patch.object(market.sina_members, "fetch", return_value=result) as fetch:
        response = client.get("/api/market/sina/sector/new_swzz/stocks?page=2")
        assert response.status_code == 200
        assert response.json()["data"]["stocks"][0]["code"] == "300199"
        assert response.json()["meta"]["status"] == "partial"
        fetch.assert_called_once_with("new_swzz", 2)
    assert client.get("/api/market/sina/sector/BK1629/stocks").status_code == 422
    assert client.get("/api/market/sina/sector/new_swzz/stocks?page=0").status_code == 422
    with patch.object(market.sina_members, "fetch", side_effect=TimeoutError):
        response = client.get("/api/market/sina/sector/new_swzz/stocks")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SINA_MEMBERS_FAILED"
    schema = client.get("/openapi.json").json()
    assert "SinaMembersEnvelope" in schema["components"]["schemas"]

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

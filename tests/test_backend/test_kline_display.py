from datetime import UTC, date, datetime
from unittest.mock import patch

from src.data.evidence import EvidenceCapability, SourceResult, SourceStatus
from src.data.kline import RawDailyBar


def test_raw_display_contract(client):
    bar = RawDailyBar(code="300913", market="SZSE", trade_date=date(2026, 9, 18),
                      open=40, high=42, low=39, close=41, volume=100)
    result = SourceResult(source_id="direct-tencent-raw-daily", upstream_id="tencent",
                          capability=EvidenceCapability.KLINE, status=SourceStatus.SUCCESS_DATA,
                          items=[bar], fetched_at=datetime.now(UTC))
    with patch("backend.kline_display.raw_daily_source.fetch", return_value=result):
        response = client.get("/api/stocks/300913/kline-raw-display")
    payload = response.json()
    assert response.status_code == 200
    assert payload["price_basis"] == "raw"
    assert payload["verification"] == "single_source"
    assert payload["data_end"] == "2026-09-18"
    assert payload["bars"][0]["amount"] is None


def test_raw_display_failed_source_keeps_empty(client):
    result = SourceResult(source_id="direct-tencent-raw-daily", upstream_id="tencent",
                          capability=EvidenceCapability.KLINE, status=SourceStatus.FAILED,
                          error_code="upstream_request_failed", error_message="private upstream")
    with patch("backend.kline_display.raw_daily_source.fetch", return_value=result):
        response = client.get("/api/stocks/300913/kline-raw-display")
    assert response.json()["bars"] == []
    assert response.json()["data_end"] is None
    assert "private upstream" not in response.text
    assert client.get("/api/stocks/invalid/kline-raw-display").status_code == 422


def test_extended_display_window_is_bounded_and_forwarded(client):
    result = SourceResult(source_id="direct-tencent-raw-daily", upstream_id="tencent",
                          capability=EvidenceCapability.KLINE, status=SourceStatus.FAILED,
                          error_code="upstream_request_failed", error_message="failed")
    with patch("backend.kline_display.raw_daily_source.fetch", return_value=result) as fetch:
        assert client.get("/api/stocks/603986/kline-raw-display?days=900").status_code == 200
        request = fetch.call_args.args[0]
        assert (request.end_at - request.start_at).days == 899
        assert request.end_at.date() < datetime.now(UTC).date()
    assert client.get("/api/stocks/603986/kline-raw-display?days=951").status_code == 422

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from backend.intraday_display import SHANGHAI, get_five_day_display, parse_five_day

NOW = datetime(2026, 10, 1, tzinfo=SHANGHAI)


def payload(mode="ok"):
    rows = [{"date": "20260930", "data": ["0930 23.1 10 2310", "0931 23.2 20 4600"]},
            {"date": "20260929", "data": ["0930 22.5 10 2250"]}]
    if mode == "duplicate":
        rows[0]["data"].append("0930 23.4")
    if mode == "nan":
        rows[0]["data"][0] = "0930 NaN"
    if mode == "holiday":
        rows[0]["date"] = "20260925"
    if mode == "future":
        rows[0]["date"] = "20261009"
    if mode == "empty":
        rows = []
    return json.dumps({"code": 0, "data": {"sz300199": {"data": rows}}}).encode()


def test_actual_prices_sorted_without_filling_gaps():
    value = parse_five_day(payload(), "300199", NOW)
    assert value.status == "partial" and len(value.days) == 2
    assert len(value.points) == 3 and value.points[0].close == 22.5
    assert len(value.incomplete_days) == 2
    assert value.verification == "single_source"
    assert parse_five_day(payload("empty"), "300199", NOW).status == "empty"


@pytest.mark.parametrize("mode", ["duplicate", "nan", "holiday", "future"])
def test_reject_corrupt_minutes(mode):
    with pytest.raises(ValueError):
        parse_five_day(payload(mode), "300199", NOW)


def test_api_contract_and_failed_source(client):
    with patch("backend.intraday_display._default_fetcher", return_value=payload()), \
         patch("backend.intraday_display._cache", {}):
        result = client.get("/api/stocks/300199/intraday-five-day-display")
        assert result.status_code == 200
        assert result.json()["verification"] == "single_source"
        assert len(result.json()["points"]) == 3
    with patch("backend.intraday_display._default_fetcher", side_effect=TimeoutError), \
         patch("backend.intraday_display._cache", {}):
        value = get_five_day_display("300199")
        assert value.status == "failed" and value.points == []
    assert client.get("/api/stocks/bad/intraday-five-day-display").status_code == 422

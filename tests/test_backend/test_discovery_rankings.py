from datetime import date, datetime
from unittest.mock import patch

import pytest

from backend.discovery_rankings import (
    RankingStore,
    expected_window,
    fetch_rankings,
    parse_rankings,
)
from src.data.providers.quotes import SHANGHAI

NOW = datetime(2026, 10, 7, 18, tzinfo=SHANGHAI)
STAMP = datetime(2026, 9, 30, 15, tzinfo=SHANGHAI).timestamp()


def payload():
    return {"data": {"diff": [
        {"f12": "300893", "f14": "松原", "f2": 15, "f127": 7, "f267": 120, "f124": STAMP},
        {"f12": "600001", "f14": "测试", "f2": 10, "f127": 9, "f267": -30, "f124": STAMP},
    ]}}


def test_holiday_windows_are_trading_days():
    assert expected_window("latest", NOW) == (date(2026, 9, 30), date(2026, 9, 30))
    assert expected_window("previous", NOW) == (date(2026, 9, 29), date(2026, 9, 29))
    assert expected_window("3", NOW) == (date(2026, 9, 28), date(2026, 9, 30))


def test_each_metric_uses_its_own_period_field_and_sorting():
    assert parse_rankings(payload(), "change", "3", NOW).data[0].code == "600001"
    result = parse_rankings(payload(), "main_net", "3", NOW)
    assert result.data[0].value == 120
    assert result.data[1].value == -30
    assert result.unit == "CNY"


def test_invalid_values_and_wrong_dates_are_excluded_not_zeroed():
    data = payload()
    data["data"]["diff"][0]["f267"] = "-"
    result = parse_rankings(data, "main_net", "3", NOW)
    assert len(result.data) == 1 and result.status == "partial"
    data["data"]["diff"][1]["f124"] = STAMP - 86400
    with pytest.raises(ValueError):
        parse_rankings(data, "main_net", "3", NOW)


def test_prior_snapshot_is_exact_date_and_survives_restart(tmp_path):
    store = RankingStore(tmp_path / "rank.db")
    result = parse_rankings(payload(), "change", "3", NOW)
    store.save(result)
    reopened = RankingStore(store.path)
    assert reopened.get("change", "3", date(2026, 9, 30)).cached
    assert reopened.get("main_net", "3", date(2026, 9, 30)) is None
    assert reopened.get("change", "3", date(2026, 9, 29)) is None


def test_gross_flow_and_missing_history_never_substitute_net_or_daily():
    with patch("backend.discovery_rankings.httpx.get") as fetch:
        assert fetch_rankings("gross_in", "3", NOW).status == "unavailable"
        assert fetch_rankings("main_net", "60", NOW).data == []
        fetch.assert_not_called()

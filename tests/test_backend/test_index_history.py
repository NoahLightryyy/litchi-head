from datetime import datetime

import pytest

from backend.index_history import parse_index_history
from src.data.providers.quotes import SHANGHAI

NOW = datetime(2026, 10, 7, tzinfo=SHANGHAI)


def sample():
    return {
        "code": 0,
        "data": {"sh000001": {"day": [["2026-09-30", "3800", "3842", "3850", "3790", "12345"]]}},
    }


def test_index_identity_and_native_units():
    result = parse_index_history(sample(), "sh000001", NOW)
    assert result.name == "上证指数"
    assert result.bars[0].close == 3842
    assert result.volume_unit == "source_native"
    for symbol in ("000001", "sz000001", "sz399001"):
        with pytest.raises(ValueError):
            parse_index_history(sample(), symbol, NOW)


@pytest.mark.parametrize("offset,value", [(1, "nan"), (3, "1"), (5, "-1"), (0, "2027-01-01")])
def test_rejects_invalid_candles(offset, value):
    payload = sample()
    payload["data"]["sh000001"]["day"][0][offset] = value
    with pytest.raises(ValueError):
        parse_index_history(payload, "sh000001", NOW)


def test_duplicate_dates_rejected():
    payload = sample()
    rows = payload["data"]["sh000001"]["day"]
    rows.append(rows[0])
    with pytest.raises(ValueError):
        parse_index_history(payload, "sh000001", NOW)

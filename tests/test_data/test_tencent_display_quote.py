"""Display-only quote snapshots from the already used Tencent daily endpoint."""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.quotes import SHANGHAI
from src.data.providers.tencent_display_quote import TencentDisplayQuoteSource


def payload(code="002885", market="51"):
    fields = [""] * 62
    for index, value in {
        0: market,
        1: "京泉华",
        2: code,
        3: "20.10",
        4: "20.93",
        5: "21.17",
        6: "73840",
        30: "20261027161418",
        31: "-0.83",
        32: "-3.97",
        33: "21.34",
        34: "20.01",
        35: "20.10/73840/153088192",
        61: "GP-A",
    }.items():
        fields[index] = value
    symbol = ("sh" if market == "1" else "sz") + code
    return {
        "code": 0,
        "data": {
            symbol: {"qt": {symbol: fields}, "day": [["2026-10-26", "99", "99", "99", "99", "99"]]}
        },
    }


def fetch(data):
    return TencentDisplayQuoteSource(fetcher=lambda *_: data).fetch(
        EvidenceRequest(stock_code="002885", capability=EvidenceCapability.REALTIME_QUOTE)
    )


def test_snapshot_is_not_the_last_daily_bar_and_retains_quote_time_and_units():
    result = fetch(payload())
    assert result.status == SourceStatus.SUCCESS_DATA
    quote = result.items[0]
    assert quote.name == "京泉华" and quote.price == 20.10
    assert quote.volume == 7_384_000 and quote.amount == 153_088_192
    assert quote.fetched_at == datetime(2026, 10, 27, 16, 14, 18, tzinfo=SHANGHAI)
    assert result.upstream_id == "tencent"


@pytest.mark.parametrize(
    ("index", "value"),
    [
        (0, "1"),
        (1, " "),
        (2, "000001"),
        (3, "nan"),
        (3, "0"),
        (4, "0"),
        (6, "1.2"),
        (6, "-1"),
        (30, "20261027"),
        (30, "20260230150000"),
        (31, "99"),
        (32, "99"),
        (33, "1"),
        (35, "20.10/1/200"),
        (35, "20.10/73840/-2"),
        (61, "ZS"),
        (61, "ETF"),
    ],
)
def test_bad_snapshot_never_becomes_a_price(index, value):
    data = payload()
    data["data"]["sz002885"]["qt"]["sz002885"][index] = value
    assert fetch(data).status == SourceStatus.FAILED


def test_missing_qt_is_not_replaced_with_kline_close():
    data = payload()
    del data["data"]["sz002885"]["qt"]
    assert fetch(data).status == SourceStatus.FAILED


def test_transport_failure_is_not_empty_success():
    with patch(
        "src.data.providers.tencent_display_quote._default_tencent_fetcher",
        side_effect=RuntimeError("offline"),
    ):
        result = TencentDisplayQuoteSource().fetch(
            EvidenceRequest(stock_code="002885", capability=EvidenceCapability.REALTIME_QUOTE)
        )
    assert result.status == SourceStatus.FAILED
    assert result.error_code == "upstream_request_failed"


def test_other_instrument_capability_or_unsupported_market_does_not_request():
    for code, capability in [
        ("000001", EvidenceCapability.MARKET_INDEX),
        ("920344", EvidenceCapability.REALTIME_QUOTE),
    ]:
        with patch(
            "src.data.providers.tencent_display_quote._default_tencent_fetcher"
        ) as transport:
            result = TencentDisplayQuoteSource().fetch(
                EvidenceRequest(stock_code=code, capability=capability)
            )
        transport.assert_not_called()
        assert result.status == SourceStatus.FAILED


def test_shanghai_identity_and_raw_bytes_are_supported():
    import json

    data = payload("688648", "1")
    result = TencentDisplayQuoteSource(fetcher=lambda *_: json.dumps(data).encode()).fetch(
        EvidenceRequest(stock_code="688648", capability=EvidenceCapability.REALTIME_QUOTE)
    )
    assert result.status == SourceStatus.SUCCESS_DATA
    assert result.items[0].code == "688648"


@pytest.mark.parametrize(
    "data", [{}, {"code": -1}, {"code": 0, "data": {}}, {"code": 0, "data": {"sh002885": {}}}]
)
def test_missing_or_wrong_exchange_data_is_rejected(data):
    assert fetch(data).status == SourceStatus.FAILED

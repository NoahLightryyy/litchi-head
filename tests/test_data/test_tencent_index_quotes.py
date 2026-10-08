"""Tencent index snapshots: identity, units, timestamps and failure semantics."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.tencent_index_quotes import TencentIndexQuoteSource


def payload(code="000001"):
    symbol = "sh000001" if code == "000001" else "sz" + code
    fields = [""] * 62
    for index, value in {
        0: "1" if code == "000001" else "51", 1: "上证指数", 2: code,
        3: "3842.19", 4: "3830.45", 5: "3839.25", 6: "414560247",
        30: "20260930161500", 31: "11.74", 32: "0.31",
        33: "3851.22", 34: "3833.09",
        35: "3842.19/414560247/679398992445", 61: "ZS",
    }.items():
        fields[index] = value
    return {"code": 0, "data": {symbol: {"qt": {symbol: fields}}}}


def request(code="000001"):
    return EvidenceRequest(capability=EvidenceCapability.MARKET_INDEX, stock_code=code)


@pytest.mark.parametrize("code", ["000001", "399001", "399006"])
def test_tencent_index_snapshot_uses_exchange_identity_and_quote_time(code):
    result = TencentIndexQuoteSource(fetcher=lambda _: payload(code)).fetch(request(code))
    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.upstream_id == "tencent"
    quote = result.items[0]
    assert quote.code == code
    assert quote.price == 3842.19
    assert quote.change == 11.74
    assert quote.change_pct == 0.31
    assert quote.volume == 41456024700  # Tencent hands -> shares
    assert quote.amount == 679398992445
    assert quote.fetched_at == datetime(2026, 9, 30, 16, 15, tzinfo=ZoneInfo("Asia/Shanghai"))


@pytest.mark.parametrize(("index", "value"), [
    (0, "51"), (2, "399001"), (3, "nan"), (3, "inf"), (3, "0"),
    (4, "0"), (6, "-1"), (6, "1.5"), (30, "20260930"),
    (30, "20260230150000"), (31, "100"), (32, "20"),
    (33, "3800"), (35, "3842.19/1/679398992445"), (61, "GP"),
])
def test_malformed_or_wrong_identity_is_not_consensus_evidence(index, value):
    data = deepcopy(payload())
    data["data"]["sh000001"]["qt"]["sh000001"][index] = value
    result = TencentIndexQuoteSource(fetcher=lambda _: data).fetch(request())
    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert result.items == []


@pytest.mark.parametrize("data", [{}, {"code": -1}, {"code": 0, "data": {}},
                                  {"code": 0, "data": {"sz000001": {}}}])
def test_missing_snapshot_does_not_become_zero_quote(data):
    result = TencentIndexQuoteSource(fetcher=lambda _: data).fetch(request())
    assert result.status is SourceStatus.FAILED
    assert not result.items


def test_transport_failure_is_distinct_from_payload_error():
    def fetch(_):
        raise httpx.ReadTimeout("timeout")
    result = TencentIndexQuoteSource(fetcher=fetch).fetch(request())
    assert result.status is SourceStatus.FAILED
    assert result.error_code == "upstream_request_failed"


def test_network_request_uses_index_symbol_and_finite_timeout(monkeypatch):
    def get(url, **kwargs):
        assert url == "https://web.ifzq.gtimg.cn/appstock/app/minute/query"
        assert kwargs["params"] == {"code": "sh000001"}
        assert 0 < kwargs["timeout"] <= 5
        return httpx.Response(200, json=payload(), request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", get)
    result = TencentIndexQuoteSource().fetch(request())
    assert result.status is SourceStatus.SUCCESS_DATA

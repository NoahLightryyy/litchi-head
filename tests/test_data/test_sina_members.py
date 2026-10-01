import httpx
import pytest

from src.data.providers.sina_members import SinaMemberProvider


def provider(mode="ok"):
    stamps = []
    calls = []
    def respond(request):
        method = request.url.path.rsplit(".", 1)[-1]
        calls.append(request)
        if method == "ssi_get_extend":
            stamps.append(1)
            return httpx.Response(200, json=str(1790751708 + (
                len(stamps) if mode == "changed" else 0)))
        assert request.url.params["bankuai"] == "0/new_swzz"
        if method == "ssc_bkzj_ssggzj":
            return httpx.Response(200, json="21")
        assert request.url.params["page"] == "2"
        rows = [{"symbol": "sz300199", "name": "翰宇药业", "trade": "23.92",
                 "changeratio": "0.049", "netamount": "324307288"}]
        if mode == "nan":
            rows[0]["netamount"] = "NaN"
        if mode == "missing":
            rows = []
        if mode == "symbol":
            rows[0]["symbol"] = "new_swzz"
        return httpx.Response(200, json=rows)
    return SinaMemberProvider(httpx.MockTransport(respond)), calls


def test_members_native_category_pagination_units_and_cache():
    p, calls = provider()
    result = p.fetch("new_swzz", 2)
    assert result.total == 21 and result.page_size == 20
    assert result.stocks[0].code == "300199"
    assert result.stocks[0].change_pct == pytest.approx(4.9)
    assert result.stocks[0].net_flow == pytest.approx(3.24307288)
    assert result.service_updated_at.isoformat() == "2026-09-30T15:01:48+08:00"
    assert p.fetch("new_swzz", 2).cached and len(calls) == 4


@pytest.mark.parametrize("mode", ["nan", "missing", "symbol", "changed"])
def test_members_fail_closed(mode):
    p, _ = provider(mode)
    with pytest.raises(ValueError):
        p.fetch("new_swzz", 2)
    assert not p._cache


def test_invalid_query_does_not_reach_upstream():
    p, calls = provider()
    with pytest.raises(ValueError):
        p.fetch("BK1629")
    assert not calls


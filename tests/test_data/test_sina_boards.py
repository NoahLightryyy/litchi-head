"""Sina pagination and semantic boundaries for display enrichment."""

import httpx
import pytest

from src.data.providers.sina_boards import SinaBoardProvider


def provider(mode="ok"):
    timestamps = []
    def respond(request):
        method = request.url.path.rsplit(".", 1)[-1]
        flag = request.url.params.get("fenlei", "0")
        if method == "ssi_get_extend":
            timestamps.append(1)
            return httpx.Response(200, json=str(
                1790751708 + (len(timestamps) if mode == "changed" else 0)))
        if method == "ssc_bkzj_bk":
            return httpx.Response(200, json="101" if flag == "1" else "1")
        page = int(request.url.params["page"])
        size = 100 if flag == "1" and page == 1 else 1
        rows = [{"cate_type": flag,
                 "category": ("new_" if flag == "0" else "gn_")+str((page-1)*100+i),
                 "name": "鏉垮潡", "avg_changeratio": "0.012", "netamount": "100000000"}
                for i in range(size)]
        if mode == "missing" and page == 2:
            rows = []
        if mode == "duplicate" and page == 2:
            rows[0]["category"] = "gn_0"
        if mode == "nan":
            rows[0]["netamount"] = "nan"
        if mode == "wrong_kind":
            rows[0]["cate_type"] = "5"
        return httpx.Response(200, json=rows)
    return SinaBoardProvider(httpx.MockTransport(respond))


def test_full_pagination_units_and_cache():
    p = provider()
    result = p.fetch()
    assert len(result.boards) == 102
    assert result.boards[0].change_pct == 1.2
    assert result.boards[0].net_flow == 100000000
    assert result.service_updated_at.isoformat() == "2026-09-30T15:01:48+08:00"
    assert p.fetch().cached


@pytest.mark.parametrize("mode", ["missing", "duplicate", "nan", "wrong_kind", "changed"])
def test_bad_enrichment_is_not_published(mode):
    p = provider(mode)
    with pytest.raises(ValueError):
        p.fetch()
    assert p._cache is None


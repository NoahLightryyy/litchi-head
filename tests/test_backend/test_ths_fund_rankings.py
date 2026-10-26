from datetime import datetime

import httpx
import pytest

from backend import ths_fund_rankings as ths
from src.data.providers.quotes import SHANGHAI

NOW = datetime(2026, 10, 26, 18, tzinfo=SHANGHAI)


def html(values=("2.30亿", "-500.00万"), field="zjjlr"):
    headers = ["序号", "股票代码", "股票简称", "最新价", "涨跌幅", "换手率",
               "流入资金(元)", "流出资金(元)", "净额(元)", "成交额(元)"]
    head = "".join(f'<th>{h}</th>' if i != 8 else
                   f'<th class="cur"><a field="{field}">{h}</a><i class="arr-down"></i></th>'
                   for i, h in enumerate(headers))
    rows = "".join(f'<tr><td>{i+1}</td><td>{600001+i}</td><td>公司{i}</td>'
                   f'<td>12.50</td><td>1%</td><td>2%</td><td>3亿</td><td>1亿</td>'
                   f'<td>{v}</td><td>4亿</td></tr>' for i, v in enumerate(values))
    return f'<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def test_units_negative_zero_and_unknown_date_are_preserved():
    result = ths.parse_page(html(("2.30亿", "0.00", "-500万")), NOW)
    assert [r.net_inflow for r in result.data] == [230000000, 0, -5000000]
    assert result.source == "ths" and result.metric == "net_inflow" and result.unit == "CNY"
    assert result.data_as_of is None and result.fetched_at == NOW
    assert result.status == "partial" and result.data[0].code == "600001"


@pytest.mark.parametrize("document", ["<html>login</html>", html(field="zdf"),
                                      html(("1亿", "2亿")), html(("nan", "--"))])
def test_empty_wrong_sort_and_invalid_values_are_not_a_ranking(document):
    with pytest.raises(ValueError):
        ths.parse_page(document, NOW)


def test_duplicate_identity_rejected():
    with pytest.raises(ValueError):
        ths.parse_page(html().replace("600002", "600001"), NOW)


async def test_cache_refresh_failure_and_recovery(monkeypatch):
    monkeypatch.setattr(ths, "_cache", {})
    calls = 0

    async def fetch(period="latest"):
        nonlocal calls
        calls += 1
        return html()

    monkeypatch.setattr(ths, "fetch_page", fetch)
    first = await ths.fund_flow()
    second = await ths.fund_flow()
    assert first.data and second.cached and calls == 1
    assert first.fetched_at == second.fetched_at

    async def fail(period="latest"):
        raise httpx.ReadTimeout("private upstream details")

    monkeypatch.setattr(ths, "fetch_page", fail)
    failed = await ths.fund_flow(refresh=True)
    assert failed.status == "partial" and failed.data and failed.cached
    assert failed.fetched_at == first.fetched_at
    assert "刷新未成功" in failed.reason and "private" not in failed.reason
    # Failure does not extend the cache lifetime; an expired cache is not revived.
    inserted, previous = ths._cache["latest"]
    ths._cache["latest"] = (inserted - ths.TTL_SECONDS, previous)
    assert not (await ths.fund_flow()).data
    monkeypatch.setattr(ths, "fetch_page", fetch)
    assert (await ths.fund_flow()).data


def multi_html():
    page = html()
    for label in ["流入资金(元)", "流出资金(元)", "成交额(元)"]:
        page = page.replace(f"<th>{label}</th>", "")
    page = page.replace("涨跌幅", "阶段涨跌幅").replace("换手率", "连续换手率")
    page = page.replace("净额(元)", "资金流入净额(元)")
    page = page.replace("<td>3亿</td><td>1亿</td>", "").replace("<td>4亿</td>", "")
    return page


def test_multi_day_schema_separate_from_daily():
    result = ths.parse_page(multi_html(), NOW, "3")
    assert result.period == "3" and result.data[0].net_inflow == 230000000
    with pytest.raises(ValueError):
        ths.parse_page(multi_html(), NOW, "latest")
    with pytest.raises(ValueError):
        ths.parse_page(html(), NOW, "3")


async def test_http_contract_period_isolation_and_schema(monkeypatch):
    from fastapi import FastAPI

    monkeypatch.setattr(ths, "_cache", {})
    monkeypatch.setattr(ths, "_locks", {})
    calls = []

    async def fetch(period="latest"):
        calls.append(period)
        return html() if period == "latest" else multi_html()

    monkeypatch.setattr(ths, "fetch_page", fetch)
    app = FastAPI()
    app.include_router(ths.router, prefix="/api/discovery")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as client:
        for period in ["latest", "3", "5", "10", "20"]:
            response = await client.get(f"/api/discovery/fund-flow/ths?period={period}")
            assert response.status_code == 200
            body = response.json()
            assert body["period"] == period and body["data_as_of"] is None
            assert len(body["data"]) == 2 and not body["cached"]
        assert (await client.get("/api/discovery/fund-flow/ths?period=3")).json()["cached"]
        assert len(calls) == 5
        for period in ["previous", "60", "bad"]:
            assert (await client.get(
                f"/api/discovery/fund-flow/ths?period={period}")).status_code == 422


async def test_transport_rejects_redirected_period(monkeypatch):
    original_client = httpx.AsyncClient

    def response(request):
        if "/board/3/" in request.url.path:
            return httpx.Response(302, headers={"Location": str(request.url).replace(
                "/board/3/", "/board/5/"
            )})
        return httpx.Response(200, text=multi_html())

    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(response), **kwargs)

    monkeypatch.setattr(ths.httpx, "AsyncClient", client)
    with pytest.raises(ValueError, match="period"):
        await ths.fetch_page("3")

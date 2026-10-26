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
    assert failed.status == "unavailable" and not failed.data
    assert "private" not in failed.reason
    # Explicit refresh failure must not revive an earlier successful cache.
    assert not (await ths.fund_flow()).data
    monkeypatch.setattr(ths, "fetch_page", fetch)
    assert (await ths.fund_flow()).data

"""Recorded supplier responses and failure semantics; no live-network CI."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.data import fundamental_research as research
from src.data.providers.akshare import _row_to_financial

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures/fundamental-statements.json").read_text(encoding="utf-8")
)


def tables(code="300199"):
    return {
        kind: research.parse_statements(raw, kind, research.URL)
        for kind, raw in FIXTURE[code].items()
    }


@pytest.mark.parametrize(
    "code,margin,parent_growth",
    [("300199", 62.91366898, 62.71562065), ("600276", 86.32634609, 0.34455454)],
)
def test_official_half_year_reconciliation(code, margin, parent_growth):
    data = research.build_research(code, tables(code), [])
    assert data.metrics["gross_margin"].value == pytest.approx(margin)
    assert data.metrics["parent_profit_growth"].value == pytest.approx(parent_growth)
    assert data.statements[0].published_at.isoformat() == (
        "2026-08-21" if code == "300199" else "2026-08-20"
    )
    assert data.metrics["pe"].value is None
    assert data.metrics["pe"].reason
    assert data.verification == "single_source"


def test_ttm_not_ytd_and_requires_all_periods():
    data = research.build_research("300199", tables(), [])
    assert data.metrics["revenue_ttm"].value == pytest.approx(1105196594.21)
    assert data.metrics["parent_profit_ttm"].value == pytest.approx(127801442.78)
    truncated = tables()
    truncated["lrb"] = truncated["lrb"][:1]
    assert research.build_research("300199", truncated, []).metrics["revenue_ttm"].value is None
    annual = tables()
    annual["lrb"] = [r for r in annual["lrb"] if r.report_date.month == 12]
    result = research.build_research("300199", annual, [])
    assert result.metrics["revenue_ttm"].value == result.metrics["revenue"].value


def test_zero_negative_and_absent_are_distinct():
    data = tables()
    data["lrb"][0].amounts["BIZCOST"] = data["lrb"][0].amounts["BIZINCO"]
    data["lrb"][0].amounts["PARENETP"] = -10
    result = research.build_research("300199", data, [])
    assert result.metrics["gross_margin"].value == 0
    assert result.metrics["parent_profit"].value == -10
    data["lrb"][0].amounts.pop("BIZCOST")
    data["fzb"] = data["fzb"][1:]
    result = research.build_research("300199", data, [])
    assert result.metrics["gross_margin"].value is None
    assert result.metrics["debt_ratio"].value is None  # cannot mix balance-sheet periods


@pytest.mark.parametrize("bad", ["nan", "inf", "not-a-number"])
def test_reject_nonfinite_facts(bad):
    raw = copy.deepcopy(FIXTURE["300199"]["lrb"])
    raw["result"]["data"]["report_list"]["20260630"]["data"][0]["item_value"] = bad
    with pytest.raises(ValueError):
        research.parse_statements(raw, "lrb", research.URL)


def test_reject_duplicate_facts_and_nonconsolidated_scope():
    raw = copy.deepcopy(FIXTURE["300199"]["lrb"])
    report = raw["result"]["data"]["report_list"]["20260630"]
    report["data"].append(report["data"][0])
    with pytest.raises(ValueError):
        research.parse_statements(raw, "lrb", research.URL)
    report["rType"] = "母公司期末"
    rows = research.parse_statements(raw, "lrb", research.URL)
    assert all(str(r.report_date) != "2026-06-30" for r in rows)


def test_failure_cache_and_stale_expiry(monkeypatch):
    research._entry.cache_clear()
    monkeypatch.setattr(research, "_fetch", lambda code, kind: tables(code)[kind])
    first = research.get_fundamental_research("300199")

    def fail(*args):
        raise OSError("upstream down")

    monkeypatch.setattr(research, "_fetch", fail)
    assert research.get_fundamental_research("300199") == first
    entry = research._entry("300199")
    entry.expires = 0
    stale = research.get_fundamental_research("300199")
    assert stale.status == "stale"
    assert stale.fetched_at == first.fetched_at
    entry.value.fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
    assert research.get_fundamental_research("300199").status == "unavailable"
    research._entry.cache_clear()


def test_partial_statement_failure_is_not_total_failure(monkeypatch):
    research._entry.cache_clear()

    def fetch(code, kind):
        if kind == "llb":
            raise OSError("cash flow timeout")
        return tables(code)[kind]

    monkeypatch.setattr(research, "_fetch", fetch)
    result = research.get_fundamental_research("300199")
    assert result.metrics["gross_margin"].value is not None
    assert result.metrics["operating_cash_flow"].value is None
    assert result.retryable
    research._entry.cache_clear()


def test_legacy_profit_never_becomes_revenue():
    row = _row_to_financial(pd.Series({"日期": "2026-06-30", "主营业务利润(元)": 100}), "300199")
    assert row.gross_margin is None
    assert row.operating_revenue is None
    zero = _row_to_financial(pd.Series({"销售毛利率(%)": 0, "营业收入(元)": 0}), "300199")
    assert zero.gross_margin == 0
    assert zero.operating_revenue == 0

"""Identity, evidence, persistence and failures for per-stock company interpretation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.company_research import (
    CitedInsight,
    CompanyEvidence,
    CompanyInterpretation,
    CompanyResearch,
    CompanyResearchStore,
    CompanySource,
    parse_profile,
    parse_report,
    report_links,
)
from backend.routers import company_research as module


def evidence(code="920344"):
    return CompanyEvidence(stock_code=code, company_name="测试药业股份有限公司",
                           fetched_at=datetime.now(UTC), gaps=["仅有主营业务资料"], sources=[
        CompanySource(id="profile", title="公司资料", url="https://example.com/profile",
                      excerpt="研发、生产和销售生物药"),
    ])


def interpretation():
    insight = CitedInsight(text="依据主营业务推断为药品研发生产环节。",
                           basis="inference", source_ids=["profile"])
    return CompanyInterpretation(niche=insight, upstream=insight, role=insight,
                                 downstream=insight, highlights=[insight], watchpoints=[insight])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "store", CompanyResearchStore(tmp_path / "research.db"))
    module._busy.clear()
    module.limiter.reset()
    app = FastAPI()
    app.state.limiter = module.limiter
    app.include_router(module.router)
    yield TestClient(app)
    module._busy.clear()


def test_get_is_free_and_empty_until_explicit_generation(client):
    with patch.object(module, "fetch_evidence", AsyncMock(return_value=evidence())) as fetch, \
            patch.object(module.llm_service, "invoke_structured",
                         AsyncMock(return_value=interpretation())) as generate:
        assert client.get("/api/stocks/920344/company-research").json() is None
        fetch.assert_not_called()
        generate.assert_not_called()
        response = client.post("/api/stocks/920344/company-research")
        assert response.status_code == 200
        stored = client.get("/api/stocks/920344/company-research").json()
        assert stored == response.json()
        assert stored["purpose"] == "company_context_only"
        assert stored["review_status"] == "ai_unreviewed"
        assert client.get("/api/stocks/600519/company-research").json() is None
        assert generate.await_count == 1


def test_new_store_instance_restores_and_rejects_corruption(client):
    snapshot = CompanyResearch(**evidence().model_dump(), generated_at=datetime.now(UTC),
                               model="test", interpretation=interpretation())
    module.store.save(snapshot)
    reopened = CompanyResearchStore(module.store.path)
    assert reopened.get("920344") == snapshot
    with reopened._connect() as connection:
        connection.execute("UPDATE company_research SET digest='corrupt'")
    assert client.get("/api/stocks/920344/company-research").status_code == 503


@pytest.mark.parametrize("bad", ["unknown", "duplicate"])
def test_generated_references_must_exist_and_be_unique(client, bad):
    output = interpretation()
    output.niche.source_ids = ["fake"] if bad == "unknown" else ["profile", "profile"]
    with patch.object(module, "fetch_evidence", AsyncMock(return_value=evidence())), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock(return_value=output)):
        assert client.post("/api/stocks/920344/company-research").status_code == 502
    assert module.store.get("920344") is None
    assert not module._busy


@pytest.mark.parametrize("failure,status", [(TimeoutError(), 504), (ValueError(), 502)])
def test_failed_refresh_retains_previous_result(client, failure, status):
    snapshot = CompanyResearch(**evidence().model_dump(), generated_at=datetime.now(UTC),
                               model="test", interpretation=interpretation())
    module.store.save(snapshot)
    with patch.object(module, "fetch_evidence", AsyncMock(return_value=evidence())), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock(side_effect=failure)):
        assert client.post("/api/stocks/920344/company-research").status_code == status
    assert module.store.get("920344") == snapshot
    assert not module._busy


def test_missing_profile_or_busy_never_calls_model(client):
    with patch.object(module, "fetch_evidence", AsyncMock(side_effect=ValueError())), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock()) as generate:
        assert client.post("/api/stocks/920344/company-research").status_code == 503
        module._busy.add("920344")
        assert client.post("/api/stocks/920344/company-research").status_code == 429
        assert client.post("/api/stocks/bad/company-research").status_code == 422
        generate.assert_not_called()


def test_profile_requires_stock_identity_and_business():
    html = '<h1 id="stockName">三元基因 (920344.BJ)</h1><table id="comInfo1">' \
           '<tr><td>公司名称：</td><td>测试药业股份有限公司</td></tr>' \
           '<tr><td>主营业务：</td><td>研发、生产和销售生物药。</td></tr></table>'
    assert parse_profile(html, "920344")[0] == "测试药业股份有限公司"
    with pytest.raises(ValueError):
        parse_profile(html, "600519")
    with pytest.raises(ValueError):
        parse_profile(html.replace("主营业务", "公司简介"), "920344")


def test_report_links_bound_to_symbol_and_host():
    html = '<a href="https://evil.test/corp/view/vCB_AllBulletinDetail.php?' \
           'stockid=920344&id=123">三元基因：2025年年度报告</a>' \
           '<a href="/corp/view/vCB_AllBulletinDetail.php?stockid=600519&id=456">' \
           '茅台：2025年年度报告</a>'
    links = report_links(html, "920344")
    assert len(links) == 1
    assert links[0][1].startswith("https://vip.stock.finance.sina.com.cn/")


@pytest.mark.parametrize("change", ["company", "date", "future"])
def test_report_identity_and_publication_date(change):
    html = '<div>公告日期:2025-08-26</div><div id="content">测试药业股份有限公司 主营业务</div>'
    assert parse_report(html, "测试药业股份有限公司", "2025半年报", "https://example.com", "r")
    if change == "company":
        html = html.replace("测试药业", "其他公司")
    elif change == "date":
        html = html.replace("公告日期", "未知日期")
    else:
        html = html.replace("2025-08-26", "2099-08-26")
    with pytest.raises(ValueError):
        parse_report(html, "测试药业股份有限公司", "半年报", "https://example.com", "r")

"""Company supplements preserve the graph, identity, sources and previous successful cache."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import chain_companies as service
from backend.chain_companies_contract import ChainCompaniesResponse
from backend.chain_draft_contract import DraftGraph, DraftResponse
from backend.routers import chain_companies as router
from backend.routers import chain_draft


def draft(code="BK1184", name="人形机器人"):
    return DraftResponse(
        sector_code=code,
        sector_name=name,
        generated_at=datetime.now(UTC),
        model=service.DEFAULT_MODEL,
        graph=DraftGraph(
            map_kind="industry_chain",
            scope="研究结构",
            nodes=[
                {"id": "parts", "label": "零部件", "role": "硬件", "verify": "产品"},
                {"id": "integration", "label": "整机", "role": "整机制造", "verify": "生产"},
            ],
            edges=[{"source": "parts", "target": "integration", "explanation": "投入"}],
        ),
    )


def proposal(name="绿的谐波", code="688017", node="parts"):
    return service.CompanyProposal(
        node_id=node,
        name=name,
        suggested_code=code,
        business="精密传动产品",
        influence="关注精密传动能力及量产进展。",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(chain_draft, "CACHE_ROOT", tmp_path / "drafts")
    monkeypatch.setattr(service, "CACHE_ROOT", tmp_path / "companies")
    chain_draft.CACHE_ROOT.mkdir()
    initial = draft()
    chain_draft.draft_path(initial.sector_code, initial.sector_name).write_text(
        initial.model_dump_json()
    )
    monkeypatch.setattr(
        service,
        "company_context",
        AsyncMock(
            return_value=(
                "苏州绿的谐波传动科技股份有限公司",
                "公司名称：苏州绿的谐波传动科技股份有限公司。主营业务：谐波减速器。",
            )
        ),
    )
    monkeypatch.setattr(
        service.llm_service,
        "invoke_structured",
        AsyncMock(return_value=service.CompanyProposals(companies=[proposal()])),
    )
    router._busy.clear()
    app = FastAPI()
    app.state.limiter = router.limiter
    app.include_router(router.router)
    with TestClient(app) as value:
        yield value
    router._busy.clear()


def post(client, **body):
    return client.post(
        "/api/market/sector/BK1184/chain-companies", json={"sector_name": "人形机器人", **body}
    )


def test_first_generate_then_read_without_spend(client):
    first, second = post(client), post(client)
    assert first.status_code == second.status_code == 200
    one = ChainCompaniesResponse.model_validate(first.json())
    assert one.companies[0].name == "绿的谐波"
    assert one.companies[0].a_share_code == "688017"
    assert len(one.companies[0].sources) == 2
    assert "谐波减速器" in one.companies[0].business
    assert second.json()["cached"] is True
    assert second.json()["generated_at"] == first.json()["generated_at"]
    assert service.llm_service.invoke_structured.await_count == 1
    assert service.llm_service.invoke_structured.call_args.kwargs["output_method"] == "json_mode"


def test_missing_graph_or_identity_does_not_generate(client):
    missing = client.post("/api/market/sector/BK0917/chain-companies", json={"sector_name": "其他"})
    assert missing.status_code == 409
    assert missing.json()["error"]["retryable"] is False
    assert post(client, sector_name="其他名称").status_code == 409
    assert post(client, sector_name="").status_code == 422
    service.llm_service.invoke_structured.assert_not_called()


def test_refresh_failure_preserves_prior_result_and_graph(client):
    first = post(client).json()
    graph_path = chain_draft.draft_path("BK1184", "人形机器人")
    before = graph_path.read_bytes()
    service.llm_service.invoke_structured.side_effect = TimeoutError()
    assert post(client, refresh=True).status_code == 504
    assert post(client).json()["generated_at"] == first["generated_at"]
    assert graph_path.read_bytes() == before
    assert not router._busy


def test_bad_candidate_does_not_replace_cache(client):
    first = post(client).json()
    service.llm_service.invoke_structured.return_value = service.CompanyProposals(
        companies=[proposal(node="unknown")]
    )
    assert post(client, refresh=True).status_code == 502
    assert post(client).json()["generated_at"] == first["generated_at"]


def test_busy_and_corrupt_storage_visible_without_spend(client):
    router._busy.update({"busy1", "busy2"})
    assert post(client).status_code == 429
    service.llm_service.invoke_structured.assert_not_called()
    router._busy.clear()
    post(client)
    path = next(service.CACHE_ROOT.glob("*.json"))
    path.write_text("invalid")
    assert post(client).status_code == 503
    assert service.llm_service.invoke_structured.await_count == 1
    assert post(client, refresh=True).status_code == 200


@pytest.mark.asyncio
async def test_wrong_code_or_failed_source_keeps_company_without_misleading_stock_link(monkeypatch):
    catalog = service.catalog_for("人形机器人")
    for effect in [None, TimeoutError()]:
        lookup = AsyncMock(return_value=("另一家公司", "主营不同业务"), side_effect=effect)
        monkeypatch.setattr(service, "company_context", lookup)
        resolved = await service.resolve_company(proposal(), catalog)
        assert resolved.name == "绿的谐波" and resolved.a_share_code is None
        assert len(resolved.sources) == 1 and resolved.reference_status == "public_reference"
    result = await service.resolve_company(proposal("其他候选企业", "600000"), catalog)
    assert result.name == "其他候选企业" and result.reference_status == "ai_candidate"
    assert not result.sources and result.a_share_code is None


@pytest.mark.asyncio
async def test_overseas_and_unlisted_names_never_take_guessed_a_share_code(monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr(service, "company_context", lookup)
    for name in ["NVIDIA", "Tesla", "宇树", "优必选"]:
        company = await service.resolve_company(
            proposal(name, "600000"), service.catalog_for("人形机器人")
        )
        assert company.a_share_code is None and company.sources
    lookup.assert_not_called()


def test_catalog_scope_and_graph_revision_isolate_caches():
    humanoid = draft()
    catalog = service.catalog_for("人形机器人")
    assert len(catalog.companies) == 6
    assert service.catalog_for("医疗器械").companies == []
    key = service.cache_key(humanoid, catalog)
    different = humanoid.model_copy(deep=True)
    different.graph.nodes[0].role = "不同的结构"
    assert key != service.cache_key(different, catalog)
    assert key != service.cache_key(draft("sina:gn_jqr"), catalog)


def test_response_rejects_duplicate_company_and_missing_reference(client):
    body = post(client).json()
    body["companies"].append(body["companies"][0].copy())
    with pytest.raises(ValidationError):
        ChainCompaniesResponse.model_validate(body)
    body["companies"].pop()
    body["companies"][0]["sources"] = []
    with pytest.raises(ValidationError):
        ChainCompaniesResponse.model_validate(body)


def test_cache_rejects_code_or_name_without_matching_identity_source(client):
    post(client)
    path = next(service.CACHE_ROOT.glob("*.json"))
    original = path.read_text()
    for field, value in [("a_share_code", "600000"), ("name", "另一家公司")]:
        body = json.loads(original)
        body["companies"][0][field] = value
        path.write_text(json.dumps(body))
        assert post(client).status_code == 503
    assert service.llm_service.invoke_structured.await_count == 1


def test_storage_write_failure_is_visible_and_does_not_cache(client, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("write unavailable")

    monkeypatch.setattr(type(service.CACHE_ROOT), "mkdir", fail)
    assert post(client).status_code == 503
    assert not router._busy

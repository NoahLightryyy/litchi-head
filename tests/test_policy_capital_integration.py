"""Consumer checks against the actual app registration, with no live model calls."""
import asyncio

import httpx
import pytest

from backend.main import app
from backend.policy_evidence import EvidenceRepository
from backend.policy_research import PolicyDraft, PolicyResearchService, ResearchStore
from backend.routers import policy_research


@pytest.mark.asyncio
async def test_registered_evidence_and_preview_boundaries():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get("/api/research/evidence/v1-stock-688012")
        assert response.status_code == 200
        assert response.json()["subject_id"] == "688012"
        body = dict(evidence_package_id="v1-stock-688012", instrument_kind="stock",
                    symbol="688012", market="SH", cash_available_cny=None,
                    user_budget_cny=None, limit_price_cny=None, quote_at=None,
                    permission_confirmed=None, rules=None, fees=None)
        response = await c.post("/api/research/execution-preview", json=body)
        result = response.json()
        assert response.status_code == 200
        assert result["status"] == "blocked" and result["quantity"] is None
        assert result["estimated_cost"] is None and result["remaining_cash"] is None
        assert "缺少可用现金" in result["gaps"]
        for endpoint in ("/api/research/execution-preview", "/api/research/jobs"):
            error = await c.post(endpoint, json={})
            assert error.status_code == 422
            assert error.json()["code"] == "VALIDATION_ERROR"
        body["evidence_package_id"] = "v1-stock-unknown"
        assert (await c.post("/api/research/execution-preview", json=body)).status_code == 404


@pytest.mark.asyncio
async def test_registered_job_revisit_does_not_rebill(tmp_path, monkeypatch):
    calls = 0

    async def runner(package, job_id):
        nonlocal calls
        calls += 1
        return PolicyDraft(claims=package.claims, conditions=["需要订单证据"],
                           counterarguments=["设备订单未证实"], gaps=package.gaps)

    service = PolicyResearchService(ResearchStore(tmp_path / "research.db"),
                                    EvidenceRepository(), runner)
    monkeypatch.setattr(policy_research, "_runtime", service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        request = dict(idempotency_key="integration-revisit", evidence_package_id="v1-stock-688012",
                       subject_kind="stock", subject_id="688012", max_cost_cny="100")
        first = await c.post("/api/research/jobs", json=request)
        assert first.status_code == 202
        job_id = first.json()["job_id"]
        await asyncio.gather(*list(service.tasks))
        replay = await c.post("/api/research/jobs", json=request)
        assert replay.json()["job_id"] == job_id
        result = (await c.get(f"/api/research/jobs/{job_id}")).json()
        assert result["status"] == "succeeded" and calls == 1
        assert result["result"]["subject_id"] == "688012"
        conflict = await c.post("/api/research/jobs", json={**request, "max_cost_cny": "101"})
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    await service.close()


def test_actual_openapi_has_frozen_models_and_contract_errors():
    schema = app.openapi()
    paths = schema["paths"]
    for path, method in (("/api/research/jobs", "post"),
                         ("/api/research/execution-preview", "post")):
        assert paths[path][method]["responses"]["422"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ContractError"}

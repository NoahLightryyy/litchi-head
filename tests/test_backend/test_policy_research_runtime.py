from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.policy_capital_contract import ResearchRequest
from backend.policy_evidence import EvidenceRepository
from backend.policy_research import PolicyResearchService, ResearchStore
from backend.routers.policy_research import create_router


def request(**overrides):
    return ResearchRequest(
        **{
            "idempotency_key": "test-key-0001",
            "evidence_package_id": "v1-sector-BK0917",
            "subject_kind": "sector",
            "subject_id": "BK0917",
            "max_cost_cny": Decimal("0.000001"),
            **overrides,
        }
    )


def test_repository_subject_and_archive():
    package = EvidenceRepository().get("v1-sector-BK0917")
    assert package.subject_id == "BK0917"
    assert package.status == "partial" and package.gaps
    assert package.evidence and all(e.snapshot_sha256 for e in package.evidence)
    with pytest.raises(KeyError):
        EvidenceRepository().get("v1-etf-159915")


@pytest.mark.asyncio
async def test_budget_prevents_model_call_and_idempotency(tmp_path):
    async def forbidden(*args):
        pytest.fail("must not spend below reserved budget")

    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"), runner=forbidden)
    job, created = service.submit(request())
    assert created and job.status == "queued"
    same, created = service.submit(request())
    assert same.job_id == job.job_id and not created
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        service.submit(request(max_cost_cny=Decimal("5")))
    await service.run(job.job_id)
    failed = service.store.get(job.job_id)
    assert failed.error.code == "BUDGET_EXCEEDED"


def test_restart_and_subject_mismatch(tmp_path):
    store = ResearchStore(tmp_path / "jobs.db")
    service = PolicyResearchService(store)
    with pytest.raises(ValueError, match="VALIDATION_ERROR"):
        service.submit(request(subject_id="other"))
    job, _ = service.submit(request())
    store.claim(job.job_id)
    store.recover_interrupted()
    assert store.get(job.job_id).error.code == "INTERRUPTED"


def test_http_errors_and_discovery(tmp_path):
    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"))
    app = FastAPI()
    app.include_router(create_router(service))
    with TestClient(app) as client:
        assert client.get("/api/research/evidence/v1-sector-BK0917").status_code == 200
        r = client.get("/api/research/evidence/missing")
        assert r.status_code == 404 and r.json()["code"] == "PACKAGE_NOT_FOUND"
        r = client.post("/api/research/jobs", json={})
        assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_success_restored_and_citations_are_server_checked(tmp_path):
    from backend.policy_research import PolicyDraft

    calls = []

    async def runner(package, job_id):
        calls.append(job_id)
        return PolicyDraft(
            claims=package.claims,
            conditions=["需求转化需要真实订单"],
            counterarguments=["资本开支下降可能抵消需求"],
            gaps=[],
        )

    store = ResearchStore(tmp_path / "jobs.db")
    service = PolicyResearchService(store, runner=runner)
    job, _ = service.submit(request(max_cost_cny=Decimal("10")))
    await service.run(job.job_id)
    await service.run(job.job_id)
    restored = ResearchStore(tmp_path / "jobs.db").get(job.job_id)
    assert len(calls) == 1 and restored.status == "succeeded"
    assert restored.result.subject_id == "BK0917"
    assert restored.result.gaps and restored.result.estimated_cost_cny > 0
    assert service.submit(request(max_cost_cny=Decimal("10.00")))[0] == restored


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_claim",
    [
        dict(
            id="fake",
            text="政策带来确定盈利",
            assessment="supported",
            evidence_ids=["P1"],
            limitations=[],
        ),
        dict(
            id="fake",
            text="可能影响需求",
            assessment="inferred",
            evidence_ids=["invented"],
            limitations=["未核验"],
        ),
    ],
)
async def test_rejects_fake_profits_and_references(tmp_path, bad_claim):
    from backend.policy_research import PolicyDraft

    async def runner(package, job_id):
        return PolicyDraft(
            claims=[bad_claim], conditions=["条件"], counterarguments=["反证"], gaps=[]
        )

    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"), runner=runner)
    job, _ = service.submit(request(max_cost_cny=Decimal("10")))
    await service.run(job.job_id)
    assert service.store.get(job.job_id).error.code == "MODEL_FAILED"


def test_tampered_snapshot_is_unavailable(tmp_path):
    import shutil

    from backend.policy_evidence import DATA_DIR

    shutil.copytree(DATA_DIR, tmp_path / "evidence")
    (tmp_path / "evidence" / "P1.html").write_text("tampered")
    with pytest.raises(OSError, match="checksum"):
        EvidenceRepository(tmp_path / "evidence").get("v1-sector-BK0917")


@pytest.mark.asyncio
async def test_cancellation_terminalizes_job(tmp_path):
    import asyncio

    started = asyncio.Event()

    async def runner(package, job_id):
        started.set()
        await asyncio.Event().wait()

    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"), runner=runner)
    job, _ = service.submit(request(max_cost_cny=Decimal("10")))
    service.schedule(job.job_id)
    await asyncio.wait_for(started.wait(), timeout=2)
    await service.close()
    assert service.store.get(job.job_id).error.code == "INTERRUPTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["wrong_source", "reversed_assessment"])
async def test_curated_fact_must_keep_source_and_assessment(tmp_path, mutation):
    from backend.policy_research import PolicyDraft

    async def runner(package, job_id):
        claim = package.claims[0].model_copy(deep=True)
        if mutation == "wrong_source":
            claim.evidence_ids = ["N1"]
        else:
            claim.assessment = "contradicted"
            claim.limitations = ["模型认为反例"]
        return PolicyDraft(claims=[claim], conditions=["条件"], counterarguments=["反证"], gaps=[])

    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"), runner=runner)
    job, _ = service.submit(request(max_cost_cny=Decimal("10")))
    await service.run(job.job_id)
    assert service.store.get(job.job_id).error.code == "MODEL_FAILED"


def test_exact_budget_fingerprint(tmp_path):
    service = PolicyResearchService(ResearchStore(tmp_path / "jobs.db"))
    service.submit(request(max_cost_cny=Decimal("1.1234567890123456789012345678901")))
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        service.submit(request(max_cost_cny=Decimal("1.1234567890123456789012345678902")))

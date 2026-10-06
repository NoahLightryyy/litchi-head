"""AI chain contract: explicit generation, citations, cache and failure isolation."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import sector_chain as module
from src.data.chain_evidence import get_sector_chain


@pytest.fixture(autouse=True)
def reset_cache():
    module._cache.clear()
    module._busy.clear()
    yield
    module._cache.clear()
    module._busy.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = module.limiter
    app.include_router(module.router)
    return TestClient(app)


def valid_output():
    evidence = get_sector_chain("BK1106", "创新药")
    assert evidence is not None
    return module.ChainInterpretation(summary="依据资料整理的活动示意。", stages=[
        module.StageExplanation(node_id=n.id, explanation=n.label, source_ids=list(n.source_ids))
        for n in evidence.nodes
    ])


def test_explicit_post_generates_and_caches_reviewed_references(client):
    generate = AsyncMock(return_value=valid_output())
    with patch.object(module.llm_service, "invoke_structured", generate):
        assert client.get("/api/market/sector/BK1106/chain-analysis").status_code == 405
        first = client.post("/api/market/sector/BK1106/chain-analysis")
        second = client.post("/api/market/sector/BK1106/chain-analysis")
    assert first.status_code == 200
    assert first.json()["review_status"] == "ai_unreviewed"
    assert first.json()["citation_coverage"] == 1
    assert not first.json()["cached"] and second.json()["cached"]
    assert generate.await_count == 1
    assert generate.call_args.kwargs["provider"] == "deepseek"


@pytest.mark.parametrize("failure", ["source", "node", "duplicate", "missing"])
def test_invalid_ai_references_do_not_enter_cache(client, failure):
    output = valid_output()
    if failure == "source":
        output.stages[0].source_ids = ["invented"]
    elif failure == "node":
        output.stages[0].node_id = "invented-company"
    elif failure == "duplicate":
        output.stages.append(output.stages[0])
    else:
        output.stages.pop()
    with patch.object(module.llm_service, "invoke_structured", AsyncMock(return_value=output)):
        response = client.post("/api/market/sector/BK1106/chain-analysis")
    assert response.status_code == 502
    assert not module._cache and not module._busy


def test_no_evidence_never_calls_ai(client):
    with patch.object(module.llm_service, "invoke_structured", AsyncMock()) as generate:
        response = client.post("/api/market/sector/BK9999/chain-analysis")
    assert response.status_code == 404
    assert response.json()["error"]["retryable"] is False
    generate.assert_not_called()


@pytest.mark.parametrize("error,status", [(TimeoutError(), 504), (RuntimeError("offline"), 502)])
def test_failure_is_retryable_and_releases_busy_state(client, error, status):
    with patch.object(module.llm_service, "invoke_structured", AsyncMock(side_effect=error)):
        response = client.post("/api/market/sector/BK1106/chain-analysis")
    assert response.status_code == status
    assert response.json()["error"]["retryable"] is True
    assert not module._cache and not module._busy


def test_busy_rejects_without_another_model_request(client):
    module._busy.update({"request1", "request2"})
    with patch.object(module.llm_service, "invoke_structured", AsyncMock()) as generate:
        assert client.post("/api/market/sector/BK1106/chain-analysis").status_code == 429
    generate.assert_not_called()

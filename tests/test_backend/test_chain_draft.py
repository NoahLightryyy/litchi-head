"""Drafts cannot masquerade as reviewed maps; caching prevents repeated spend."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.chain_draft_contract import DraftGraph
from backend.routers import chain_draft as module


def graph():
    return DraftGraph(
        map_kind="industry_chain",
        scope="一般研究框架，待核验",
        nodes=[
            {"id": "a", "label": "材料", "role": "生产投入", "verify": "材料成本"},
            {"id": "b", "label": "制造", "role": "加工", "verify": "产能利用率"},
        ],
        edges=[{"source": "a", "target": "b", "explanation": "一般投入关系"}],
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "CACHE_ROOT", tmp_path)
    module._busy.clear()
    app = FastAPI()
    app.state.limiter = module.limiter
    app.include_router(module.router)
    with TestClient(app) as c:
        yield c
    module._busy.clear()


def test_persistence_identity_and_no_repeat_spend(client):
    with patch.object(
        module.llm_service, "invoke_structured", AsyncMock(return_value=graph())
    ) as llm:
        first = client.post(
            "/api/market/sector/BK0917/chain-draft", json={"sector_name": "测试行业"}
        )
        second = client.post(
            "/api/market/sector/BK0917/chain-draft", json={"sector_name": "测试行业"}
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["review_status"] == "ai_inferred_unverified"
        assert second.json()["cached"]
        assert llm.await_count == 1
        client.post("/api/market/sector/BK0917/chain-draft", json={"sector_name": "其他行业"})
        assert llm.await_count == 2


@pytest.mark.parametrize("kind", ["unknown", "self", "duplicate"])
def test_bad_edges_rejected(kind):
    value = graph().model_dump()
    if kind == "unknown":
        value["edges"][0]["target"] = "not_in_graph"
    elif kind == "self":
        value["edges"][0]["target"] = "a"
    else:
        value["edges"].append(value["edges"][0])
    with pytest.raises(ValidationError):
        DraftGraph.model_validate(value)


@pytest.mark.parametrize("error,status", [(TimeoutError(), 504), (ValueError(), 502)])
def test_failures_visible_and_uncached(client, error, status):
    with patch.object(module.llm_service, "invoke_structured", AsyncMock(side_effect=error)):
        result = client.post("/api/market/sector/BK0917/chain-draft", json={"sector_name": "测试"})
    assert result.status_code == status
    assert result.json()["error"]["retryable"]
    assert not list(module.CACHE_ROOT.glob("*.json"))
    assert not module._busy


def test_invalid_and_busy_do_not_spend(client):
    with patch.object(module.llm_service, "invoke_structured", AsyncMock()) as llm:
        assert (
            client.post(
                "/api/market/sector/BK0917/chain-draft", json={"sector_name": ""}
            ).status_code
            == 422
        )
        module._busy.update({"a", "b"})
        assert (
            client.post(
                "/api/market/sector/BK0917/chain-draft", json={"sector_name": "测试"}
            ).status_code
            == 429
        )
        llm.assert_not_called()

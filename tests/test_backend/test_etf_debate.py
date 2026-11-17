"""ETF debates use typed identities and the existing graph without corporate side effects."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.debate.models import AgentAnalysis, DebateResult
from src.debate.session_store import SqliteDebateSessionStore


@pytest.fixture(autouse=True)
def isolated_sessions(tmp_path):
    with (
        patch(
            "backend.routers.debate._session_store",
            SqliteDebateSessionStore(tmp_path / "sessions.db"),
        ),
        patch("backend.routers.debate._analysis_is_configured", return_value=True),
    ):
        yield


def test_etf_identity_flow_persistence_and_history_separation(client):
    class Engine:
        async def run(self, inp):
            assert inp.instrument_type == "etf" and inp.stock_name == "半导体设备ETF广发"
            assert "场内ETF" in inp.question
            return DebateResult(**inp.model_dump(), analyses=[AgentAnalysis(
                agent_name="master.fixture", skill_id="fixture", skill_name="测试流派",
                rating="", score=50, summary="测试摘要", analysis="测试分析", success=True,
            )])

    with (
        patch(
            "backend.routers.debate._get_etf_orchestrator",
            new_callable=AsyncMock,
            return_value=("半导体设备ETF广发", Engine()),
        ) as engine,
        patch("backend.routers.debate.resolve_stock_name") as stock_lookup,
        patch("backend.routers.debate._get_orchestrator") as stock_engine,
        patch("backend.routers.debate._auto_create_retro_record", new_callable=AsyncMock) as retro,
    ):
        response = client.post(
            "/api/debate/run", json={"stock_code": "560780", "instrument_type": "etf"}
        )
    assert response.status_code == 200
    engine.assert_awaited_once_with("560780")
    stock_lookup.assert_not_called()
    stock_engine.assert_not_called()
    retro.assert_not_awaited()
    sid = response.json()["data"]["session_id"]
    result = client.get(f"/api/debate/result/{sid}").json()["data"]
    assert result["instrument_type"] == "etf" and result["stock_code"] == "560780"
    status = client.get(f"/api/debate/status/{sid}").json()["data"]
    assert status["instrument_type"] == "etf"
    history = client.get(
        "/api/debate/history", params={"stock_code": "560780", "instrument_type": "etf"}
    ).json()["data"]
    assert len(history) == 1 and history[0]["session_id"] == sid
    assert client.get("/api/debate/history", params={"stock_code": "560780"}).json()["data"] == []


@pytest.mark.parametrize(
    "status,message", [(404, "未在ETF目录中找到该代码"), (503, "ETF资料准备暂时失败")]
)
def test_etf_preparation_failure_does_not_fall_back_to_stock(client, status, message):
    with (
        patch(
            "backend.routers.debate._get_etf_orchestrator",
            new_callable=AsyncMock,
            side_effect=HTTPException(status, message),
        ),
        patch("backend.routers.debate._get_orchestrator") as engine,
    ):
        response = client.post(
            "/api/debate/run", json={"stock_code": "560780", "instrument_type": "etf"}
        )
    assert response.status_code == status and response.json()["error"]["message"] == message
    engine.assert_not_called()
    records = client.get(
        "/api/debate/history", params={"stock_code": "560780", "instrument_type": "etf"}
    ).json()["data"]
    assert records[0]["status"] == "failed"


def test_invalid_instrument_type_rejected_before_inference(client):
    with patch("backend.routers.debate._get_etf_orchestrator") as engine:
        response = client.post(
            "/api/debate/run", json={"stock_code": "560780", "instrument_type": "fund"}
        )
    assert response.status_code == 422
    engine.assert_not_called()
    schema = client.get("/openapi.json").json()["components"]["schemas"]["DebateRequest"]
    assert schema["properties"]["instrument_type"]["default"] == "stock"
    assert schema["properties"]["instrument_type"]["enum"] == ["stock", "etf"]


def test_result_and_status_contracts_expose_instrument_identity(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for name in ("DebateRunData", "DebateStatusData", "DebateHistoryItem", "DebateResult"):
        assert "instrument_type" in schemas[name]["properties"]
    assert client.get("/api/debate/status/missing").json() == {
        "data": {"status": "not_found", "progress": 0}
    }
    assert client.get("/api/debate/result/missing").json() == {"data": None}


def test_legacy_stock_request_for_named_etf_does_not_run_company_analysis(client):
    with (
        patch("backend.routers.debate.resolve_stock_name", return_value="半导体设备ETF广发"),
        patch("backend.routers.debate._get_orchestrator") as company_engine,
    ):
        response = client.post("/api/debate/run", json={"stock_code": "560780"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSTRUMENT_TYPE_MISMATCH"
    company_engine.assert_not_called()

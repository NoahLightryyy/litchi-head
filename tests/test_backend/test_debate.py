"""debate.py 路由测试

覆盖：
1. POST /api/debate/run — 触发辩论
2. GET /api/debate/status/{session_id} — 查询状态
3. GET /api/debate/result/{session_id} — 获取结果
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from backend.routers.debate import _analysis_is_configured
from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
)
from src.debate.evidence_gate import EvidenceIncompleteError


@pytest.fixture(autouse=True)
def mock_stock_name_lookup():
    """Keep backend route tests independent from the live AKShare network."""
    with (
        patch("backend.routers.debate.resolve_stock_name", return_value="平安银行"),
        patch("backend.routers.debate._analysis_is_configured", return_value=True),
    ):
        yield


class _MockDebateResult(BaseModel):
    """模拟 DebateOutput"""
    stock_code: str = "000001"
    question: str = "测试问题"
    summary: str = "辩论总结"
    consensus: str = "看多"
    confidence: float = 0.75
    evidence_limitations: list[dict[str, object]] = Field(default_factory=list)


class _MockOrchestrator:
    """模拟 DebateOrchestrator"""

    def __init__(self) -> None:
        self.last_input: object = None

    async def run(self, debate_input: object) -> _MockDebateResult:
        self.last_input = debate_input
        return _MockDebateResult()


# ═══════════════════════════════════════════════════════════════════════
# POST /api/debate/run
# ═══════════════════════════════════════════════════════════════════════


class TestRunDebate:
    """触发辩论"""

    def test_configuration_failure_stops_before_data_or_model_calls(self, client):
        with (
            patch("backend.routers.debate._analysis_is_configured", return_value=False),
            patch("backend.routers.debate.resolve_stock_name") as lookup,
            patch("backend.routers.debate._get_orchestrator") as engine,
        ):
            response = client.post("/api/debate/run", json={"stock_code": "300199"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ANALYSIS_NOT_CONFIGURED"
        assert response.json()["error"]["detail"]["retryable"] is False
        lookup.assert_not_called()
        engine.assert_not_called()

    def test_identity_timeout_is_dependency_failure_not_internal_error(self, client):
        with (
            patch("backend.routers.debate.resolve_stock_name", side_effect=TimeoutError),
            patch("backend.routers.debate._get_orchestrator") as engine,
        ):
            response = client.post("/api/debate/run", json={"stock_code": "300199"})
        assert response.status_code == 503
        assert response.json()["error"]["detail"]["capability"] == "stock_identity"
        engine.assert_not_called()

    def test_invalid_identity_is_rejected_before_upstream(self, client):
        with patch("backend.routers.debate.resolve_stock_name") as lookup:
            response = client.post("/api/debate/run", json={"stock_code": "bad"})
        assert response.status_code == 422
        lookup.assert_not_called()

    def test_configuration_presence_and_public_error_contract(self, client, monkeypatch):
        from src.utils.config import settings

        monkeypatch.setattr(settings, "deepseek_api_key", "   ")
        assert not _analysis_is_configured()
        monkeypatch.setattr(settings, "deepseek_api_key", "test-only-not-a-secret")
        monkeypatch.setattr(settings, "llm_provider", "deepseek")
        # This pre-fixture import retains the real helper while routing is mocked.
        assert _analysis_is_configured()
        schema = client.get("/openapi.json").json()
        properties = schema["components"]["schemas"]["DebateUnavailableError"]["properties"]
        codes = properties["code"]["enum"]
        assert "ANALYSIS_NOT_CONFIGURED" in codes

    def test_run_debate_success(self, client):
        mock_orch = _MockOrchestrator()

        async def _run_limited(debate_input: object) -> _MockDebateResult:
            mock_orch.last_input = debate_input
            return _MockDebateResult(
                evidence_limitations=[
                    {
                        "status": "limited",
                        "capability": "news",
                        "missing_upstream_ids": ["sina"],
                    }
                ]
            )

        mock_orch.run = _run_limited  # type: ignore[method-assign]
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            resp = client.post(
                "/api/debate/run",
                json={"stock_code": "000001", "question": "后市如何？"},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "completed"
        assert data["session_id"].startswith("deb_")
        result_resp = client.get(f"/api/debate/result/{data['session_id']}")
        assert result_resp.status_code == 200
        limitation = result_resp.json()["data"]["evidence_limitations"][0]
        assert limitation["status"] == "limited"
        assert limitation["missing_upstream_ids"] == ["sina"]

    def test_run_debate_without_question(self, client):
        """question 可选"""
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"

    def test_run_debate_resolves_stock_name_for_evidence_matching(self, client):
        mock_orch = _MockOrchestrator()
        with (
            patch("backend.routers.debate._get_orchestrator", return_value=mock_orch),
            patch(
                "backend.routers.debate.resolve_stock_name",
                return_value="平安银行",
            ),
        ):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 200
        assert getattr(mock_orch.last_input, "stock_name") == "平安银行"

    def test_missing_stock_identity_fails_before_orchestrator(self, client):
        mock_orch = _MockOrchestrator()
        with (
            patch("backend.routers.debate._get_orchestrator", return_value=mock_orch),
            patch("backend.routers.debate.resolve_stock_name", return_value=""),
        ):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "EVIDENCE_INCOMPLETE"
        assert mock_orch.last_input is None

    def test_run_debate_returns_session_id(self, client):
        """返回的 session_id 可用于后续查询"""
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        session_id = resp.json()["data"]["session_id"]
        assert session_id

        # 查询状态
        status_resp = client.get(f"/api/debate/status/{session_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] == "completed"

        # 查询结果
        result_resp = client.get(f"/api/debate/result/{session_id}")
        assert result_resp.status_code == 200
        assert result_resp.json()["data"] is not None

    def test_run_debate_error(self, client):
        """orchestrator 异常时返回 500"""
        error_orch = _MockOrchestrator()

        async def _raise_error(*args: object, **kwargs: object) -> object:
            raise ValueError("模拟辩论失败")

        error_orch.run = _raise_error  # type: ignore[method-assign]
        with patch("backend.routers.debate._get_orchestrator", return_value=error_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 500
        assert "辩论执行失败" in resp.json()["detail"]

    def test_incomplete_evidence_returns_503_with_retry_details(self, client):
        error_orch = _MockOrchestrator()
        request = EvidenceRequest(
            capability=EvidenceCapability.NEWS,
            stock_code="000001",
        )
        policy = EvidencePolicy(
            capability=EvidenceCapability.NEWS,
            min_independent_upstreams=2,
        )
        envelope = EvidenceEnvelope(
            request=request,
            policy=policy,
            assessment=EvidenceAssessment(
                capability=EvidenceCapability.NEWS,
                complete=False,
                missing_independent_upstreams=1,
                missing_required_upstream_ids={"sina"},
            ),
            complete=False,
        )

        async def _raise_incomplete(*args: object, **kwargs: object) -> object:
            raise EvidenceIncompleteError(envelope, retry_after_seconds=300)

        error_orch.run = _raise_incomplete  # type: ignore[method-assign]
        with patch("backend.routers.debate._get_orchestrator", return_value=error_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 503
        error = resp.json()["error"]
        assert error["code"] == "EVIDENCE_INCOMPLETE"
        assert error["detail"]["missing_upstream_ids"] == ["sina"]
        assert error["detail"]["retry_after_seconds"] == 300

    def test_missing_stock_code_returns_422(self, client):
        """缺少必需字段 stock_code → 422"""
        resp = client.post("/api/debate/run", json={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /api/debate/status/{session_id}
# ═══════════════════════════════════════════════════════════════════════


class TestGetDebateStatus:
    """查询辩论状态"""

    def test_session_not_found(self, client):
        resp = client.get("/api/debate/status/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "not_found"

    def test_session_found(self, client):
        """先创建 session 再查询"""
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            create_resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        session_id = create_resp.json()["data"]["session_id"]
        resp = client.get(f"/api/debate/status/{session_id}")
        assert resp.json()["data"]["status"] == "completed"
        assert resp.json()["data"]["progress"] == 100


# ═══════════════════════════════════════════════════════════════════════
# GET /api/debate/result/{session_id}
# ═══════════════════════════════════════════════════════════════════════


class TestGetDebateResult:
    """获取辩论结果"""

    def test_session_not_found(self, client):
        resp = client.get("/api/debate/result/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_session_has_result(self, client):
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            create_resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        session_id = create_resp.json()["data"]["session_id"]
        resp = client.get(f"/api/debate/result/{session_id}")
        data = resp.json()["data"]
        assert data is not None
        assert "summary" in data
        assert "consensus" in data
        assert "confidence" in data


# ═══════════════════════════════════════════════════════════════════════
# 速率限制
# ═══════════════════════════════════════════════════════════════════════


class TestRateLimit:
    """辩论路由限流（默认 6/分钟）"""

    def test_rate_limit_on_post_and_get_independent(self, client):
        """POST /debate/run 超限返回 429，但 GET status/result 独立计数不受影响"""
        client.app.state.limiter.enabled = True
        mock_orch = _MockOrchestrator()

        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            # 前 6 次 POST 成功
            for i in range(6):
                resp = client.post("/api/debate/run", json={"stock_code": "000001"})
                assert resp.status_code == 200, f"第 {i+1} 次请求应成功"

            # 第 7 次 POST → 429
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})
            assert resp.status_code == 429

            # 响应格式正确
            body = resp.json()
            assert "error" in body
            assert body["error"]["code"] == "RATE_LIMITED"
            assert body["error"]["message"]

        # GET status/result 走独立限流 key，不受 POST 计数影响
        status_resp = client.get("/api/debate/status/test_session")
        assert status_resp.status_code == 200

        result_resp = client.get("/api/debate/result/test_session")
        assert result_resp.status_code == 200

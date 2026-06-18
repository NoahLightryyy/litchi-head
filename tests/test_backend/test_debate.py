"""debate.py 路由测试

覆盖：
1. POST /api/debate/run — 触发辩论
2. GET /api/debate/status/{session_id} — 查询状态
3. GET /api/debate/result/{session_id} — 获取结果
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel


class _MockDebateResult(BaseModel):
    """模拟 DebateOutput"""
    stock_code: str = "000001"
    question: str = "测试问题"
    summary: str = "辩论总结"
    consensus: str = "看多"
    confidence: float = 0.75


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

    def test_run_debate_success(self, client):
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001", "question": "后市如何？"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "completed"
        assert data["session_id"].startswith("deb_")

    def test_run_debate_without_question(self, client):
        """question 可选"""
        mock_orch = _MockOrchestrator()
        with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
            resp = client.post("/api/debate/run", json={"stock_code": "000001"})

        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"

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

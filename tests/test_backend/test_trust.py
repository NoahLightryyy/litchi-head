"""trust.py 路由 + 辅助函数测试

覆盖：
1. _trust_report_to_resp 映射函数
2. GET /api/trust/report/{agent_name}
3. GET /api/trust/leaderboard
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel


# ═══════════════════════════════════════════════════════════════════════
# Mock 数据
# ═══════════════════════════════════════════════════════════════════════


class _MockMetrics(BaseModel):
    """模拟 TrustMetrics"""
    win_rate: float = 0.65
    brier_score: float = 0.25
    confidence_bias: float = 0.05
    trend_direction: str = "stable"
    total_samples: int = 100


class _MockTrustReport(BaseModel):
    """模拟 TrustReport"""
    agent_name: str = "巴菲特"
    skill_name: str = "价值投资大师"
    metrics: _MockMetrics = _MockMetrics()
    summary: str = "巴菲特历史表现稳定，胜率 65%"
    is_reliable: bool = True


class _MockEmptyReport(BaseModel):
    """无指标数据的 TrustReport"""
    agent_name: str = "新大师"
    skill_name: str = "新手"
    metrics: None = None
    summary: str = "暂无信任度数据"
    is_reliable: bool = False


class _MockTracker:
    """模拟 TrustTracker"""

    def __init__(self, reports: dict[str, _MockTrustReport] | None = None) -> None:
        self._reports = (
            reports
            if reports is not None
            else {
                "巴菲特": _MockTrustReport(),
                "索罗斯": _MockTrustReport(
                    agent_name="索罗斯",
                    metrics=_MockMetrics(win_rate=0.72, total_samples=50),
                    summary="索罗斯胜率 72%",
                ),
            }
        )

    async def get_trust_report(self, agent_name: str) -> _MockTrustReport:
        return self._reports.get(agent_name, _MockEmptyReport(agent_name=agent_name))

    async def get_all_agent_names(self) -> list[str]:
        return list(self._reports.keys())


# ═══════════════════════════════════════════════════════════════════════
# _trust_report_to_resp（通过后端路由间接测试）
# ═══════════════════════════════════════════════════════════════════════


class TestTrustReportToResp:
    """_trust_report_to_resp 映射逻辑（通过后端代码间接测试）"""

    def test_full_report_mapping(self, client):
        """完整报告映射到 TrustReportResp"""
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/report/巴菲特")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == "巴菲特"
        assert data["win_rate"] == 0.65
        assert data["brier_score"] == 0.25
        assert data["confidence_bias"] == 0.05
        assert data["trend_direction"] == "stable"
        assert data["total_predictions"] == 100
        assert data["is_reliable"] is True
        assert data["summary"] == "巴菲特历史表现稳定，胜率 65%"

    def test_empty_report(self, client):
        """无指标时报告只含基本信息和提示"""
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/report/不存在的")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == "不存在的"
        assert data["win_rate"] == 0.0
        assert data["total_predictions"] == 0
        assert data["is_reliable"] is False
        assert data["summary"] == "暂无信任度数据"


# ═══════════════════════════════════════════════════════════════════════
# GET /api/trust/report/{agent_name}
# ═══════════════════════════════════════════════════════════════════════


class TestGetTrustReport:
    """查询信任度报告"""

    def test_existing_agent(self, client):
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/report/巴菲特")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == "巴菲特"
        assert isinstance(data["win_rate"], float)
        assert isinstance(data["total_predictions"], int)

    def test_unknown_agent(self, client):
        """不存在的 agent 返回空报告"""
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/report/未知大师")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_name"] == "未知大师"
        # 空报告默认值
        assert data["total_predictions"] == 0

    def test_meta_timing(self, client):
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/report/巴菲特")

        meta = resp.json()["meta"]
        assert "latency_ms" in meta

    def test_error_returns_503(self, client):
        """Tracker 异常时返回 503"""
        error_tracker = _MockTracker()

        async def _raise_error(name: str) -> object:
            raise ConnectionError("数据源不可用")

        error_tracker.get_trust_report = _raise_error  # type: ignore[method-assign]
        with patch("backend.routers.trust._get_tracker", return_value=error_tracker):
            resp = client.get("/api/trust/report/巴菲特")

        assert resp.status_code == 503
        assert "查询信任度报告失败" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════
# GET /api/trust/leaderboard
# ═══════════════════════════════════════════════════════════════════════


class TestGetTrustLeaderboard:
    """信任度排行榜"""

    def test_returns_sorted_leaderboard(self, client):
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/leaderboard")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # 按 win_rate 降序: 索罗斯 0.72 > 巴菲特 0.65
        assert data[0]["agent_name"] == "索罗斯"
        assert data[1]["agent_name"] == "巴菲特"

    def test_empty_leaderboard(self, client):
        """无 agent 时返回空列表"""
        empty_tracker = _MockTracker(reports={})
        with patch("backend.routers.trust._get_tracker", return_value=empty_tracker):
            resp = client.get("/api/trust/leaderboard")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_error_returns_503(self, client):
        error_tracker = _MockTracker()

        async def _raise_error() -> object:
            raise ConnectionError("数据源不可用")

        error_tracker.get_all_agent_names = _raise_error  # type: ignore[method-assign]
        with patch("backend.routers.trust._get_tracker", return_value=error_tracker):
            resp = client.get("/api/trust/leaderboard")

        assert resp.status_code == 503

    def test_leaderboard_fields(self, client):
        """排行榜每项含所需字段"""
        tracker = _MockTracker()
        with patch("backend.routers.trust._get_tracker", return_value=tracker):
            resp = client.get("/api/trust/leaderboard")

        for item in resp.json()["data"]:
            assert "agent_name" in item
            assert "win_rate" in item
            assert "total_predictions" in item
            assert "is_reliable" in item

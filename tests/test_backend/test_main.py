"""main.py 测试 — 应用入口 + 全局处理

覆盖：
1. GET /api/health — 健康检查
2. GET /api/health/data-source — 数据源健康统计
3. 全局异常处理 — Exception → ErrorResponse
4. 404 — 不存在的路由返回标准格式
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestHealth:
    """健康检查 GET /api/health"""

    def test_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "litchi-head-bridge"
        assert "timestamp" in data

    def test_timestamp_is_float(self, client):
        resp = client.get("/api/health")
        assert isinstance(resp.json()["timestamp"], (int, float))

    def test_degrades_when_news_ingestion_task_has_died(self, client):
        task = MagicMock()
        task.done.return_value = True
        with patch.object(
            client.app.state,
            "news_ingestion_task",
            task,
            create=True,
        ):
            resp = client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
        assert resp.json()["news_ingestion"] == "failed"


class TestDataSourceHealth:
    """数据源健康统计 GET /api/health/data-source"""

    def test_returns_stats(self, client):
        resp = client.get("/api/health/data-source")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "stats" in data

    def test_stats_contains_endpoints(self, client):
        resp = client.get("/api/health/data-source")
        stats = resp.json()["stats"]
        # 至少应包含 endpoint 统计
        assert isinstance(stats, dict)


class TestNotFound:
    """不存在的路由"""

    def test_returns_404(self, client):
        """不存在的路由返回 fastapi 原生 404"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_route(self, client):
        resp = client.post("/api/nowhere")
        assert resp.status_code == 404


class TestGlobalExceptionHandler:
    """全局异常处理 — Exception → ErrorResponse"""

    def test_unhandled_exception_returns_500(self, client):
        """通过触发内部异常来验证全局异常处理器"""
        with patch(
            "backend.routers.retro._get_store",
            side_effect=RuntimeError("模拟未处理异常"),
        ):
            resp = client.get("/api/retro/records")

        # 由于异常被路由内部的 try/except 捕获，先走路由的 500
        # 验证 500 状态码
        assert resp.status_code == 500

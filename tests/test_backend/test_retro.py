"""retro.py 复盘路由测试

覆盖（6 端点全）：
1. GET /api/retro/records — 查询复盘记录列表
2. GET /api/retro/summary — 聚合统计
3. PUT /api/retro/{record_id}/action — 记录用户操作
4. PUT /api/retro/{record_id}/outcome — 更新实际结果
5. POST /api/retro/refresh — 批量刷新 pending 记录
6. DELETE /api/retro/{record_id} — 删除记录
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from src.retro.models import RetroRecord, RetroSummary

# ── Mock RetroStore ───────────────────────────────────────────────────


class _MockRetroStore:
    """模拟 RetroStore，所有方法可控"""

    def __init__(
        self,
        records: list[RetroRecord] | None = None,
        summary: RetroSummary | None = None,
    ) -> None:
        self._records = records or []
        self._summary = summary or RetroSummary(
            total_records=len(self._records),
            win_rate=0.5,
        )
        self.last_action: str | None = None
        self.last_outcome_return: float | None = None

    async def list_records(
        self,
        stock_code: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RetroRecord]:
        records = self._records
        if stock_code:
            records = [r for r in records if r.stock_code == stock_code]
        if outcome:
            records = [r for r in records if r.outcome == outcome]
        return records[offset : offset + limit]

    async def get_summary(self) -> RetroSummary:
        return self._summary

    async def update_action(self, record_id: str, action: str) -> RetroRecord | None:
        self.last_action = action
        for r in self._records:
            if r.record_id == record_id:
                r.user_action = action
                return r
        return None

    async def update_outcome(
        self,
        record_id: str,
        actual_return_pct: float,
        actual_price: float,
    ) -> RetroRecord | None:
        self.last_outcome_return = actual_return_pct
        for r in self._records:
            if r.record_id == record_id:
                r.actual_return_pct = actual_return_pct
                r.actual_price = actual_price
                r.outcome = "correct"
                return r
        return None

    async def delete(self, record_id: str) -> bool:
        for i, r in enumerate(self._records):
            if r.record_id == record_id:
                self._records.pop(i)
                return True
        return False


def make_mock_record(**overrides) -> RetroRecord:
    """工厂：创建测试用 RetroRecord"""
    data = dict(
        record_id="retro_test_001",
        session_id="deb_test_session",
        stock_code="000001",
        stock_name="平安银行",
        created_at=datetime(2024, 6, 1, 10, 0, 0),
        consensus="Bullish",
        weighted_score=7.5,
        confidence=0.82,
        direction_distribution={"Bullish": 5, "Bearish": 1, "Neutral": 1},
        avg_score=6.8,
        rating_distribution={"买入": 4, "持有": 2, "卖出": 1},
        price_at_debate=12.5,
        user_action=None,
        outcome="pending",
    )
    data.update(overrides)
    return RetroRecord(**data)


# ═══════════════════════════════════════════════════════════════════════
# GET /api/retro/records
# ═══════════════════════════════════════════════════════════════════════


class TestListRecords:
    """复盘记录列表"""

    def test_returns_records(self, client):
        """返回复盘记录列表"""
        records = [make_mock_record()]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["record_id"] == "retro_test_001"
        assert data[0]["stock_code"] == "000001"

    def test_filter_by_stock_code(self, client):
        """按股票代码过滤"""
        records = [
            make_mock_record(record_id="r1", stock_code="000001"),
            make_mock_record(record_id="r2", stock_code="000002"),
        ]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records", params={"stock_code": "000001"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["stock_code"] == "000001"

    def test_filter_by_outcome(self, client):
        """按结果过滤"""
        records = [
            make_mock_record(record_id="r1", outcome="correct"),
            make_mock_record(record_id="r2", outcome="pending"),
        ]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records", params={"outcome": "pending"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["outcome"] == "pending"

    def test_empty_list(self, client):
        """无记录时返回空列表"""
        store = _MockRetroStore(records=[])
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_meta_pagination(self, client):
        """meta 包含分页信息"""
        records = [make_mock_record(record_id=f"r{i}") for i in range(5)]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records")

        meta = resp.json()["meta"]
        assert "total" in meta
        assert "limit" in meta
        assert "offset" in meta
        assert meta["total"] == 5

    def test_limit_and_offset(self, client):
        """分页参数生效"""
        records = [make_mock_record(record_id=f"r{i}") for i in range(10)]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/records", params={"limit": 3, "offset": 5})

        data = resp.json()["data"]
        assert len(data) == 3

    def test_error_returns_500(self, client):
        """store 异常时返回 500"""
        error_store = _MockRetroStore()

        async def _raise_error(**kw) -> object:
            raise RuntimeError("store 异常")

        error_store.list_records = _raise_error  # type: ignore[method-assign]
        with patch("backend.routers.retro._get_store", return_value=error_store):
            resp = client.get("/api/retro/records")

        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# GET /api/retro/summary
# ═══════════════════════════════════════════════════════════════════════


class TestGetSummary:
    """复盘聚合统计"""

    def test_returns_summary(self, client):
        """返回聚合统计"""
        summary = RetroSummary(
            total_records=10,
            today_records=2,
            closed_records=6,
            win_count=4,
            loss_count=2,
            win_rate=0.6667,
            avg_confidence=0.75,
            avg_score=7.0,
            last_record_at=datetime(2024, 6, 1, 10, 0, 0),
        )
        store = _MockRetroStore(summary=summary)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/summary")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_records"] == 10
        assert data["today_records"] == 2
        assert data["win_count"] == 4
        assert data["win_rate"] == 0.6667
        assert data["avg_confidence"] == 0.75

    def test_empty_summary(self, client):
        """无记录时统计为零"""
        summary = RetroSummary()
        store = _MockRetroStore(summary=summary)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.get("/api/retro/summary")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_records"] == 0
        assert data["win_rate"] == 0.0

    def test_error_returns_500(self, client):
        """store 异常时返回 500"""
        error_store = _MockRetroStore()

        async def _raise() -> object:
            raise RuntimeError("store 异常")

        error_store.get_summary = _raise  # type: ignore[method-assign]
        with patch("backend.routers.retro._get_store", return_value=error_store):
            resp = client.get("/api/retro/summary")

        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# PUT /api/retro/{record_id}/action
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateAction:
    """记录用户操作"""

    def test_update_action(self, client):
        """更新操作成功"""
        records = [make_mock_record()]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/retro_test_001/action",
                json={"action": "buy"},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["user_action"] == "buy"

    def test_invalid_action_returns_422(self, client):
        """无效操作返回 422"""
        store = _MockRetroStore(records=[make_mock_record()])
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/retro_test_001/action",
                json={"action": "invalid_action"},
            )

        assert resp.status_code == 422

    def test_not_found_returns_404(self, client):
        """不存在的 record_id 返回 404"""
        store = _MockRetroStore(records=[])
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/nonexistent/action",
                json={"action": "hold"},
            )

        assert resp.status_code == 404

    @pytest.mark.parametrize("action", ["buy", "sell", "hold", "skip"])
    def test_all_valid_actions(self, client, action: str):
        """所有合法操作类型"""
        records = [make_mock_record()]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/retro_test_001/action",
                json={"action": action},
            )

        assert resp.status_code == 200
        assert resp.json()["data"]["user_action"] == action


# ═══════════════════════════════════════════════════════════════════════
# PUT /api/retro/{record_id}/outcome
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateOutcome:
    """更新实际结果"""

    def test_update_outcome(self, client):
        """更新结果成功"""
        records = [make_mock_record(consensus="Bullish")]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/retro_test_001/outcome",
                json={"return_pct": 3.5, "price": 12.94},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["actual_return_pct"] == 3.5
        assert data["actual_price"] == 12.94

    def test_not_found_returns_404(self, client):
        """不存在的记录返回 404"""
        store = _MockRetroStore(records=[])
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.put(
                "/api/retro/nonexistent/outcome",
                json={"return_pct": 1.0, "price": 13.0},
            )

        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# POST /api/retro/refresh
# ═══════════════════════════════════════════════════════════════════════


class TestRefreshPending:
    """批量刷新 pending 记录"""

    def test_refresh_empty(self, client):
        """无 pending 记录时刷新 0 条"""
        store = _MockRetroStore(records=[])
        with (
            patch("backend.routers.retro._get_store", return_value=store),
        ):
            resp = client.post("/api/retro/refresh")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_pending"] == 0
        assert data["updated"] == 0

    def test_refresh_pending_records(self, client, mock_collector):
        """刷新 pending 记录"""
        records = [
            make_mock_record(
                record_id="r1",
                stock_code="000001",
                price_at_debate=12.0,
                outcome="pending",
            ),
            make_mock_record(
                record_id="r2",
                stock_code="000002",
                price_at_debate=10.0,
                outcome="pending",
            ),
        ]
        # MockCollector 已有 000001 的行情
        store = _MockRetroStore(records=records)
        with (
            patch("backend.routers.retro._get_store", return_value=store),
            patch("src.data.collector.DataCollector", return_value=mock_collector),
        ):
            resp = client.post("/api/retro/refresh")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_pending"] == 2
        assert data["updated"] == 1  # mock_collector 只有 000001 的行情
        assert data["errors"] == 0

    def test_refresh_skip_no_price(self, client, mock_collector):
        """price_at_debate 为 None 时跳过"""
        records = [
            make_mock_record(
                record_id="r1",
                stock_code="000001",
                price_at_debate=None,
                outcome="pending",
            ),
        ]
        store = _MockRetroStore(records=records)
        with (
            patch("backend.routers.retro._get_store", return_value=store),
            patch("src.data.collector.DataCollector", return_value=mock_collector),
        ):
            resp = client.post("/api/retro/refresh")

        data = resp.json()["data"]
        assert data["total_pending"] == 1
        assert data["updated"] == 0  # price_at_debate=None → skip

    def test_refresh_error_returns_500(self, client):
        """整体异常时返回 500"""
        error_store = _MockRetroStore()

        async def _raise(**kw) -> object:
            raise RuntimeError("store 异常")

        error_store.list_records = _raise  # type: ignore[method-assign]
        with patch("backend.routers.retro._get_store", return_value=error_store):
            resp = client.post("/api/retro/refresh")

        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════
# DELETE /api/retro/{record_id}
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteRecord:
    """删除复盘记录"""

    def test_delete_success(self, client):
        """删除成功返回 deleted=True"""
        records = [make_mock_record()]
        store = _MockRetroStore(records=records)
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.delete("/api/retro/retro_test_001")

        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

    def test_not_found_returns_404(self, client):
        """不存在的记录返回 404"""
        store = _MockRetroStore(records=[])
        with patch("backend.routers.retro._get_store", return_value=store):
            resp = client.delete("/api/retro/nonexistent")

        assert resp.status_code == 404

    def test_error_returns_500(self, client):
        """store 异常时返回 500"""
        error_store = _MockRetroStore()

        async def _raise(name: str) -> object:
            raise RuntimeError("store 异常")

        error_store.delete = _raise  # type: ignore[method-assign]
        with patch("backend.routers.retro._get_store", return_value=error_store):
            resp = client.delete("/api/retro/r1")

        assert resp.status_code == 500

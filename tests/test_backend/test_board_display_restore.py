"""Historical display recovery must stay explicit and isolated from live collectors."""
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from backend.routers import market
from src.data.board_store import BoardSnapshotStore
from src.data.providers.eastmoney_boards import BoardQuoteSnapshot, BoardSnapshot


@pytest.mark.parametrize("mode", ["saved", "missing", "corrupt"])
async def test_board_display_restore(client, tmp_path, mode):
    store = BoardSnapshotStore(tmp_path / "boards.db")
    at = datetime(2026, 9, 28, 7, tzinfo=UTC)
    if mode != "missing":
        store.record_success(BoardSnapshot(kind="industry", fetched_at=at, quotes=(
            BoardQuoteSnapshot(code="BK0001", name="历史板块", change_pct=1.2,
                               fund_flow=100000000, as_of=at),
        )))
    if mode == "corrupt":
        import sqlite3
        with sqlite3.connect(store.path) as connection:
            connection.execute("UPDATE board_display_v1 SET digest='invalid'")
    frames = {"industry": pd.DataFrame(), "concept": pd.DataFrame()}
    with patch.object(market.board_snapshots, "store", store), patch.object(
        market, "_fetch_board_perf_sources", return_value=(frames, ["industry", "concept"])
    ):
        response = client.get("/api/market/sectors")
    if mode != "saved":
        assert response.status_code == 503
        return
    result = response.json()
    assert response.status_code == 200
    assert result["meta"]["status"] == "stale"
    assert result["meta"]["cached"] is True
    assert result["meta"]["failed_sources"] == ["industry", "concept"]
    assert result["data"][0]["as_of"] == at.isoformat().replace("+00:00", "Z")
    assert result["data"][0]["fund_flow"] == 1
    assert any(x["code"] == "BOARD_HISTORY_ONLY" for x in result["meta"]["limitations"])
    assert "BK0001" not in market.board_snapshots._cache

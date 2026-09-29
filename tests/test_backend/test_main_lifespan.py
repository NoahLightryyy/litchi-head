"""FastAPI 生命周期中的新闻采集门禁。"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_invalid_news_poll_interval_fails_startup_before_serving() -> None:
    with (
        patch.dict("os.environ", {"LITCHI_NEWS_POLL_SECONDS": "59"}),
        patch(
            "backend.config.setup_production_source",
            return_value="test-source",
        ),
        pytest.raises(ValueError, match="at least 60"),
        TestClient(app),
    ):
        pass


def test_board_warmup_is_started_and_joined_without_blocking_app():
    import asyncio
    stopped = []
    async def news_loop(*args, **kwargs):
        await asyncio.Event().wait()
    async def board_loop(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append("board")
    with (
        patch("backend.config.setup_production_source", return_value="test-source"),
        patch("src.data.news_runtime.get_news_evidence_runtime", return_value=None),
        patch("src.data.news_runtime.run_news_ingestion_loop", side_effect=news_loop),
        patch("src.data.board_runtime.configure_board_store") as configure,
        patch("src.data.board_runtime.warm_boards", side_effect=board_loop),
    ):
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            configure.assert_called_once()
            assert app.state.board_warmup_task is not None
        assert stopped == ["board"] and app.state.board_warmup_task is None

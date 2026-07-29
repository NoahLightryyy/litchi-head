"""FastAPI 生命周期中的新闻采集门禁。"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_invalid_news_poll_interval_fails_startup_before_serving() -> None:
    with (
        patch.dict("os.environ", {"LITCHI_NEWS_POLL_SECONDS": "59"}),
        pytest.raises(ValueError, match="at least 60"),
        TestClient(app),
    ):
        pass

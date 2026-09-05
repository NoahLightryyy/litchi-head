from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from src.data.providers.caixin_news import fetch_caixin_news, publication_time


@pytest.mark.parametrize(
    "value", [None, 0, -1, True, "1788569539", float("nan"), float("inf"), 10**20],
)
def test_invalid_time_stays_unknown(value):
    assert publication_time(value) is None


def test_original_timestamp_survives_adapter():
    response = httpx.Response(200, request=httpx.Request("GET", "https://cxdata.caixin.com"), json={
        "data": {"data": [{"summary": "原摘要", "title": "标题", "time": 1788569539, "url": "https://example.com"},
                          {"summary": "缺时间"}]}})
    with patch("src.data.providers.caixin_news.httpx.get", return_value=response):
        frame = fetch_caixin_news()
    assert frame.iloc[0]["date"] == "2026-09-05T08:52:19+08:00"
    assert frame.iloc[0]["summary"] == "原摘要"
    assert pd.isna(frame.iloc[1]["date"])

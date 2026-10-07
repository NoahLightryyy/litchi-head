"""Public news adapter parsing; no network required."""
from unittest.mock import Mock, patch

import pandas as pd

from src.data.providers.global_news import fetch_eastmoney_hot_news, publication_time


def test_eastmoney_normalizes_timestamp_and_validates_article_link():
    response = Mock()
    response.json.return_value = {"data": {"fastNewsList": [
        {"title": "<b>产业</b>&amp;政策", "showTime": "2026-01-02 12:30:00", "code": "123"},
        {"summary": "无日期新闻", "code": "javascript:bad"},
    ]}}
    with patch("src.data.providers.global_news.httpx.get", return_value=response) as get:
        rows = fetch_eastmoney_hot_news().to_dict("records")
    assert rows[0]["title"] == "产业&政策"
    assert rows[0]["date"] == "2026-01-02T12:30:00+08:00"
    assert rows[0]["url"] == "https://finance.eastmoney.com/a/123.html"
    assert pd.isna(rows[1]["date"])
    assert rows[1]["url"] == ""
    assert get.call_args.kwargs["timeout"] == 10.0
    assert "req_trace" in get.call_args.kwargs["params"]


def test_news_dates_are_not_replaced_with_fetch_time():
    assert publication_time("2099-01-01 10:00:00") is None
    assert publication_time("invalid") is None
    assert publication_time(None) is None


def test_extra_channels_parse_their_actual_fields():
    from src.data.providers.global_news import (
        fetch_cls_hot_news,
        fetch_futu_hot_news,
        fetch_ths_hot_news,
    )
    cases = [
        (fetch_cls_hot_news, {"errno": 0, "data": {"roll_data": [
            {"title": "财联新闻", "ctime": 1700000000, "id": 123}]}}),
        (fetch_futu_hot_news, {"data": {"data": {"news": [
            {"content": "富途新闻", "time": 1700000000, "detailUrl": "https://example.com"}]}}}),
        (fetch_ths_hot_news, {"data": {"list": [
            {"title": "同花顺新闻", "rtime": 1700000000, "url": "https://example.com"}]}}),
    ]
    for fetcher, payload in cases:
        with patch("src.data.providers.global_news._get_json", return_value=payload):
            rows = fetcher().to_dict("records")
        assert len(rows) == 1
        assert rows[0]["title"].endswith("新闻")
        assert rows[0]["date"].endswith("+08:00")

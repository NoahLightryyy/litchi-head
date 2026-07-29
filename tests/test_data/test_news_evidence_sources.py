"""东方财富与新浪新闻证据适配器契约测试。"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceStatus,
)
from src.data.providers.news import (
    EastmoneyNewsSource,
    SinaNewsSource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code="000001",
        stock_name="平安银行",
        start_at=datetime(2026, 7, 28, tzinfo=SHANGHAI),
        end_at=datetime(2026, 7, 29, 23, 59, tzinfo=SHANGHAI),
    )


def test_eastmoney_normalizes_relevant_news_and_filters_time_window() -> None:
    calls: list[int] = []

    def fetcher(*, keyword: str, page_index: int, page_size: int) -> dict[str, Any]:
        calls.append(page_index)
        assert keyword == "000001"
        assert page_size == 50
        return {
            "code": 0,
            "msg": "OK",
            "hitsTotal": 3,
            "result": {
                "cmsArticleWebOld": [
                    {
                        "code": "article-1",
                        "title": "平安银行发布半年度业绩快报",
                        "content": "平安银行经营保持稳健。",
                        "date": "2026-07-29 09:30:00",
                        "mediaName": "证券时报",
                        "url": "https://example.test/eastmoney/1",
                    },
                    {
                        "code": "article-2",
                        "title": "其他银行新闻",
                        "content": "与目标股票无关。",
                        "date": "2026-07-29 08:00:00",
                        "mediaName": "测试媒体",
                        "url": "https://example.test/eastmoney/2",
                    },
                    {
                        "code": "article-3",
                        "title": "平安银行历史新闻",
                        "content": "已经超出查询窗口。",
                        "date": "2026-07-01 08:00:00",
                        "mediaName": "证券时报",
                        "url": "https://example.test/eastmoney/3",
                    },
                ]
            },
        }

    result = EastmoneyNewsSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_DATA
    assert calls == [1]
    assert len(result.items) == 1
    item = result.items[0]
    assert item.external_id == "article-1"
    assert item.code == "000001"
    assert item.source_id == "eastmoney-stock-search"
    assert item.publisher == "证券时报"
    assert item.content == ""
    assert item.association_reason == "stock_name"
    assert len(item.content_hash) == 64


def test_eastmoney_uses_hits_total_to_return_explicit_empty() -> None:
    def fetcher(*, keyword: str, page_index: int, page_size: int) -> dict[str, Any]:
        return {
            "code": 0,
            "msg": "OK",
            "hitsTotal": 0,
            "result": {"cmsArticleWebOld": []},
        }

    result = EastmoneyNewsSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_EMPTY
    assert result.items == []


def test_eastmoney_exposes_malformed_payload_as_failure() -> None:
    def fetcher(*, keyword: str, page_index: int, page_size: int) -> dict[str, Any]:
        return {"code": 0, "result": {"cmsArticleWebOld": []}}

    result = EastmoneyNewsSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert result.error_message


def test_sina_matches_stock_name_and_transmits_metadata_only() -> None:
    def fetcher(*, page: int, page_size: int) -> dict[str, Any]:
        assert page == 1
        assert page_size == 100
        return {
            "result": {
                "status": {"code": 0},
                "data": {
                    "feed": {
                        "list": [
                            {
                                "id": "sina-1",
                                "create_time": "2026-07-29 10:00:00",
                                "rich_text": "平安银行发布半年度业绩快报，经营保持稳健。",
                                "docurl": "https://example.test/sina/1",
                            },
                            {
                                "id": "sina-2",
                                "create_time": "2026-07-29 10:01:00",
                                "rich_text": "国际市场快讯，与目标股票无关。",
                                "docurl": "https://example.test/sina/2",
                            },
                            {
                                "id": "sina-boundary",
                                "create_time": "2026-07-27 23:59:00",
                                "rich_text": "用于证明时间窗已完整扫描的边界快讯。",
                            },
                        ],
                        "page_info": {"totalNum": 3, "totalPage": 1},
                    }
                },
            }
        }

    result = SinaNewsSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_DATA
    assert len(result.items) == 1
    item = result.items[0]
    assert item.external_id == "sina-1"
    assert item.source_id == "sina-finance-feed"
    assert item.publisher == "新浪财经"
    assert item.content == ""
    assert item.association_reason == "stock_name"
    assert item.url == "https://example.test/sina/1"


def test_sina_returns_explicit_empty_when_feed_has_no_matching_stock() -> None:
    def fetcher(*, page: int, page_size: int) -> dict[str, Any]:
        return {
            "result": {
                "status": {"code": 0},
                "data": {
                    "feed": {
                        "list": [
                            {
                                "id": "sina-2",
                                "create_time": "2026-07-29 10:01:00",
                                "rich_text": "国际市场快讯。",
                            },
                            {
                                "id": "sina-boundary",
                                "create_time": "2026-07-27 23:59:00",
                                "rich_text": "时间窗边界快讯。",
                            }
                        ],
                        "page_info": {"totalNum": 2, "totalPage": 1},
                    }
                },
            }
        }

    result = SinaNewsSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_EMPTY
    assert result.items == []


def test_sina_marks_result_stale_when_feed_cannot_cover_requested_window() -> None:
    def fetcher(*, page: int, page_size: int) -> dict[str, Any]:
        return {
            "result": {
                "status": {"code": 0},
                "data": {
                    "feed": {
                        "list": [
                            {
                                "id": "sina-recent",
                                "create_time": "2026-07-29 10:01:00",
                                "rich_text": "国际市场快讯。",
                            }
                        ],
                        "page_info": {
                            "totalNum": 900,
                            "totalPage": 9,
                            "page": 1,
                        },
                    }
                },
            }
        }

    result = SinaNewsSource(fetcher=fetcher, max_pages=1).fetch(_request())

    assert result.status is SourceStatus.STALE
    assert result.error_code == "time_window_not_fully_covered"
    assert result.error_message


def test_news_sources_reject_non_news_capability_without_calling_upstream() -> None:
    calls = 0

    def fetcher(*, keyword: str, page_index: int, page_size: int) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    request = EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code="000001",
    )
    result = EastmoneyNewsSource(fetcher=fetcher).fetch(request)

    assert result.status is SourceStatus.UNSUPPORTED
    assert calls == 0

"""Display news must not inherit all-or-nothing investment evidence policy."""

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from backend.news_display import NewsDisplayService, collect_display

NOW = datetime(2026, 10, 1, 12, tzinfo=ZoneInfo("Asia/Shanghai"))


def run(handler):
    async def request():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await collect_display("300199", 30, client=client, now=NOW)

    return asyncio.run(request())


def handler_for(rows, *, broken_cninfo=False, broken_news=False):
    def handler(request):
        if "eastmoney" in request.url.host:
            if broken_news:
                return httpx.Response(502)
            return httpx.Response(
                200,
                text="callback("
                + json.dumps(
                    {
                        "code": 0,
                        "hitsTotal": len(rows),
                        "result": {"cmsArticleWebOld": rows},
                    }
                )
                + ")",
            )
        if broken_cninfo:
            return httpx.Response(502)
        if "szse_stock" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "stockList": [
                        {"code": "300199", "orgId": "990001", "zwjc": "翰宇药业"},
                    ]
                },
            )
        return httpx.Response(200, json={"totalAnnouncement": 0, "announcements": []})

    return handler


def row(title="翰宇药业（300199）发布报告", **extra):
    return {
        "title": title,
        "content": "",
        "date": "2026-09-30 14:05:00",
        "url": "https://finance.eastmoney.com/a/123.html",
        "mediaName": "媒体",
        "code": "a1",
        **extra,
    }


def test_valid_news_survives_announcement_failure():
    result = run(handler_for([row()], broken_cninfo=True))
    assert result.status == "partial"
    assert len(result.items) == 1
    assert result.items[0].published_at == "2026-09-30T14:05:00+08:00"
    assert result.items[0].kind == "report"
    assert result.sources[1].status == "failed"


def test_failure_is_not_empty():
    assert run(handler_for([], broken_cninfo=True, broken_news=True)).status == "failed"
    assert run(handler_for([])).status == "empty"


def test_clean_identity_time_and_safe_url():
    result = run(
        handler_for(
            [
                row(title="nan"),
                row(title="价格为13001990元", content=""),
                row(title="其他公司新闻", content="行业文章提及翰宇药业"),
                row(date="2027-01-01 10:00:00"),
                row(url="javascript:alert(1)"),
            ]
        )
    )
    assert len(result.items) == 1
    assert result.items[0].kind == "mention"
    assert result.status == "partial"


def test_duplicate_titles_keep_provenance_and_unknown_time_not_filled():
    result = run(
        handler_for(
            [
                row(date=None),
                row(date=None, code="a2", mediaName="转载媒体"),
            ]
        )
    )
    assert len(result.items) == 1
    assert result.items[0].published_at is None
    assert len(result.items[0].provenance) == 2
    assert result.status == "partial"


def test_cninfo_identity_mismatch_is_rejected():
    base = handler_for([])

    def handler(request):
        if "hisAnnouncement" not in request.url.path:
            return base(request)
        return httpx.Response(
            200,
            json={
                "totalAnnouncement": 1,
                "announcements": [
                    {
                        "secCode": "000001",
                        "secName": "其他公司",
                        "orgId": "990001",
                        "announcementId": "a1",
                        "announcementTitle": "错误公司公告",
                        "announcementTime": 1790697600000,
                    }
                ],
            },
        )

    result = run(handler)
    assert not result.items
    assert result.status == "failed"


def test_singleflight_and_cache_keep_fetched_time():
    async def check():
        calls = 0

        async def collect(symbol, days):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler_for([row()]))
            ) as client:
                return await collect_display(symbol, days, client=client, now=NOW)

        service = NewsDisplayService(collector=collect)
        a, b = await asyncio.gather(service.get("300199", 30), service.get("300199", 30))
        c = await service.get("300199", 30)
        assert calls == 1
        assert c.cached and c.fetched_at == a.fetched_at == b.fetched_at

    asyncio.run(check())


def test_api_contract_status_and_parameters(client, monkeypatch):
    from backend.routers import news

    result = run(handler_for([], broken_cninfo=True, broken_news=True))

    async def get(*args):
        return result

    monkeypatch.setattr(news.service, "get", get)
    response = client.get("/api/stocks/300199/news-display")
    assert response.status_code == 503
    assert response.json()["status"] == "failed"
    assert client.get("/api/stocks/300199/news-display?days=30").status_code == 503
    assert client.get("/api/stocks/invalid/news-display").status_code == 422
    assert client.get("/api/stocks/300199/news-display?days=365").status_code == 422


def test_timeout_cancels_upstream_and_preserves_other_source(monkeypatch):
    from backend import news_display

    monkeypatch.setattr(news_display, "SOURCE_BUDGET", 0.01)
    completed = []

    async def check():
        base = handler_for([])

        async def handler(request):
            if "eastmoney" in request.url.host:
                try:
                    await asyncio.sleep(1)
                finally:
                    completed.append("cancelled")
            return base(request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await collect_display("300199", 30, client=client, now=NOW)
        assert result.status == "failed"
        assert result.sources[0].error_code == "SOURCE_TIMEOUT"
        assert result.sources[1].status == "empty"

    asyncio.run(check())
    assert completed == ["cancelled"]


def test_success_announcement_has_date_precision():
    base = handler_for([], broken_news=True)

    def handler(request):
        if "hisAnnouncement" not in request.url.path:
            return base(request)
        return httpx.Response(
            200,
            json={
                "totalAnnouncement": 1,
                "announcements": [
                    {
                        "secCode": "300199",
                        "secName": "翰宇药业",
                        "orgId": "990001",
                        "announcementId": "a1",
                        "announcementTitle": "关于公司事项的公告",
                        "announcementTime": int(
                            datetime(2026, 9, 30, tzinfo=NOW.tzinfo).timestamp() * 1000
                        ),
                    }
                ],
            },
        )

    result = run(handler)
    assert result.status == "partial"
    assert result.items[0].kind == "announcement"
    assert result.items[0].published_at == "2026-09-30"
    assert result.items[0].time_precision == "date"

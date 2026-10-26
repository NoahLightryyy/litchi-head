"""Relevant display retrieval must work without a subject-specific evidence package."""

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from backend.related_research import make_document, rank_documents, retrieve, search_news
from backend.related_research_contract import RelatedKeyword, RelatedSourceStatus
from backend.routers import related_research as routes
from src.data.news_archive import ArchivedArticle, NewsArchive

NOW = datetime(2026, 10, 26, 18, tzinfo=UTC)
PROFILE = RelatedSourceStatus(source="company_profile", status="not_requested")
KEYWORDS = [
    RelatedKeyword(term="半导体", origin="expanded"),
    RelatedKeyword(term="560780", origin="code"),
]


class NoPolicies:
    @property
    def root(self):
        raise OSError("test policy unavailable")


def article(identity, title, *, url=None, date="2026-10-25T12:00:00+00:00", content=""):
    return ArchivedArticle(
        id=identity,
        channel="sina",
        title=title,
        content=content,
        url=url or f"https://finance.sina.com.cn/{identity}.html",
        date=date,
        source="新浪财经",
    )


def test_etf_keyword_retrieval_without_whitelisted_package(tmp_path):
    store = NewsArchive(tmp_path / "news.db")
    store.store(
        [
            article("policy", "工信部发布半导体产业支持政策"),
            article("fund", "半导体设备ETF广发560780成交活跃"),
            article("unrelated", "白酒销售回暖"),
        ]
    )
    result = retrieve("etf", "560780", "半导体设备ETF广发", "", "", PROFILE, store=store, now=NOW)
    assert result.status == "ready"
    assert {item.relevance for item in result.data} == {"direct", "topic"}
    assert "news:unrelated" not in {item.id for item in result.data}
    assert any(item.category == "policy" for item in result.data)
    assert any(item.source == "policy_archive" for item in result.data)
    assert not hasattr(result, "claims") and not hasattr(result, "holdings")
    assert result.subject_id == "560780"


def test_query_override_dedup_dates_and_numeric_boundaries(tmp_path):
    store = NewsArchive(tmp_path / "news.db")
    store.store(
        [
            article("wrong_code", "成交15607809万元"),
            article("code", "560780公布公告"),
            article("a", "半导体设备扩产", url="https://example.com/shared"),
            article("b", "半导体设备扩产", url="https://example.com/repost"),
            article("future", "半导体政策未来消息", date="2027-01-01T00:00:00+00:00"),
            article("old", "半导体政策旧消息", date="2020-01-01T00:00:00+00:00"),
            article("unsafe", "半导体资料", url="javascript:alert(1)"),
        ]
    )
    code_rows = search_news(store, [KEYWORDS[1]], "560780", "", NOW)
    assert [item.id for item in code_rows] == ["news:code"]
    result = retrieve(
        "etf", "560780", "半导体设备ETF广发", "", "半导体设备", PROFILE, store=store, now=NOW
    )
    assert all(item.origin == "user" for item in result.keywords)
    assert [item.id for item in result.data if item.source == "news_archive"] in [
        ["news:a"],
        ["news:b"],
    ]
    assert all(item.published_at != NOW.isoformat() for item in result.data)


def test_partial_source_failure_retains_results_and_empty_is_honest(tmp_path):
    store = NewsArchive(tmp_path / "news.db")
    store.store([article("a", "半导体政策报道")])
    result = retrieve(
        "etf",
        "560780",
        "半导体设备ETF广发",
        "",
        "",
        PROFILE,
        store=store,
        repository=NoPolicies(),
        now=NOW,
    )
    assert result.status == "partial" and result.data
    assert result.sources[-1].status == "unavailable"
    empty = retrieve("stock", "000001", "", "", "不存在的检索主题", PROFILE, store=store, now=NOW)
    assert empty.status == "empty" and empty.data == []


def test_total_source_failure_is_not_empty(tmp_path):
    class BrokenNews:
        def connect(self):
            raise OSError("test db unavailable")

    result = retrieve(
        "stock",
        "000001",
        "平安银行",
        "",
        "",
        PROFILE,
        store=BrokenNews(),
        repository=NoPolicies(),
        now=NOW,
    )
    assert result.status == "unavailable" and not result.data


def test_html_safe_excerpt_and_policy_slot():
    def document(identity, title):
        return make_document(
            identity=identity,
            title=title,
            content="<p>半导体业务资料</p>",
            url=f"https://example.com/{identity}",
            publisher="来源",
            stamp="2026-10-20",
            source="news_archive",
            keywords=KEYWORDS,
            code="560780",
            name="",
            now=NOW,
        )

    items = [document(str(i), f"560780半导体行情第{i}条") for i in range(15)]
    policy = document("policy", "半导体支持政策")
    result = rank_documents([*items, policy])
    assert len(result) == 12 and policy in result
    assert all("<p>" not in item.excerpt for item in result)
    assert all(item.relevance == "direct" for item in result if item.id != "policy")


@pytest.mark.asyncio
async def test_http_identity_validation_and_read_only_contract(monkeypatch, tmp_path):
    async def read(kind, code, name, query):
        return retrieve(
            kind, code, name, "", query, PROFILE, store=NewsArchive(tmp_path / "http.db"), now=NOW
        )

    monkeypatch.setattr(routes, "related_research", read)
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get(
            "/api/research/related",
            params={"kind": "etf", "code": "560780", "name": "半导体设备ETF广发"},
        )
        assert r.status_code == 200 and r.json()["subject_id"] == "560780"
        for kind, code in [("etf", "BK0917"), ("stock", "../data"), ("sector", "560780")]:
            assert (
                await client.get("/api/research/related", params={"kind": kind, "code": code})
            ).status_code == 422
        assert (await client.post("/api/research/related")).status_code == 405
        assert "/api/research/related" in (await client.get("/openapi.json")).json()["paths"]

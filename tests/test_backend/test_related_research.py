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


def test_generic_corporate_notices_are_not_policy_and_recency_wins():
    def document(identity, title, stamp, content=""):
        return make_document(
            identity=identity,
            title=title,
            content=content,
            url=f"https://example.com/{identity}",
            publisher="来源",
            stamp=stamp,
            source="news_archive",
            keywords=KEYWORDS,
            code="560780",
            name="",
            now=NOW,
        )

    dividend = document("dividend", "半导体ETF年度分红通知", "2026-10-25")
    meeting = document("meeting", "半导体设备公司股东大会的通知", "2026-10-25")
    assert dividend.category == meeting.category == "report"
    old = document("old", "560780半导体报道", "2026-07-01")
    new = document("new", "560780报道", "2026-10-01")
    assert rank_documents([old, new])[0].id == "new"
    roundup = document("roundup", "监管新规", "2026-10-25", "其他资料。" * 80 + "半导体行业走势")
    assert roundup.category == "report"
    adjacent = document(
        "adjacent", "全球要闻", "2026-10-25", "1、央行调整货币政策。2、半导体涨价。"
    )
    forecast = document("forecast", "财政部长预计半导体市场增长", "2026-10-25")
    assert adjacent.category == forecast.category == "report"
    headline = document("headline", "半导体出口管制新规发布", "2026-10-25")
    flash = document("flash", "【半导体出口管制新规发布】半导体消息全文。", "2026-10-25")
    assert flash.title == headline.title
    assert len(rank_documents([headline, flash])) == 1


@pytest.mark.asyncio
async def test_manual_query_validation_and_profile_name_echo(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock

    import backend.related_research as service

    monkeypatch.setattr(service.company_news_service, "get", AsyncMock(side_effect=TimeoutError()))

    async def profile(code):
        return "测试银行股份有限公司", "主营业务：商业银行"

    monkeypatch.setattr(service, "company_context", profile)
    original = service.retrieve
    store = NewsArchive(tmp_path / "profile.db")
    monkeypatch.setattr(service, "retrieve", lambda *args: original(*args, store=store, now=NOW))
    result = await service.related_research("stock", "000001", "000001", "")
    assert result.subject_name == "000001"
    assert any(term.term == "银行" for term in result.keywords)
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        bad = await client.get(
            "/api/research/related", params={"kind": "etf", "code": "560780", "q": ", ;"}
        )
        assert bad.status_code == 422 and "关键词" in bad.json()["detail"]


def test_existing_company_news_is_recent_input_not_archived_fact(tmp_path):
    from backend.news_display import DisplayNewsItem, NewsDisplay, NewsOrigin
    from backend.related_research import merge_company_news

    result = retrieve(
        "stock",
        "300916",
        "朗特智能",
        "",
        "",
        PROFILE,
        store=NewsArchive(tmp_path / "news.db"),
        now=NOW,
    )
    display = NewsDisplay(
        symbol="300916",
        status="ready",
        start_date="2026-07-28",
        end_date="2026-10-26",
        fetched_at=NOW,
        sources=[],
        items=[
            DisplayNewsItem(
                id="recent",
                title="朗特智能拟收购相关公司",
                kind="report",
                published_at="2026-10-26T12:00:00+08:00",
                time_precision="second",
                association="title_match",
                provenance=[
                    NewsOrigin(
                        source="eastmoney", publisher="证券时报", url="https://example.com/recent"
                    )
                ],
            ),
            DisplayNewsItem(
                id="unknown-date",
                title="朗特智能旧消息",
                kind="report",
                published_at=None,
                time_precision="unknown",
                association="title_match",
                provenance=[],
            ),
        ],
    )
    merged = merge_company_news(result, display)
    assert len(merged.data) == 1
    assert merged.data[0].source == "company_news"
    assert merged.data[0].published_at == "2026-10-26T12:00:00+08:00"
    assert merged.data[0].excerpt == merged.data[0].title
    assert "仅标题" in merged.data[0].reason
    display.status = "partial"
    assert merge_company_news(result, display).status == "partial"
    display.symbol = "000001"
    with pytest.raises(ValueError):
        merge_company_news(result, display)


@pytest.mark.asyncio
async def test_company_failure_keeps_archive_without_model_call(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from backend import related_research as service

    base = retrieve(
        "stock",
        "300916",
        "朗特智能",
        "",
        "朗特智能",
        PROFILE,
        store=NewsArchive(tmp_path / "news.db"),
        now=NOW,
    )
    monkeypatch.setattr(service._runner, "run", AsyncMock(return_value=base))
    getter = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(service.company_news_service, "get", getter)
    result = await service.related_research("stock", "300916", "朗特智能", "朗特智能")
    assert result.data == base.data and result.sources[-1].source == "company_news"
    assert result.sources[-1].status == "unavailable"
    await service.related_research("etf", "560780", "半导体ETF", "")
    assert getter.await_count == 1


@pytest.mark.asyncio
async def test_archive_timeout_does_not_block_available_company_news(monkeypatch):
    from unittest.mock import AsyncMock

    from backend import related_research as service
    from backend.news_display import DisplayNewsItem, NewsDisplay, NewsOrigin

    monkeypatch.setattr(service._runner, "run", AsyncMock(side_effect=TimeoutError()))
    news = NewsDisplay(
        symbol="300916",
        status="ready",
        start_date="2026-07-28",
        end_date="2026-10-26",
        fetched_at=NOW,
        sources=[],
        items=[
            DisplayNewsItem(
                id="recent",
                title="朗特智能披露业务进展",
                kind="report",
                published_at="2026-10-26T12:00:00+08:00",
                time_precision="second",
                association="title_match",
                provenance=[
                    NewsOrigin(
                        source="eastmoney", publisher="证券时报", url="https://example.com/recent"
                    )
                ],
            ),
        ],
    )
    monkeypatch.setattr(service.company_news_service, "get", AsyncMock(return_value=news))
    result = await service.related_research("stock", "300916", "朗特智能", "朗特智能")
    assert result.status == "partial" and result.data[0].source == "company_news"

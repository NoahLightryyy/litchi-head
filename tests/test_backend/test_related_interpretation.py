"""Related-material interpretation is explicit, cited, and reusable without generation."""

import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import related_interpretation as service
from backend.related_interpretation_contract import (
    RelatedEvent,
    RelatedInference,
    RelatedInterpretationDraft,
    RelatedInterpretationGeneration,
    RelatedInterpretationRequest,
    RelatedInterpretationResult,
    RelatedSynthesis,
)
from backend.related_research_contract import RelatedResearchResult
from backend.routers import related_interpretation as routes

NOW = datetime(2026, 10, 26, 21, tzinfo=UTC)
PARAMS = {"kind": "stock", "code": "688648", "name": "中邮科技"}
URL = "/api/research/related/interpretation"


def snapshot(*, kind="stock", code="688648", query="", two_sources=False, partial=False):
    documents = [
        {
            "id": "news:1",
            "title": "物流网建设方案发布",
            "url": "https://example.com/policy",
            "publisher": "测试报道",
            "published_at": "2026-08-28T02:14:47+00:00",
            "excerpt": "报道表示到2030年物流网建设取得明显成效。",
            "source": "news_archive",
            "category": "policy",
            "relevance": "topic",
            "matched_keywords": ["物流"],
            "reason": "主题关键词相关：物流",
        }
    ]
    if two_sources:
        documents.append(
            {
                **documents[0],
                "id": "news:2",
                "title": "航空运行标准研讨会",
                "excerpt": "航空运行标准研讨会召开。",
                "url": "https://example.com/other",
            }
        )
    return RelatedResearchResult.model_validate(
        {
            "subject_kind": kind,
            "subject_id": code,
            "subject_name": "中邮科技",
            "query": query,
            "status": "partial" if partial else "ready",
            "keywords": [{"term": "物流", "origin": "business"}],
            "data": documents,
            "sources": [{"source": "news_archive", "status": "ok"}],
            "searched_at": NOW,
            "limitations": ["已入库材料，不代表全网"],
        }
    )


def draft(*, two_sources=False):
    inference = RelatedInference(text="可能先影响预期，需观察资金、招标及订单才能判断经营兑现。")
    return RelatedInterpretationDraft(
        overview="物流网方案与物流主题有关，尚不能认定本公司已取得订单。",
        synthesis=RelatedSynthesis(
            what_happened="物流网方案提出建设目标。",
            price_impact=inference.model_dump(),
            industry_impact=inference.model_dump(),
            duration=inference.model_dump(),
            market_reaction=inference.model_dump(),
            business_realization=inference.model_dump(),
            watchpoints=["看后续订单能否落地"],
            source_ids=["news:1"],
        ),
        events=[
            RelatedEvent(
                title="物流网建设方案",
                source_ids=["news:1"],
                summary={
                    "text": "报道提出到2030年的物流网建设目标。",
                    "quotes": [
                        {
                            "source_id": "news:1",
                            "field": "excerpt",
                            "quote": "到2030年物流网建设取得明显成效",
                        }
                    ],
                },
                impact_direction="unclear",
                impact_path=inference,
                affected_scope=inference,
                duration=inference,
                market_reaction=inference,
                business_realization=inference,
                subject_relation=inference,
                watchpoints=["观察招标公告与公司订单披露"],
            )
        ],
        excluded_sources=[{"source_id": "news:2", "reason": "航空运行与本标的仅宽泛运输词匹配"}]
        if two_sources
        else [],
        limitations=["主题命中不证明已经受益"],
    )


def saved_result(*, source=None, analysis=None):
    source = source or snapshot()
    analysis = analysis or draft()
    return RelatedInterpretationResult(
        subject_kind=source.subject_kind,
        subject_id=source.subject_id,
        subject_name=source.subject_name,
        query=source.query,
        generated_at=NOW,
        model="test-model",
        prompt_version=service.PROMPT_VERSION,
        status="interpreted" if analysis.events else "no_relevant_events",
        snapshot_sha256=service.snapshot_digest(source),
        snapshot=source,
        analysis=analysis,
    )


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service, "store", service.RelatedInterpretationStore(tmp_path / "results.db")
    )
    service._busy.clear()
    routes.limiter.reset()
    yield
    service._busy.clear()


@pytest.fixture
def client(isolated):
    app = FastAPI()
    app.state.limiter = routes.limiter
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client


def test_request_reuses_success_by_default_and_forbids_client_materials():
    assert RelatedInterpretationRequest().refresh is False
    assert RelatedInterpretationRequest(refresh=True).refresh is True
    with pytest.raises(ValidationError):
        RelatedInterpretationRequest.model_validate({"articles": ["client text"]})


def test_contract_allows_excluding_all_sources_without_inventing_an_event():
    result = RelatedInterpretationDraft(
        overview="现有运输材料与本标的关联较弱。",
        events=[],
        excluded_sources=[{"source_id": "news:1", "reason": "只有宽泛运输词匹配"}],
        limitations=["没有直接业务关联证据"],
    )
    assert result.events == []
    with pytest.raises(ValidationError):
        RelatedInference.model_validate({"text": "或影响需求", "basis": "reported"})


def test_get_is_free_post_reuses_success_and_refresh_is_explicit(client, monkeypatch):
    fetch = AsyncMock(return_value=snapshot(two_sources=True, partial=True))
    invoke = AsyncMock(return_value=draft(two_sources=True))
    monkeypatch.setattr(service, "related_research", fetch)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    assert client.get(URL, params=PARAMS).json() is None
    assert not service.store.path.exists()
    fetch.assert_not_called()
    invoke.assert_not_called()
    first = client.post(URL, params=PARAMS)
    assert first.status_code == 200
    body = first.json()
    assert body["snapshot"]["status"] == "partial"
    assert body["review_status"] == "ai_unreviewed"
    assert body["analysis"]["events"][0]["summary"]["basis"] == "reported"
    assert body["analysis"]["events"][0]["duration"]["basis"] == "inference"
    assert client.get(URL, params=PARAMS).json() == body
    assert client.post(URL, params=PARAMS, json={"refresh": False}).json() == body
    assert fetch.await_count == invoke.await_count == 1
    assert client.post(URL, params=PARAMS, json={"refresh": True}).status_code == 200
    assert fetch.await_count == invoke.await_count == 2
    call = invoke.call_args.kwargs
    assert call["llm_config"].reasoning_effort is None
    assert call["llm_config"].model == service.DEFAULT_MODEL
    assert "到2030年物流网建设取得明显成效" in call["prompt"]
    assert call["output_model"] is RelatedInterpretationGeneration


@pytest.mark.parametrize(
    "kind,code",
    [("stock", "688648"), ("etf", "560780"), ("sector", "BK0917"), ("sector", "sina:hangye_hy012")],
)
def test_each_subject_kind_uses_its_own_server_retrieval(client, monkeypatch, kind, code):
    fetch = AsyncMock(return_value=snapshot(kind=kind, code=code, query="铜"))
    monkeypatch.setattr(service, "related_research", fetch)
    monkeypatch.setattr(service.llm_service, "invoke_structured", AsyncMock(return_value=draft()))
    response = client.post(URL, params={"kind": kind, "code": code, "name": "测试", "q": " 铜 "})
    assert response.status_code == 200
    fetch.assert_awaited_once_with(kind, code, "测试", "铜")
    assert service.get_saved(kind, code, "铜") is not None
    assert service.get_saved(kind, code) is None


@pytest.mark.parametrize(
    "params",
    [
        {"kind": "stock", "code": "BK0917"},
        {"kind": "etf", "code": "../data"},
        {"kind": "sector", "code": "560780"},
        {**PARAMS, "q": ", ;"},
        {**PARAMS, "q": "a"},
    ],
)
def test_invalid_identity_or_keywords_never_calls_model(client, monkeypatch, params):
    invoke = AsyncMock()
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    assert client.post(URL, params=params).status_code == 422
    assert client.get(URL, params=params).status_code == 422
    invoke.assert_not_called()


def test_client_cannot_supply_documents_or_model_prompt(client, monkeypatch):
    invoke = AsyncMock()
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    response = client.post(
        URL, params=PARAMS, json={"refresh": True, "snapshot": "client materials"}
    )
    assert response.status_code == 422
    invoke.assert_not_called()


@pytest.mark.parametrize("broken", ["missing", "double", "foreign", "quote", "outside"])
def test_every_document_is_assigned_once_and_quotes_are_actual_substrings(broken):
    source, analysis = snapshot(two_sources=True), draft(two_sources=True)
    if broken == "missing":
        analysis.excluded_sources = []
    elif broken == "double":
        analysis.events[0].source_ids.append("news:2")
    elif broken == "foreign":
        analysis.events[0].source_ids.append("fake")
    elif broken == "quote":
        analysis.events[0].summary.quotes[0].quote = "到2030年给中邮科技新增十亿订单"
    else:
        analysis.events[0].summary.quotes[0].source_id = "news:2"
    with pytest.raises(ValueError):
        service.validate_interpretation(analysis, source)


def test_title_only_and_archived_summary_are_usable_without_fulltext_claims(client, monkeypatch):
    source = snapshot()
    source.data[0].source = "policy_archive"
    source.data[0].excerpt = source.data[0].title
    analysis = draft()
    analysis.events[0].summary.quotes[0].field = "title"
    analysis.events[0].summary.quotes[0].quote = source.data[0].title
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=source))
    monkeypatch.setattr(service.llm_service, "invoke_structured", AsyncMock(return_value=analysis))
    assert client.post(URL, params=PARAMS).status_code == 200
    formatted = service.format_saved_interpretation("stock", "688648")
    assert '"text_basis": "archived_summary"' in formatted
    assert "标题材料可作有限解读" in service.SYSTEM_PROMPT
    assert "不能说已读政策原文" in service.SYSTEM_PROMPT


def test_all_weak_documents_can_be_excluded(client, monkeypatch):
    analysis = RelatedInterpretationDraft(
        overview="没有足以展开产业联系的材料",
        events=[],
        excluded_sources=[{"source_id": "news:1", "reason": "只有宽泛主题命中"}],
        limitations=["没有本标的直接联系材料"],
    )
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=snapshot()))
    monkeypatch.setattr(service.llm_service, "invoke_structured", AsyncMock(return_value=analysis))
    result = client.post(URL, params=PARAMS)
    assert result.status_code == 200
    assert result.json()["status"] == "no_relevant_events"


@pytest.mark.parametrize("failure", ["empty", "wrong_identity", "source_error"])
def test_no_usable_snapshot_never_spends_model_call(client, monkeypatch, failure):
    source = snapshot()
    if failure == "empty":
        source.data = []
        source.status = "empty"
    elif failure == "wrong_identity":
        source.subject_id = "600519"
    fetch = (
        AsyncMock(side_effect=OSError("test unavailable"))
        if failure == "source_error"
        else AsyncMock(return_value=source)
    )
    invoke = AsyncMock()
    monkeypatch.setattr(service, "related_research", fetch)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    result = client.post(URL, params=PARAMS)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "RELATED_INTERPRETATION_SOURCE_UNAVAILABLE"
    invoke.assert_not_called()


@pytest.mark.parametrize("failure,status", [(TimeoutError(), 504), (ValueError("failed"), 502)])
def test_failed_refresh_retains_saved_success_and_does_not_retry(
    client, monkeypatch, failure, status
):
    prior = saved_result()
    service.store.save(prior)
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=snapshot()))
    invoke = AsyncMock(side_effect=failure)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    response = client.post(URL, params=PARAMS, json={"refresh": True})
    assert response.status_code == status
    assert service.get_saved("stock", "688648") == prior
    invoke.assert_awaited_once()
    assert service._busy == set()


def test_invalid_model_quote_is_replaced_with_same_source_fragment(client, monkeypatch, caplog):
    prior = saved_result()
    service.store.save(prior)
    analysis = draft()
    analysis.events[0].summary.quotes[0].quote = "虚构的原文"
    source = snapshot()
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=source))
    invoke = AsyncMock(return_value=analysis)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    response = client.post(URL, params=PARAMS, json={"refresh": True})
    assert response.status_code == 200
    result = service.get_saved("stock", "688648")
    assert result is not None and result != prior
    summary = result.analysis.events[0].summary
    assert summary.text == analysis.events[0].summary.text
    assert summary.basis == "reported"
    assert summary.quotes[0].quote == source.data[0].excerpt
    assert summary.quotes[0].source_id == "news:1"
    assert service.SOURCE_QUOTE_NOTE in result.analysis.limitations
    assert "code=688648 count=1" in caplog.text
    assert "虚构的原文" not in caplog.text
    assert analysis.events[0].summary.quotes[0].quote == "虚构的原文"
    invoke.assert_awaited_once()


@pytest.mark.parametrize("invalid", ["foreign", "outside", "duplicate", "empty"])
def test_quote_recovery_never_repairs_invalid_source_ownership(
    client,
    monkeypatch,
    invalid,
    caplog,
):
    prior = saved_result()
    service.store.save(prior)
    analysis = draft(two_sources=True)
    analysis.events[0].summary.quotes[0].quote = "文字复制错误"
    if invalid == "foreign":
        analysis.events[0].summary.quotes[0].source_id = "unknown"
    elif invalid == "outside":
        analysis.events[0].summary.quotes[0].source_id = "news:2"
    elif invalid == "duplicate":
        analysis.events[0].source_ids.append("news:2")
    else:
        analysis.events[0].summary.quotes[0].source_id = ""
    monkeypatch.setattr(
        service, "related_research", AsyncMock(return_value=snapshot(two_sources=True))
    )
    monkeypatch.setattr(service.llm_service, "invoke_structured", AsyncMock(return_value=analysis))
    response = client.post(URL, params=PARAMS, json={"refresh": True})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "RELATED_INTERPRETATION_INVALID_OUTPUT"
    assert service.get_saved("stock", "688648") == prior
    assert "source quotes restored" not in caplog.text


def test_quote_recovery_preserves_correct_quotes_and_uses_real_title_for_empty_excerpt():
    source, analysis = snapshot(), draft()
    restored = service.restore_source_quotes(analysis, source)
    assert restored == analysis
    source.data[0].excerpt = ""
    restored = service.restore_source_quotes(analysis, source)
    quote = restored.events[0].summary.quotes[0]
    assert quote.field == "title"
    assert quote.quote == source.data[0].title
    service.validate_interpretation(restored, source)


def test_quote_recovery_caps_fragment_and_preserves_all_existing_limitations():
    source, analysis = snapshot(), draft()
    source.data[0].excerpt = "物流建设原始片段。" * 50
    analysis.limitations = [f"已有缺口{index}" for index in range(8)]
    restored = service.restore_source_quotes(analysis, source)
    quote = restored.events[0].summary.quotes[0]
    assert quote.quote == source.data[0].excerpt[:300]
    assert len(quote.quote) == 300
    assert len(restored.limitations) == 8
    assert all(gap in "；".join(restored.limitations) for gap in analysis.limitations)
    assert service.SOURCE_QUOTE_NOTE in restored.limitations[-1]
    service.validate_interpretation(restored, source)
    RelatedInterpretationDraft.model_validate(restored.model_dump())


@pytest.mark.parametrize("corruption", ["body", "snapshot", "identity", "quote"])
def test_reopen_checks_entire_result_snapshot_identity_and_quotes(isolated, corruption):
    prior = saved_result()
    service.store.save(prior)
    reopened = service.RelatedInterpretationStore(service.store.path)
    assert reopened.get("stock", "688648") == prior
    body = prior.model_dump(mode="json")
    if corruption == "body":
        body["analysis"]["overview"] = "tampered"
    elif corruption == "snapshot":
        body["snapshot"]["data"][0]["excerpt"] += "篡改"
    elif corruption == "identity":
        body["subject_id"] = body["snapshot"]["subject_id"] = "600519"
        body["snapshot_sha256"] = service.snapshot_digest(
            RelatedResearchResult.model_validate(body["snapshot"])
        )
    else:
        body["analysis"]["events"][0]["summary"]["quotes"][0]["quote"] = "不存在的引用"
    serialized = json.dumps(body, ensure_ascii=False)
    with sqlite3.connect(service.store.path) as connection:
        if corruption == "body":
            connection.execute("UPDATE related_interpretation SET body=?", (serialized,))
        else:
            connection.execute(
                "UPDATE related_interpretation SET body=?, digest=?",
                (serialized, hashlib.sha256(serialized.encode()).hexdigest()),
            )
    with pytest.raises(ValueError):
        reopened.get("stock", "688648")


def test_formatter_is_read_only_same_key_and_labels_historical_inferences(isolated, monkeypatch):
    fetch, invoke = AsyncMock(), AsyncMock()
    monkeypatch.setattr(service, "related_research", fetch)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    assert service.format_saved_interpretation("stock", "688648") == ""
    source = snapshot(query="铜")
    service.store.save(saved_result(source=source))
    assert service.format_saved_interpretation("stock", "688648") == ""
    assert service.format_saved_interpretation("etf", "688648", "铜") == ""
    formatted = service.format_saved_interpretation("stock", "688648", "铜")
    for expected in [
        "历史相关资料 AI 解读",
        "优先当前原始资料",
        "2026-08-28",
        "2026-10-26",
        "https://example.com/policy",
        '"basis": "inference"',
        service.snapshot_digest(source),
    ]:
        assert expected in formatted
    fetch.assert_not_called()
    invoke.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_same_key_and_global_cap_prevent_extra_model_calls(isolated, monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def fetch(kind, code, name, query):
        entered.set()
        await release.wait()
        return snapshot(kind=kind, code=code, query=query)

    monkeypatch.setattr(service, "related_research", fetch)
    invoke = AsyncMock(return_value=draft())
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    pending = asyncio.create_task(service.generate_interpretation("stock", "688648", "测试"))
    await entered.wait()
    with pytest.raises(service.RelatedInterpretationServiceError) as caught:
        await service.generate_interpretation("stock", "688648", "测试")
    assert caught.value.status == 429
    service._busy.add(("etf", "560780", ""))
    with pytest.raises(service.RelatedInterpretationServiceError) as caught:
        await service.generate_interpretation("sector", "BK0917", "半导体")
    assert caught.value.status == 429
    invoke.assert_not_called()
    service._busy.remove(("etf", "560780", ""))
    release.set()
    await pending
    invoke.assert_awaited_once()
    assert service._busy == set()


@pytest.mark.asyncio
async def test_total_timeout_releases_slot_without_saving_or_model_retry(isolated, monkeypatch):
    async def delayed_model(**kwargs):
        await asyncio.sleep(1)
        return draft()

    monkeypatch.setattr(service, "GENERATION_TIMEOUT", 0.02)
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=snapshot()))
    invoke = AsyncMock(side_effect=delayed_model)
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    with pytest.raises(service.RelatedInterpretationServiceError) as caught:
        await service.generate_interpretation("stock", "688648", "测试")
    assert caught.value.status == 504
    assert service.get_saved("stock", "688648") is None
    assert service._busy == set()
    invoke.assert_awaited_once()


def test_read_and_save_errors_are_visible_and_preserve_last_success(client, monkeypatch):
    prior = saved_result()
    service.store.save(prior)
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=snapshot()))
    monkeypatch.setattr(service.llm_service, "invoke_structured", AsyncMock(return_value=draft()))

    def fail_save(result):
        raise OSError("disk unavailable")

    monkeypatch.setattr(service.store, "save", fail_save)
    response = client.post(URL, params=PARAMS, json={"refresh": True})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RELATED_INTERPRETATION_SAVE_FAILED"
    assert service.get_saved("stock", "688648") == prior
    service.store.path.write_text("not a database")
    assert client.get(URL, params=PARAMS).status_code == 503


@pytest.mark.asyncio
async def test_openapi_exposes_frozen_contract(isolated):
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        document = (await client.get("/openapi.json")).json()
    assert set(document["paths"][URL]) == {"get", "post"}
    schema = document["components"]["schemas"]["RelatedInterpretationRequest"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["refresh"]["default"] is False
    assert document["components"]["schemas"]["RelatedEvent"]["properties"]["summary"]


def test_new_generation_requires_brief_but_legacy_saved_records_still_read(isolated):
    legacy = saved_result().model_dump(mode="json")
    legacy["analysis"].pop("synthesis")
    restored = RelatedInterpretationResult.model_validate(legacy)
    assert restored.analysis.synthesis is None
    service.store.save(restored)
    assert service.get_saved("stock", "688648").analysis.synthesis is None
    with pytest.raises(ValidationError):
        RelatedInterpretationGeneration.model_validate(legacy["analysis"])
    data = draft().model_dump()
    data["events"] *= 4
    with pytest.raises(ValidationError):
        RelatedInterpretationGeneration.model_validate(data)


@pytest.mark.parametrize("ids", [["news:2"], ["news:1", "news:2"], ["news:1", "news:1"]])
def test_brief_cannot_use_excluded_material_or_duplicate_votes(ids):
    analysis = draft(two_sources=True)
    analysis.synthesis.source_ids = ids
    with pytest.raises(ValueError, match="Synthesis"):
        service.validate_interpretation(analysis, snapshot(two_sources=True))


def test_missing_combined_brief_never_replaces_success_or_retries(client, monkeypatch):
    prior = saved_result()
    service.store.save(prior)
    invalid = draft()
    invalid.synthesis = None
    invoke = AsyncMock(return_value=invalid)
    monkeypatch.setattr(service, "related_research", AsyncMock(return_value=snapshot()))
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    result = client.post(URL, params=PARAMS, json={"refresh": True})
    assert result.status_code == 502
    invoke.assert_awaited_once()
    assert service.get_saved("stock", "688648") == prior


def test_saved_brief_reaches_debate_context_with_sources_and_original_dates(isolated):
    prior = saved_result()
    service.store.save(prior)
    formatted = service.format_saved_interpretation("stock", "688648")
    payload = json.loads(formatted[formatted.index("{") :])
    assert payload["analysis"]["synthesis"] == prior.analysis.synthesis.model_dump()
    assert payload["generated_at"] == prior.generated_at.isoformat()
    assert payload["sources"][0]["published_at"] == prior.snapshot.data[0].published_at
    assert "不能当新事实或当前信号" in formatted


def test_unused_article_is_retained_without_rejecting_good_brief(client, monkeypatch):
    analysis = draft(two_sources=True)
    analysis.excluded_sources = []
    invoke = AsyncMock(return_value=analysis)
    monkeypatch.setattr(
        service, "related_research", AsyncMock(return_value=snapshot(two_sources=True))
    )
    monkeypatch.setattr(service.llm_service, "invoke_structured", invoke)
    response = client.post(URL, params=PARAMS, json={"refresh": True})
    assert response.status_code == 200
    result = response.json()
    assert result["analysis"]["synthesis"] == analysis.synthesis.model_dump()
    assert result["analysis"]["excluded_sources"][0]["source_id"] == "news:2"
    assert "不据此认定无关" in result["analysis"]["excluded_sources"][0]["reason"]
    invoke.assert_awaited_once()

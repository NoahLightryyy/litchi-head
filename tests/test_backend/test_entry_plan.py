"""Entry-plan contracts and service behavior; no live model calls."""
import json
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.entry_plan import (
    EntryEvidence,
    EntryPlanDraft,
    EntryPlanRequest,
    EntryPlanResult,
    EntryPlanStore,
    _daily_content,
    build_entry_prompt,
    collect_entry_context,
    current_market_facts,
    qualify_historical_conditions,
)
from backend.routers import entry_plan as module
from src.debate.models import DebateResult
from src.debate.session_store import DebateSessionRecord


def plan_payload() -> dict:
    return {"plans": [{
        "horizon": horizon, "status": "waiting", "summary": "等待确认后考虑买入",
        "conditions": [{"condition": "突破后回踩企稳", "status": "unknown",
                        "explanation": "当前只取得收盘快照", "evidence_ids": ["quote"]}],
        "entry_low": 10, "entry_high": 11, "stop_loss": 9,
        "price_basis": "日线支撑作为候选，属于研究建议", "price_evidence_ids": ["quote"],
        "invalidation": ["跌破候选支撑重新研究"],
        "batches": [{"budget_pct": 40, "trigger": "首次确认"},
                    {"budget_pct": 60, "trigger": "进一步确认"}],
        "position_note": "金额按用户预算及风险上限计算", "limitations": ["未持续监测"],
    } for horizon in ("short", "medium", "long")]}


def result_payload() -> dict:
    return {**plan_payload(), "session_id": "deb_test", "stock_code": "688648",
            "source_session_id": "deb_test", "source_research_generated_at": datetime.now(UTC),
            "stock_name": "测试标的", "instrument_type": "stock",
            "generated_at": datetime.now(UTC), "model": "test",
            "evidence": [{"id": "quote", "kind": "quote", "title": "行情",
                          "data_time": "2026-10-26T15:00:00+08:00", "content": "报价10元"}]}


def test_entry_contract_roundtrip_and_no_account_fields():
    result = EntryPlanResult(**result_payload())
    assert EntryPlanResult.model_validate_json(result.model_dump_json()) == result
    assert len(EntryPlanResult.model_json_schema()["$defs"]) > 0
    with pytest.raises(ValidationError):
        EntryPlanRequest.model_validate({"refresh": True, "cash": 10000})


@pytest.mark.parametrize("changes", [
    {"entry_low": float("nan")}, {"stop_loss": float("inf")}, {"stop_loss": 0},
    {"entry_low": 12}, {"stop_loss": 10}, {"entry_high": None}, {"status": "consider"},
    {"batches": [{"budget_pct": 60, "trigger": "观察"}]},
    {"batches": [{"budget_pct": 33.333, "trigger": "观察"},
                 {"budget_pct": 66.667, "trigger": "再确认"}]},
    {"price_evidence_ids": []}, {"invalidation": [" "]},
])
def test_invalid_price_state_or_allocation_is_rejected(changes):
    payload = plan_payload()
    payload["plans"][0].update(changes)
    with pytest.raises(ValidationError):
        EntryPlanDraft.model_validate(payload)


def test_null_prices_and_bearish_waiting_plan_are_supported():
    payload = plan_payload()
    payload["plans"][0].update(entry_low=None, entry_high=None, stop_loss=None,
                               price_evidence_ids=[], summary="当前看跌，等待转强后再评估")
    assert EntryPlanDraft(**payload).plans[0].entry_low is None
    payload["plans"][0]["conditions"][0]["status"] = "met"
    payload["plans"][0]["status"] = "consider"
    with pytest.raises(ValidationError):
        EntryPlanDraft(**payload)


def test_reference_and_horizon_validation():
    for alter in ("unknown", "history_prices", "duplicate_horizon"):
        payload = deepcopy(result_payload())
        if alter == "unknown":
            payload["plans"][0]["conditions"][0]["evidence_ids"] = ["invented"]
        elif alter == "history_prices":
            payload["evidence"][0]["kind"] = "analysis"
        else:
            payload["plans"][1]["horizon"] = "short"
        with pytest.raises(ValidationError):
            EntryPlanResult(**payload)


def record(kind="stock") -> DebateSessionRecord:
    code = "688648" if kind == "stock" else "560780"
    return DebateSessionRecord(
        session_id="deb_test", stock_code=code, instrument_type=kind,
        status="completed", progress=100,
        result=DebateResult(session_id="deb_test", stock_code=code, instrument_type=kind,
                            stock_name="测试标的", question="投资研究"),
    )


def context() -> tuple[list[EntryEvidence], list[str]]:
    return [EntryEvidence(**result_payload()["evidence"][0])], ["未复权，未连续监测"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "store", EntryPlanStore(tmp_path / "plans.db"))
    monkeypatch.setattr(module, "configured", lambda: True)
    monkeypatch.setattr(module.sessions, "get", AsyncMock(return_value=record()))
    module._busy.clear()
    module.limiter.reset()
    app = FastAPI()
    app.state.limiter = module.limiter
    app.include_router(module.router)
    with TestClient(app) as test_client:
        yield test_client
    module._busy.clear()


URL = "/api/debate/deb_test/entry-plan"


@pytest.mark.parametrize("kind", ["stock", "etf"])
def test_generate_once_read_free_and_explicit_refresh(client, kind):
    module.sessions.get.return_value = record(kind)
    with patch.object(module, "collect_entry_context",
                      AsyncMock(return_value=context())) as collect, \
            patch.object(module.llm_service, "invoke_structured",
                         AsyncMock(return_value=EntryPlanDraft(**plan_payload()))) as generate:
        assert client.get(URL).json() is None
        generate.assert_not_called()
        first = client.post(URL, json={})
        assert first.status_code == 200
        assert first.json()["instrument_type"] == kind
        assert first.json()["source_session_id"] == "deb_test"
        assert not first.json()["cached"]
        assert client.get(URL).json()["cached"]
        assert client.post(URL, json={}).json()["cached"]
        assert generate.await_count == collect.await_count == 1
        assert client.post(URL, json={"refresh": True}).status_code == 200
        assert generate.await_count == 2
        assert "cash" not in generate.call_args.kwargs["prompt"]
        assert EntryPlanStore(module.store.path).get("deb_test") is not None


@pytest.mark.parametrize("error,status", [(TimeoutError(), 504), (RuntimeError("provider"), 502)])
def test_failure_keeps_previous_and_releases_busy(client, error, status):
    previous = EntryPlanResult(**result_payload())
    module.store.save(previous)
    with patch.object(module, "collect_entry_context", AsyncMock(return_value=context())), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock(side_effect=error)):
        response = client.post(URL, json={"refresh": True})
        assert response.status_code == status
        assert response.json()["error"]["retryable"]
        assert module.store.get("deb_test") == previous
        assert not module._busy


@pytest.mark.parametrize("defect", ["reference", "price"])
def test_untrusted_output_revalidated_before_persistence(client, defect):
    output = EntryPlanDraft(**plan_payload())
    evidence, gaps = context()
    if defect == "reference":
        output.plans[0].conditions[0].evidence_ids = ["fake"]
    elif defect == "price":
        output.plans[0].stop_loss = 50
    with patch.object(module, "collect_entry_context", AsyncMock(return_value=(evidence, gaps))), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock(return_value=output)):
        response = client.post(URL, json={})
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "ENTRY_PLAN_INVALID_OUTPUT"
        assert module.store.get("deb_test") is None


@pytest.mark.parametrize("case,status", [("missing", 404), ("running", 409),
                                       ("busy", 429), ("capacity", 429), ("config", 503)])
def test_preconditions_do_not_start_model(client, monkeypatch, case, status):
    if case == "missing":
        module.sessions.get.return_value = None
    elif case == "running":
        module.sessions.get.return_value = DebateSessionRecord(
            session_id="deb_test", stock_code="688648", status="running", progress=50)
    elif case == "busy":
        module._busy.add("deb_test")
    elif case == "capacity":
        module._busy.update({"deb_other", "deb_third"})
    else:
        monkeypatch.setattr(module, "configured", lambda: False)
    with patch.object(module.llm_service, "invoke_structured", AsyncMock()) as generate:
        assert client.post(URL, json={}).status_code == status
        generate.assert_not_called()


def test_corrupted_storage_and_invalid_request_do_not_generate(client):
    module.store.save(EntryPlanResult(**result_payload()))
    with module.store._connect() as connection:
        connection.execute("UPDATE entry_plans SET digest='invalid'")
    with patch.object(module.llm_service, "invoke_structured", AsyncMock()) as generate:
        assert client.get(URL).status_code == 503
        assert client.post(URL, json={}).status_code == 503
        assert client.post(URL, json={"cash": 20000}).status_code == 422
        generate.assert_not_called()


@pytest.mark.asyncio
async def test_stock_partial_sources_preserve_research_and_available_daily():
    from datetime import date

    from backend.kline_display import RawDailyDisplay
    from src.data.evidence import SourceStatus
    from src.data.kline import MarketCode, RawDailyBar

    daily = RawDailyDisplay(
        symbol="688648", status=SourceStatus.SUCCESS_DATA, fetched_at=datetime.now(UTC),
        data_start=date(2026, 10, 23), data_end=date(2026, 10, 23), bars=[RawDailyBar(
            code="688648", market=MarketCode.SSE, trade_date=date(2026, 10, 23),
            open=10, close=10, high=11, low=9, volume=1000,
        )],
    )
    with patch("backend.quote_display.get_display_quote", side_effect=RuntimeError("offline")), \
            patch("backend.kline_display.get_raw_daily_display", return_value=daily):
        evidence, gaps = await collect_entry_context(record())
    assert [item.kind for item in evidence] == ["analysis", "daily"]
    assert evidence[1].data_time == "2026-10-23"
    assert "ma5" in evidence[1].content and 'null' in evidence[1].content
    assert any("行情暂不可用" in gap for gap in gaps)


@pytest.mark.asyncio
async def test_etf_catalog_unavailable_preserves_historical_context():
    with patch("backend.etf_display.get_catalog", AsyncMock(side_effect=RuntimeError("offline"))):
        evidence, gaps = await collect_entry_context(record("etf"))
    assert len(evidence) == 1 and evidence[0].kind == "analysis"
    assert '"instrument_type":"etf"' in evidence[0].content
    assert any("ETF身份目录" in gap for gap in gaps)


def test_storage_failure_does_not_return_unsaved_success(client):
    with patch.object(module, "collect_entry_context", AsyncMock(return_value=context())), \
            patch.object(module.llm_service, "invoke_structured",
                         AsyncMock(return_value=EntryPlanDraft(**plan_payload()))), \
            patch.object(module.store, "save", side_effect=OSError("disk full")):
        response = client.post(URL, json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENTRY_PLAN_SAVE_FAILED"
    assert module.store.get("deb_test") is None
    assert not module._busy


@pytest.mark.asyncio
async def test_concurrent_duplicate_is_rejected_and_total_deadline_cancels(client, monkeypatch):
    import asyncio

    entered = asyncio.Event()

    async def slow_model(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(module, "GENERATION_TIMEOUT", 0.1)
    with patch.object(module, "collect_entry_context", AsyncMock(return_value=context())), \
            patch.object(module.llm_service, "invoke_structured", slow_model):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                                     base_url="http://test") as caller:
            first = asyncio.create_task(caller.post(URL, json={}))
            await asyncio.wait_for(entered.wait(), timeout=1)
            assert (await caller.post(URL, json={})).status_code == 429
            assert (await first).status_code == 504
    assert not module._busy
    assert module.store.get("deb_test") is None


@pytest.mark.asyncio
async def test_quote_time_is_upstream_timestamp_not_collection_clock():
    from backend.quote_display import DisplayQuote

    stamp = datetime(2026, 10, 23, 7, tzinfo=UTC)
    quote = DisplayQuote(code="688648", name="测试标的", price=10, change=0, change_pct=0,
                         high=11, low=9, prev_close=10, volume=1000, amount=10000,
                         fetched_at=stamp, source="sina")
    with patch("backend.quote_display.get_display_quote", return_value=quote), \
            patch("backend.kline_display.get_raw_daily_display", side_effect=RuntimeError("down")):
        evidence, gaps = await collect_entry_context(record())
    assert evidence[1].data_time == stamp.isoformat()
    assert evidence[0].data_time != evidence[1].data_time
    assert any("日线暂不可用" in gap for gap in gaps)


@pytest.mark.parametrize("claimed_status", ["met", "unmet"])
def test_history_only_condition_is_explicitly_qualified_as_unverified(client, claimed_status):
    output = EntryPlanDraft(**plan_payload())
    evidence, gaps = context()
    evidence[0].kind = "analysis"
    for plan in output.plans:
        plan.entry_low = plan.entry_high = plan.stop_loss = None
        plan.price_evidence_ids = []
        plan.conditions[0].status = claimed_status
    with patch.object(module, "collect_entry_context", AsyncMock(return_value=(evidence, gaps))), \
            patch.object(module.llm_service, "invoke_structured", AsyncMock(return_value=output)):
        response = client.post(URL, json={})
    assert response.status_code == 200
    for plan in response.json()["plans"]:
        assert plan["status"] == "waiting"
        assert plan["conditions"][0]["status"] == "unknown"
        assert "包含历史AI引用，本次未重新核验相关事实" in plan["conditions"][0]["explanation"]


@pytest.mark.parametrize("claimed_status", ["met", "unmet"])
def test_mixed_quote_and_history_cannot_upgrade_unverified_valuation(client, claimed_status):
    payload = result_payload()
    payload["evidence"].append({"id": "debate", "kind": "analysis", "title": "旧研究",
                                "data_time": "2026-10-23", "content": "旧AI净资产未核实"})
    for plan in payload["plans"]:
        plan["conditions"][0].update(status=claimed_status, evidence_ids=["quote", "debate"])
        if claimed_status == "met":
            plan["status"] = "consider"
    original = EntryPlanResult(**payload)
    qualified = qualify_historical_conditions(original)
    assert qualify_historical_conditions(qualified) == qualified  # Repeated reads are idempotent.
    for plan in qualified.plans:
        assert plan.status == "waiting"
        assert plan.conditions[0].status == "unknown"
        assert "未重新核验相关事实" in plan.conditions[0].explanation
    module.store.save(original)
    for response in (client.get(URL), client.post(URL, json={})):
        assert response.status_code == 200
        assert response.json()["plans"][0]["conditions"][0]["status"] == "unknown"
    assert module.store.get("deb_test") == original  # Read projection never rewrites history.


def test_current_computed_facts_take_priority_without_promoting_volume_conflicts():
    rows = [{"date": f"2026-10-{day:02d}", "open": 10, "high": 11, "low": 9,
             "close": 10.1, "volume": 100000} for day in range(1, 27)]
    daily = _daily_content({"source": "tencent", "bars": rows}, rows)
    evidence = [
        EntryEvidence(id="debate", kind="analysis", title="旧研究",
                      data_time="2026-10-23", content="技术指标无法计算，需要双源校验"),
        EntryEvidence(id="quote", kind="quote", title="行情", data_time="2026-10-26",
                      content=json.dumps({"price": 10.1, "volume": 1000})),
        EntryEvidence(id="daily", kind="daily", title="日线", data_time="2026-10-26",
                      content=daily),
    ]
    facts = current_market_facts(evidence)
    assert facts["daily"]["ma"]["ma5"] == 10.1
    assert "ma60" not in facts["daily"]["ma"]  # No invented warm-up values.
    assert facts["daily"]["available_ma_count"] == 3
    assert "成交量明显不一致" in facts["volume_limitation"]
    assert "价格与MA仍可用于条件研究" in facts["volume_limitation"]
    prompt = build_entry_prompt(record(), evidence, [])
    parsed = json.loads(prompt)
    assert parsed["current_observations_and_calculations"] == facts
    assert len(parsed["current_market_evidence"][1]["data"]["bars"]) == 20
    assert "技术指标无法计算，需要双源校验" not in prompt  # No repeated legacy transcript.
    assert "单源" in parsed["final_priority"]
    assert "2至3批" in parsed["final_priority"]
    assert "原研究曾称" in parsed["final_priority"]
    assert json.loads(daily)["computed"]["ma"]["ma5"] == 10.1


@pytest.mark.asyncio
async def test_etf_valid_quote_is_preserved_when_daily_fails():
    from pydantic import HttpUrl

    from backend.etf_contract import EtfCatalog, EtfDetail, EtfIdentity, EtfQuote

    stamp = datetime(2026, 10, 23, 7, tzinfo=UTC)
    identity = EtfIdentity(code="560780", symbol="sh560780", exchange="SH", name="测试ETF")
    catalog = EtfCatalog(items=(identity,), fetched_at=datetime.now(UTC))
    detail = EtfDetail(identity=identity, status="ready", quote=EtfQuote(
        price=0.749, previous_close=0.792, change=-0.043, change_pct=-5.43,
        quoted_at=stamp, source_name="测试ETF"), source_url=HttpUrl("https://example.com"),
        catalog_fetched_at=catalog.fetched_at, fetched_at=datetime.now(UTC), limitations=["单源"])
    with patch("backend.etf_display.get_catalog", AsyncMock(return_value=catalog)), \
            patch("backend.etf_display.detail", AsyncMock(return_value=detail)), \
            patch("backend.etf_kline.get_etf_kline", AsyncMock(side_effect=RuntimeError("down"))):
        evidence, gaps = await collect_entry_context(record("etf"))
    assert [item.kind for item in evidence] == ["analysis", "quote"]
    assert evidence[1].data_time == stamp.isoformat()
    assert "0.749" in evidence[1].content
    assert any("日线暂不可用" in gap for gap in gaps)

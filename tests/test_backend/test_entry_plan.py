"""Entry-plan contracts and service behavior; no live model calls."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.entry_plan import EntryPlanDraft, EntryPlanRequest, EntryPlanResult


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

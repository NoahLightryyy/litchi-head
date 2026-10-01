"""Fail-closed AI decision verification and immutable association tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from src.debate.models import AgentAnalysis, DebateResult, VoteSummary
from src.debate.session_store import DebateSessionRecord
from src.retro.ai_decision_reference import (
    AiDecisionReference,
    DecisionEvidenceReference,
    DecisionProvenance,
    DecisionReferenceReason,
    verify_ai_decision_reference,
)
from src.retro.ai_decision_reference_ledger import (
    AiDecisionReferenceConflictError,
    AiDecisionReferenceLedger,
    AiDecisionReferenceLedgerError,
)
from src.retro.user_actions import UserActionEvent

NOW = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def _event(**updates: object) -> UserActionEvent:
    values: dict[str, object] = {
        "client_action_id": "browser-001",
        "event_id": "ua_1234567890abcdef12345678",
        "user_id": "user-a",
        "session_id": "debate-001",
        "ai_decision_id": "debate-001",
        "stock_code": "300199",
        "action": "watch",
        "occurred_at": NOW,
        "recorded_at": NOW,
    }
    values.update(updates)
    return UserActionEvent.model_validate(values)


def _analysis(**updates: object) -> AgentAnalysis:
    values: dict[str, object] = {
        "agent_name": "master.buffett",
        "skill_id": "buffett",
        "skill_name": "巴菲特",
        "rating": "看涨",
        "score": 80,
        "summary": "有护城河",
        "analysis": "现金流与竞争优势均支持观点。",
        "key_evidence": ["evidence://fundamental/300199/2026-10-01"],
        "confidence": 0.8,
        "success": True,
    }
    values.update(updates)
    return AgentAnalysis.model_validate(values)


def _session(
    *, analyses: list[AgentAnalysis] | None = None, **summary_updates: object
) -> DebateSessionRecord:
    summary_values: dict[str, object] = {
        "total_votes": 1,
        "average_score": 80,
        "weighted_score": 80,
        "confidence": 0.8,
        "consensus": "看涨",
    }
    summary_values.update(summary_updates)
    result = DebateResult(
        session_id="debate-001",
        stock_code="300199",
        stock_name="测试股票",
        question="是否值得关注？",
        analyses=analyses if analyses is not None else [_analysis()],
        vote_summary=VoteSummary.model_validate(summary_values),
    )
    return DebateSessionRecord(
        session_id="debate-001",
        stock_code="300199",
        question=result.question,
        status="completed",
        progress=100,
        result=result,
        created_at=NOW,
        updated_at=NOW,
    )


def _provenance() -> DecisionProvenance:
    return DecisionProvenance(
        decided_at=NOW,
        model_versions={"master.buffett": "deepseek-chat@2026-09"},
        prompt_versions={"master.buffett": "sha256:prompt-v3"},
        config_version="debate-config-v4",
        code_version="7d96ddf4a035c55636dcf1bfd55403d89e79e0d3",
        evidence_references=[
            DecisionEvidenceReference(
                evidence_id="quote:300199:2026-10-01T08:00:00Z",
                source_id="eastmoney",
                as_of=NOW,
                sha256="a" * 64,
            )
        ],
    )


def _reason_values(reference: AiDecisionReference) -> set[str]:
    return {reason.value for reason in reference.reason_codes}


def test_legacy_snapshot_with_scores_is_ineligible_without_provenance() -> None:
    reference = verify_ai_decision_reference(event=_event(), session=_session(), checked_at=NOW)

    assert reference.status == "ineligible"
    assert not reference.eligible_for_effect_sample
    assert reference.original_viewpoints_sha256 is not None
    assert "decision_provenance_missing" in _reason_values(reference)
    assert "evidence_references_missing" in _reason_values(reference)


@pytest.mark.parametrize(
    ("session", "expected_reason"),
    [
        (_session(weighted_score=0), DecisionReferenceReason.WEIGHTED_SCORE_MISSING_OR_ZERO),
        (_session(confidence=0), DecisionReferenceReason.CONFIDENCE_MISSING_OR_ZERO),
        (
            _session(analyses=[_analysis(success=False, error="provider timeout")]),
            DecisionReferenceReason.AGENT_FAILURE_PRESENT,
        ),
        (
            DebateSessionRecord(
                session_id="debate-001",
                stock_code="300199",
                status="failed",
                progress=30,
                error="provider timeout",
                created_at=NOW,
                updated_at=NOW,
            ),
            DecisionReferenceReason.SESSION_NOT_COMPLETED,
        ),
    ],
)
def test_zero_scores_or_failed_requests_never_become_effect_samples(
    session: DebateSessionRecord,
    expected_reason: DecisionReferenceReason,
) -> None:
    reference = verify_ai_decision_reference(
        event=_event(),
        session=session,
        provenance=_provenance(),
        checked_at=NOW,
    )

    assert not reference.eligible_for_effect_sample
    assert expected_reason in reference.reason_codes


def test_complete_snapshot_and_provenance_can_become_eligible() -> None:
    reference = verify_ai_decision_reference(
        event=_event(),
        session=_session(),
        provenance=_provenance(),
        checked_at=NOW,
    )

    assert reference.status == "eligible"
    assert reference.eligible_for_effect_sample
    assert reference.reason_codes == []
    assert reference.successful_agent_count == 1
    assert reference.failed_agent_count == 0


def test_identity_mismatch_is_explicitly_ineligible() -> None:
    reference = verify_ai_decision_reference(
        event=_event(stock_code="000001"),
        session=_session(),
        provenance=_provenance(),
        checked_at=NOW,
    )

    assert DecisionReferenceReason.STOCK_CODE_MISMATCH in reference.reason_codes
    assert not reference.eligible_for_effect_sample


def test_provenance_must_cover_every_successful_agent() -> None:
    second = _analysis(agent_name="master.munger", skill_id="munger", skill_name="芒格")
    reference = verify_ai_decision_reference(
        event=_event(),
        session=_session(analyses=[_analysis(), second], total_votes=2),
        provenance=_provenance(),
        checked_at=NOW,
    )

    assert DecisionReferenceReason.MODEL_VERSION_MISSING in reference.reason_codes
    assert DecisionReferenceReason.PROMPT_VERSION_MISSING in reference.reason_codes
    assert not reference.eligible_for_effect_sample


@pytest.mark.asyncio
async def test_reference_is_idempotent_durable_and_user_isolated(tmp_path) -> None:
    database = tmp_path / "actions.sqlite3"
    reference = verify_ai_decision_reference(
        event=_event(),
        session=_session(),
        provenance=_provenance(),
        checked_at=NOW,
    )
    ledger = AiDecisionReferenceLedger(database)
    written, replayed = await ledger.append(reference)
    retried, second_replay = await ledger.append(
        reference.model_copy(update={"checked_at": datetime(2026, 10, 1, 9, tzinfo=UTC)})
    )

    assert not replayed
    assert second_replay
    assert retried == written

    restarted = AiDecisionReferenceLedger(database)
    own = await restarted.list_references(user_id="user-a", event_id=reference.event_id)
    other = await restarted.list_references(user_id="user-b", event_id=reference.event_id)
    assert own == [written]
    assert other == []


@pytest.mark.asyncio
async def test_reference_facts_are_immutable(tmp_path) -> None:
    ledger = AiDecisionReferenceLedger(tmp_path / "actions.sqlite3")
    reference = verify_ai_decision_reference(
        event=_event(),
        session=_session(),
        provenance=_provenance(),
        checked_at=NOW,
    )
    await ledger.append(reference)

    tampered = reference.model_copy(update={"stock_code": "000001"})
    with pytest.raises(AiDecisionReferenceConflictError):
        await ledger.append(tampered)


@pytest.mark.asyncio
async def test_persisted_reference_tampering_fails_closed(tmp_path) -> None:
    database = tmp_path / "actions.sqlite3"
    ledger = AiDecisionReferenceLedger(database)
    reference = verify_ai_decision_reference(
        event=_event(),
        session=_session(),
        provenance=_provenance(),
        checked_at=NOW,
    )
    await ledger.append(reference)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE ai_decision_references SET payload_json = ? WHERE reference_id = ?",
            (reference.model_dump_json().replace("300199", "000001"), reference.reference_id),
        )

    restarted = AiDecisionReferenceLedger(database)
    with pytest.raises(AiDecisionReferenceLedgerError, match="checksum"):
        await restarted.list_references(user_id="user-a")

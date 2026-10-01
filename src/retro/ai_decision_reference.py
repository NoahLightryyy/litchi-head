"""Fail-closed verification for immutable AI-decision references.

An action is never rewritten when a decision is checked.  Instead, this
module creates an immutable verification fact that binds the action to the
exact decision snapshot and provenance supplied by the producer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.debate.session_store import DebateSessionRecord, measure_session_snapshot
from src.retro.user_actions import UserActionEvent


class DecisionReferenceReason(str, Enum):
    """Machine-readable reasons that exclude a reference from effect samples."""

    DECISION_REFERENCE_MISSING = "decision_reference_missing"
    SESSION_NOT_COMPLETED = "session_not_completed"
    SESSION_RESULT_MISSING = "session_result_missing"
    SESSION_ID_MISMATCH = "session_id_mismatch"
    STOCK_CODE_MISMATCH = "stock_code_mismatch"
    VOTE_COUNT_MISSING = "vote_count_missing"
    AVERAGE_SCORE_MISSING_OR_ZERO = "average_score_missing_or_zero"
    WEIGHTED_SCORE_MISSING_OR_ZERO = "weighted_score_missing_or_zero"
    CONFIDENCE_MISSING_OR_ZERO = "confidence_missing_or_zero"
    AGENT_ANALYSES_MISSING = "agent_analyses_missing"
    AGENT_FAILURE_PRESENT = "agent_failure_present"
    AGENT_SCORE_MISSING_OR_ZERO = "agent_score_missing_or_zero"
    AGENT_CONFIDENCE_MISSING_OR_ZERO = "agent_confidence_missing_or_zero"
    DECISION_PROVENANCE_MISSING = "decision_provenance_missing"
    DECISION_TIME_MISSING = "decision_time_missing"
    MODEL_VERSION_MISSING = "model_version_missing"
    PROMPT_VERSION_MISSING = "prompt_version_missing"
    CONFIG_VERSION_MISSING = "config_version_missing"
    CODE_VERSION_MISSING = "code_version_missing"
    EVIDENCE_REFERENCES_MISSING = "evidence_references_missing"


class DecisionEvidenceReference(BaseModel):
    """Integrity-bound reference to evidence used by a decision."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=128)
    as_of: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("as_of")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include timezone")
        return value


class DecisionProvenance(BaseModel):
    """Producer-supplied versions required for a verifiable decision."""

    model_config = ConfigDict(extra="forbid")

    decided_at: datetime
    model_versions: dict[str, str] = Field(min_length=1)
    prompt_versions: dict[str, str] = Field(min_length=1)
    config_version: str = Field(min_length=1, max_length=256)
    code_version: str = Field(min_length=7, max_length=128)
    evidence_references: list[DecisionEvidenceReference] = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_versions(self) -> DecisionProvenance:
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decided_at must include timezone")
        if any(not key.strip() or not value.strip() for key, value in self.model_versions.items()):
            raise ValueError("model_versions keys and values must be non-empty")
        if any(not key.strip() or not value.strip() for key, value in self.prompt_versions.items()):
            raise ValueError("prompt_versions keys and values must be non-empty")
        return self


class AiDecisionReference(BaseModel):
    """Immutable eligibility decision for one action/snapshot/provenance tuple."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"
    reference_id: str = Field(pattern=r"^air_[0-9a-f]{24}$")
    user_id: str
    event_id: str
    decision_id: str | None
    stock_code: str
    session_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_viewpoints_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    status: Literal["eligible", "ineligible"]
    eligible_for_effect_sample: bool
    reason_codes: list[DecisionReferenceReason]
    successful_agent_count: int = Field(ge=0)
    failed_agent_count: int = Field(ge=0)
    provenance: DecisionProvenance | None
    checked_at: datetime

    @model_validator(mode="after")
    def require_consistent_eligibility(self) -> AiDecisionReference:
        eligible = not self.reason_codes and self.provenance is not None
        if self.eligible_for_effect_sample != eligible:
            raise ValueError("eligibility must match reason_codes and provenance")
        if (self.status == "eligible") != eligible:
            raise ValueError("status must match eligibility")
        return self


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_ai_decision_reference(
    *,
    event: UserActionEvent,
    session: DebateSessionRecord,
    provenance: DecisionProvenance | None = None,
    checked_at: datetime | None = None,
) -> AiDecisionReference:
    """Verify a decision snapshot; any absent trust signal makes it ineligible."""
    reasons: set[DecisionReferenceReason] = set()
    if event.ai_decision_id is None:
        reasons.add(DecisionReferenceReason.DECISION_REFERENCE_MISSING)
    if event.session_id != session.session_id or (
        event.ai_decision_id is not None and event.ai_decision_id != session.session_id
    ):
        reasons.add(DecisionReferenceReason.SESSION_ID_MISMATCH)
    if event.stock_code != session.stock_code:
        reasons.add(DecisionReferenceReason.STOCK_CODE_MISMATCH)
    if session.status != "completed":
        reasons.add(DecisionReferenceReason.SESSION_NOT_COMPLETED)

    result = session.result
    successful_count = 0
    failed_count = 0
    viewpoints_digest: str | None = None
    if result is None:
        reasons.add(DecisionReferenceReason.SESSION_RESULT_MISSING)
    else:
        viewpoints = [item.model_dump(mode="json") for item in result.analyses]
        viewpoints_digest = _canonical_digest(viewpoints)
        successful = [item for item in result.analyses if item.success]
        failed = [item for item in result.analyses if not item.success]
        successful_count = len(successful)
        failed_count = len(failed)
        if not result.analyses or not successful:
            reasons.add(DecisionReferenceReason.AGENT_ANALYSES_MISSING)
        if failed:
            reasons.add(DecisionReferenceReason.AGENT_FAILURE_PRESENT)
        if any(item.score <= 0 for item in successful):
            reasons.add(DecisionReferenceReason.AGENT_SCORE_MISSING_OR_ZERO)
        if any(item.confidence <= 0 for item in successful):
            reasons.add(DecisionReferenceReason.AGENT_CONFIDENCE_MISSING_OR_ZERO)
        summary = result.vote_summary
        if summary.total_votes <= 0:
            reasons.add(DecisionReferenceReason.VOTE_COUNT_MISSING)
        if summary.average_score <= 0:
            reasons.add(DecisionReferenceReason.AVERAGE_SCORE_MISSING_OR_ZERO)
        if summary.weighted_score <= 0:
            reasons.add(DecisionReferenceReason.WEIGHTED_SCORE_MISSING_OR_ZERO)
        if summary.confidence <= 0:
            reasons.add(DecisionReferenceReason.CONFIDENCE_MISSING_OR_ZERO)

    if provenance is None:
        reasons.update(
            {
                DecisionReferenceReason.DECISION_PROVENANCE_MISSING,
                DecisionReferenceReason.DECISION_TIME_MISSING,
                DecisionReferenceReason.MODEL_VERSION_MISSING,
                DecisionReferenceReason.PROMPT_VERSION_MISSING,
                DecisionReferenceReason.CONFIG_VERSION_MISSING,
                DecisionReferenceReason.CODE_VERSION_MISSING,
                DecisionReferenceReason.EVIDENCE_REFERENCES_MISSING,
            }
        )
    elif result is not None:
        successful_agent_names = {item.agent_name for item in result.analyses if item.success}
        if not successful_agent_names.issubset(provenance.model_versions):
            reasons.add(DecisionReferenceReason.MODEL_VERSION_MISSING)
        if not successful_agent_names.issubset(provenance.prompt_versions):
            reasons.add(DecisionReferenceReason.PROMPT_VERSION_MISSING)

    measurement = measure_session_snapshot(session)
    identity_payload = {
        "event_id": event.event_id,
        "session_snapshot_sha256": measurement.sha256,
        "provenance": provenance.model_dump(mode="json") if provenance else None,
    }
    reference_id = f"air_{_canonical_digest(identity_payload)[:24]}"
    ordered_reasons = sorted(reasons, key=lambda item: item.value)
    eligible = not ordered_reasons and provenance is not None
    return AiDecisionReference(
        reference_id=reference_id,
        user_id=event.user_id,
        event_id=event.event_id,
        decision_id=event.ai_decision_id,
        stock_code=event.stock_code,
        session_snapshot_sha256=measurement.sha256,
        original_viewpoints_sha256=viewpoints_digest,
        status="eligible" if eligible else "ineligible",
        eligible_for_effect_sample=eligible,
        reason_codes=ordered_reasons,
        successful_agent_count=successful_count,
        failed_agent_count=failed_count,
        provenance=provenance,
        checked_at=checked_at or datetime.now(UTC),
    )


__all__ = [
    "AiDecisionReference",
    "DecisionEvidenceReference",
    "DecisionProvenance",
    "DecisionReferenceReason",
    "verify_ai_decision_reference",
]

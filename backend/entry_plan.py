"""Conditional entry-plan contract, independent of legacy trading defaults."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class EntryEvidence(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["analysis", "quote", "daily"]
    title: str = Field(min_length=1, max_length=200)
    data_time: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=120000)


class EntryCondition(StrictModel):
    condition: str = Field(min_length=1, max_length=400)
    status: Literal["met", "unmet", "unknown"]
    explanation: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class EntryBatch(StrictModel):
    budget_pct: float = Field(gt=0, le=100)
    trigger: str = Field(min_length=1, max_length=400)


class HorizonEntryPlan(StrictModel):
    horizon: Literal["short", "medium", "long"]
    status: Literal["consider", "waiting", "insufficient"]
    summary: str = Field(min_length=1, max_length=600)
    conditions: list[EntryCondition] = Field(min_length=1, max_length=6)
    entry_low: float | None = Field(ge=0, default=None)
    entry_high: float | None = Field(ge=0, default=None)
    stop_loss: float | None = Field(ge=0, default=None)
    price_basis: str = Field(min_length=1, max_length=600)
    price_evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    invalidation: list[str] = Field(min_length=1, max_length=5)
    batches: list[EntryBatch] = Field(min_length=1, max_length=4)
    position_note: str = Field(min_length=1, max_length=600)
    limitations: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        prices = (self.entry_low, self.entry_high, self.stop_loss)
        if any(value is None for value in prices) and any(value is not None for value in prices):
            raise ValueError("entry and stop prices must be present together")
        if self.entry_low is not None:
            if (self.entry_high is None or self.stop_loss is None
                    or not 0 < self.stop_loss < self.entry_low <= self.entry_high):
                raise ValueError("prices must satisfy 0 < stop < entry_low <= entry_high")
            if not self.price_evidence_ids:
                raise ValueError("candidate prices require evidence")
        if abs(sum(batch.budget_pct for batch in self.batches) - 100) > 0.000001:
            raise ValueError("batch budget percentages must sum to 100")
        if self.status == "consider" and (
            self.entry_low is None or any(item.status != "met" for item in self.conditions)
        ):
            raise ValueError("consider requires grounded prices and all conditions met")
        if any(not value.strip() for value in [*self.invalidation, *self.limitations]):
            raise ValueError("plan explanations must not be blank")
        return self


class EntryPlanDraft(StrictModel):
    plans: list[HorizonEntryPlan] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_horizons(self) -> Self:
        if {plan.horizon for plan in self.plans} != {"short", "medium", "long"}:
            raise ValueError("exactly one plan for each horizon is required")
        return self


class EntryPlanResult(EntryPlanDraft):
    schema_version: Literal[1] = 1
    session_id: str = Field(min_length=1, max_length=100)
    source_session_id: str = Field(min_length=1, max_length=100)
    source_research_generated_at: datetime
    stock_code: str = Field(pattern=r"^\d{6}$")
    instrument_type: Literal["stock", "etf"]
    stock_name: str = Field(min_length=1)
    generated_at: datetime
    model: str = Field(min_length=1)
    evidence: list[EntryEvidence] = Field(min_length=1)
    gaps: list[str] = Field(default_factory=list)
    cached: bool = False
    purpose: Literal["conditional_research_plan"] = "conditional_research_plan"
    status_basis: Literal["ai_review_of_dated_evidence"] = "ai_review_of_dated_evidence"

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if self.session_id != self.source_session_id:
            raise ValueError("source session identity mismatch")
        sources = {item.id: item for item in self.evidence}
        if len(sources) != len(self.evidence):
            raise ValueError("duplicate evidence IDs")
        for plan in self.plans:
            for ids in [plan.price_evidence_ids, *[item.evidence_ids for item in plan.conditions]]:
                if len(set(ids)) != len(ids) or not set(ids) <= sources.keys():
                    raise ValueError("unknown or repeated evidence reference")
            if plan.entry_low is not None and not any(
                sources[key].kind in {"quote", "daily"} for key in plan.price_evidence_ids
            ):
                raise ValueError("candidate prices need actual market evidence")
        return self


class EntryPlanRequest(StrictModel):
    refresh: bool = False


class EntryPlanErrorBody(StrictModel):
    code: Literal[
        "ENTRY_PLAN_NOT_FOUND", "ENTRY_PLAN_SESSION_NOT_READY", "ENTRY_PLAN_BUSY",
        "ENTRY_PLAN_TIMEOUT", "ENTRY_PLAN_INVALID_OUTPUT", "ENTRY_PLAN_FAILED",
        "ENTRY_PLAN_READ_FAILED", "ENTRY_PLAN_SAVE_FAILED", "ENTRY_PLAN_NOT_CONFIGURED",
    ]
    message: str
    retryable: bool


class EntryPlanError(StrictModel):
    error: EntryPlanErrorBody

"""Source-bounded interpretation of retrieved materials, not verified policy evidence."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from backend.related_research_contract import RelatedResearchResult, SubjectKind


class SourceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    field: Literal["title", "excerpt"]
    quote: str = Field(min_length=2, max_length=300)


class ReportedSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    basis: Literal["reported"] = "reported"
    quotes: list[SourceQuote] = Field(min_length=1, max_length=4)


class RelatedInference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    basis: Literal["inference"] = "inference"


class RelatedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    source_ids: list[str] = Field(min_length=1, max_length=12)
    summary: ReportedSummary
    impact_direction: Literal["positive", "negative", "mixed", "unclear"]
    impact_path: RelatedInference
    affected_scope: RelatedInference
    duration: RelatedInference
    market_reaction: RelatedInference
    business_realization: RelatedInference
    subject_relation: RelatedInference
    watchpoints: list[str] = Field(min_length=1, max_length=4)


class ExcludedRelatedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    reason: str = Field(min_length=1, max_length=240)


class RelatedInterpretationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overview: str = Field(min_length=1, max_length=600)
    events: list[RelatedEvent] = Field(max_length=6)
    excluded_sources: list[ExcludedRelatedSource] = Field(max_length=12)
    limitations: list[str] = Field(min_length=1, max_length=8)


class RelatedInterpretationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh: bool = False


class RelatedInterpretationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    subject_kind: SubjectKind
    subject_id: str
    subject_name: str
    query: str
    generated_at: AwareDatetime
    model: str
    prompt_version: str
    review_status: Literal["ai_unreviewed"] = "ai_unreviewed"
    purpose: Literal["related_material_context_only"] = "related_material_context_only"
    status: Literal["interpreted", "no_relevant_events"]
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot: RelatedResearchResult
    analysis: RelatedInterpretationDraft

    @model_validator(mode="after")
    def consistent_identity(self) -> "RelatedInterpretationResult":
        if (self.subject_kind, self.subject_id, self.subject_name, self.query) != (
            self.snapshot.subject_kind,
            self.snapshot.subject_id,
            self.snapshot.subject_name,
            self.snapshot.query,
        ):
            raise ValueError("Related interpretation identity and snapshot disagree")
        if bool(self.analysis.events) != (self.status == "interpreted"):
            raise ValueError("Related interpretation status and events disagree")
        return self


class RelatedInterpretationErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool


class RelatedInterpretationError(BaseModel):
    error: RelatedInterpretationErrorBody

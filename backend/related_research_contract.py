"""Display retrieval contract, separate from verified evidence and paid research."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

SubjectKind = Literal["stock", "etf", "sector"]


class RelatedKeyword(BaseModel):
    term: str = Field(min_length=2, max_length=80)
    origin: Literal["name", "business", "expanded", "user", "code"]


class RelatedDocument(BaseModel):
    id: str
    title: str
    url: HttpUrl
    publisher: str
    published_at: str
    excerpt: str = Field(max_length=600)
    source: Literal["policy_archive", "news_archive"]
    category: Literal["policy", "report"]
    relevance: Literal["direct", "topic"]
    matched_keywords: list[str] = Field(min_length=1)
    reason: str


class RelatedSourceStatus(BaseModel):
    source: Literal["policy_archive", "news_archive", "company_profile"]
    status: Literal["ok", "unavailable", "not_requested"]
    message: str = ""


class RelatedResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    subject_kind: SubjectKind
    subject_id: str
    subject_name: str
    query: str
    status: Literal["ready", "partial", "empty", "unavailable"]
    keywords: list[RelatedKeyword] = Field(max_length=12)
    data: list[RelatedDocument] = Field(max_length=12)
    sources: list[RelatedSourceStatus]
    searched_at: AwareDatetime
    window_days: Literal[365] = 365
    limitations: list[str]

    @model_validator(mode="after")
    def consistent_status(self) -> "RelatedResearchResult":
        if bool(self.data) != (self.status in {"ready", "partial"}):
            raise ValueError("Related research status and rows disagree")
        return self

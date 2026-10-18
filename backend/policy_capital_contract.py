"""Frozen S2 evidence boundary; no production endpoints registered here."""
from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(ContractModel):
    id: str = Field(min_length=1)
    canonical_document_id: str = Field(min_length=1)
    url: HttpUrl
    publisher: str = Field(min_length=1)
    role: Literal["primary", "official_repost", "reporting"]
    title: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    authored_date: date | None
    published_date: date
    effective_date: date | None
    effective_date_status: Literal["stated", "not_stated", "conflicting"]
    retrieved_at: AwareDatetime
    snapshot_sha256: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def effective_date_consistent(self) -> Self:
        if (self.effective_date_status == "stated") != (self.effective_date is not None):
            raise ValueError("only a stated effective date may be populated")
        return self


class Claim(ContractModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    assessment: Literal["supported", "inferred", "insufficient", "contradicted"]
    evidence_ids: list[str]
    limitations: list[str]

    @model_validator(mode="after")
    def support(self) -> Self:
        if self.assessment in {"supported", "contradicted"} and not self.evidence_ids:
            raise ValueError("factual assessment requires evidence")
        if self.assessment != "supported" and not self.limitations:
            raise ValueError("uncertain assessment requires limitations")
        return self


class Holding(ContractModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    nav_weight_pct: Decimal = Field(ge=0, le=100)


class HoldingsDisclosure(ContractModel):
    etf_symbol: str = Field(pattern=r"^\d{6}$")
    as_of: date
    published_date: date
    evidence_id: str
    coverage: Literal["top_ten", "full_disclosure", "other_subset"]
    holdings: list[Holding]

    @model_validator(mode="after")
    def valid_disclosure(self) -> Self:
        if self.published_date < self.as_of:
            raise ValueError("disclosure predates holdings")
        symbols = [h.symbol for h in self.holdings]
        if len(set(symbols)) != len(symbols):
            raise ValueError("duplicate holding")
        if sum(h.nav_weight_pct for h in self.holdings) > Decimal("100"):
            raise ValueError("NAV weights exceed 100 percent")
        return self


class EvidencePackage(ContractModel):
    schema_version: Literal[1] = 1
    package_id: str = Field(min_length=1)
    subject_kind: Literal["sector", "stock", "etf"]
    subject_id: str = Field(min_length=1)
    status: Literal["partial", "verified_scope"]
    evidence: list[Evidence]
    claims: list[Claim]
    holdings: list[HoldingsDisclosure]
    gaps: list[str]

    @model_validator(mode="after")
    def references(self) -> Self:
        ids = {e.id for e in self.evidence}
        if len(ids) != len(self.evidence):
            raise ValueError("duplicate evidence ID")
        if len({c.id for c in self.claims}) != len(self.claims):
            raise ValueError("duplicate claim ID")
        if any(not set(c.evidence_ids) <= ids for c in self.claims):
            raise ValueError("unknown claim evidence")
        if any(h.evidence_id not in ids for h in self.holdings):
            raise ValueError("unknown holdings evidence")
        if self.status == "partial" and not self.gaps:
            raise ValueError("partial package requires gaps")
        if self.status == "verified_scope" and (not self.evidence or self.gaps):
            raise ValueError("verified scope requires evidence and no open gaps")
        return self


class ContractError(ContractModel):
    code: Literal[
        "PACKAGE_NOT_FOUND", "SOURCE_UNAVAILABLE", "VALIDATION_ERROR", "IDEMPOTENCY_CONFLICT"
    ]
    message: str
    retryable: bool
    retry_after_seconds: int | None = Field(ge=1)

    @model_validator(mode="after")
    def retry_policy(self) -> Self:
        expected = self.code == "SOURCE_UNAVAILABLE"
        if self.retryable != expected or (self.retry_after_seconds is not None and not expected):
            raise ValueError("retry policy contradicts error code")
        return self


class ResearchRequest(ContractModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    evidence_package_id: str = Field(min_length=1)
    subject_kind: Literal["sector", "stock", "etf"]
    subject_id: str = Field(min_length=1)
    max_cost_cny: Decimal = Field(gt=0)


class ResearchResult(ContractModel):
    evidence_package_id: str
    subject_kind: Literal["sector", "stock", "etf"]
    subject_id: str
    claims: list[Claim]
    conditions: list[str]
    counterarguments: list[str]
    gaps: list[str]
    generated_at: AwareDatetime
    model: str
    prompt_version: str
    estimated_cost_cny: Decimal = Field(ge=0)


class JobError(ContractModel):
    code: Literal["SOURCE_UNAVAILABLE", "BUDGET_EXCEEDED", "MODEL_FAILED", "INTERRUPTED"]
    message: str
    retryable: bool

    @model_validator(mode="after")
    def retry_policy(self) -> Self:
        if self.retryable != (self.code in {"SOURCE_UNAVAILABLE", "MODEL_FAILED", "INTERRUPTED"}):
            raise ValueError("invalid job retry policy")
        return self


class ResearchJob(ContractModel):
    job_id: str = Field(min_length=1)
    status: Literal["queued", "running", "succeeded", "failed"]
    result: ResearchResult | None
    error: JobError | None

    @model_validator(mode="after")
    def terminal_payload(self) -> Self:
        if (self.status == "succeeded") != (self.result is not None):
            raise ValueError("only succeeded jobs have a result")
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("only failed jobs have an error")
        return self


class TradingRule(ContractModel):
    evidence_id: str
    version: str
    effective_from: date
    effective_until: date | None
    min_quantity: int = Field(gt=0)
    quantity_step: int = Field(gt=0)
    max_quantity: int = Field(gt=0)
    price_tick_cny: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.max_quantity < self.min_quantity:
            raise ValueError("invalid quantity bounds")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("invalid rule dates")
        return self


class FeeSchedule(ContractModel):
    # Explicit all-in customer costs; no automatic exchange-fee addition.
    version: str
    source_reference: str = Field(min_length=1)
    verified_at: AwareDatetime
    commission_rate: Decimal = Field(ge=0, le=1)
    minimum_commission_cny: Decimal = Field(ge=0)
    additional_rate: Decimal = Field(ge=0, le=1)
    additional_fixed_cny: Decimal = Field(ge=0)
    includes_all_applicable_costs: Literal[True]


class ExecutionRequest(ContractModel):
    evidence_package_id: str
    instrument_kind: Literal["stock", "etf"]
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["SH", "SZ"]
    side: Literal["buy"] = "buy"
    order_type: Literal["limit"] = "limit"
    cash_available_cny: Decimal | None = Field(ge=0)
    user_budget_cny: Decimal | None = Field(gt=0)
    limit_price_cny: Decimal | None = Field(gt=0)
    quote_at: AwareDatetime | None
    permission_confirmed: bool | None
    rules: TradingRule | None
    fees: FeeSchedule | None


class ExecutionPreview(ContractModel):
    # A single-order affordability check, not portfolio suitability advice.
    status: Literal["ready", "blocked"]
    evidence_package_id: str
    quantity: int | None = Field(gt=0)
    estimated_cost: Decimal | None = Field(ge=0)
    remaining_cash: Decimal | None = Field(ge=0)
    gaps: list[str]

    @model_validator(mode="after")
    def no_false_precision(self) -> Self:
        amounts = (self.quantity, self.estimated_cost, self.remaining_cash)
        if self.status == "blocked" and (any(v is not None for v in amounts) or not self.gaps):
            raise ValueError("blocked preview must contain gaps and no amounts")
        if self.status == "ready" and (any(v is None for v in amounts) or self.gaps):
            raise ValueError("ready preview requires all amounts and no gaps")
        return self

"""Immutable contracts for the E0 validation-first benchmark."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
IDENTITY_SHA256_PATTERN = r"^[a-z0-9_-]+:sha256:[0-9a-f]{64}$"
ERROR_CODE_PATTERN = r"^[a-z][a-z0-9_]*$"


class MarketRegime(StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class RunnerId(StrEnum):
    A0 = "A0"
    A1 = "A1"
    B0 = "B0"
    B1 = "B1"
    B3 = "B3"


class DecisionAction(StrEnum):
    LONG = "LONG"
    CASH = "CASH"
    ABSTAIN = "ABSTAIN"


class RunnerStatus(StrEnum):
    COMPLETE = "COMPLETE"
    ABSTAIN = "ABSTAIN"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class ExperimentStatus(StrEnum):
    FROZEN = "FROZEN"
    RUNNING = "RUNNING"
    DECISIONS_COMPLETE = "DECISIONS_COMPLETE"
    LABELED = "LABELED"
    TERMINAL = "TERMINAL"
    INVALID = "INVALID"


class E0Verdict(StrEnum):
    INVALID = "INVALID"
    STOP_AND_ABLATE = "STOP_AND_ABLATE"
    EXPAND_SAMPLE = "EXPAND_SAMPLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="after")
    def reject_blank_or_padded_strings(self) -> Self:
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if isinstance(value, str) and (
                not value.strip() or value != value.strip()
            ):
                raise ValueError(
                    f"{field_name} must be non-blank and have no surrounding whitespace"
                )
        return self


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"strict JSON forbids non-finite constant {value}")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class RegimePolicy(_FrozenModel):
    version: str = Field(min_length=1)
    lookback_trading_days: int = Field(ge=20)
    trend_return_threshold: Decimal = Field(gt=0)
    sideways_abs_return_max: Decimal = Field(ge=0)
    high_volatility_threshold: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> Self:
        if self.sideways_abs_return_max >= self.trend_return_threshold:
            raise ValueError("sideways threshold must be below trend threshold")
        return self


class FeeProfile(_FrozenModel):
    version: str = Field(min_length=1)
    buy_commission_rate: Decimal = Field(ge=0)
    sell_commission_rate: Decimal = Field(ge=0)
    minimum_commission: Decimal = Field(ge=0)
    sell_stamp_tax_rate: Decimal = Field(ge=0)
    transfer_fee_rate: Decimal = Field(ge=0)
    slippage_rate: Decimal = Field(ge=0)


class PositionProfile(_FrozenModel):
    version: str = Field(min_length=1)
    initial_capital: Decimal = Field(gt=0)
    long_fraction: Decimal = Field(gt=0, le=1)


class ConfidencePolicy(_FrozenModel):
    version: str = Field(min_length=1)
    high_confidence_threshold: Decimal = Field(gt=0, le=1)
    ece_bucket_edges: tuple[Decimal, ...]
    expansion_sample_count: int = Field(ge=300, le=500)

    @model_validator(mode="after")
    def validate_bucket_edges(self) -> Self:
        if len(self.ece_bucket_edges) < 2:
            raise ValueError("ECE requires at least two bucket edges")
        if self.ece_bucket_edges[0] != 0 or self.ece_bucket_edges[-1] != 1:
            raise ValueError("ECE bucket edges must start at 0 and end at 1")
        if any(
            left >= right
            for left, right in zip(self.ece_bucket_edges, self.ece_bucket_edges[1:])
        ):
            raise ValueError("ECE bucket edges must be strictly increasing")
        return self


class A0RunnerConfig(_FrozenModel):
    version: str = Field(min_length=1)
    enable_risk: bool
    enable_trader: bool
    enable_reflection: bool
    enable_trust: bool
    enable_mirror: bool


class CandidateSnapshot(_FrozenModel):
    candidate_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    market: str = Field(min_length=1)
    decision_at: datetime
    membership_as_of: datetime
    membership_proof_id: str = Field(min_length=1)
    membership_proof_hash: str = Field(pattern=SHA256_PATTERN)
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=SHA256_PATTERN)
    return_dates: tuple[date, ...]
    return_closes: tuple[Decimal, ...]
    return_window_hash: str = Field(pattern=SHA256_PATTERN)
    entry_tradable: bool

    _aware_decision_at = field_validator("decision_at")(_require_aware)
    _aware_membership_as_of = field_validator("membership_as_of")(_require_aware)

    @model_validator(mode="after")
    def validate_return_window(self) -> Self:
        if len(self.return_dates) != len(self.return_closes):
            raise ValueError("return dates and closes must have equal length")
        if any(close <= 0 for close in self.return_closes):
            raise ValueError("return closes must be positive")
        return self


class FrozenEvidence(_FrozenModel):
    sample_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    as_of: datetime
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=SHA256_PATTERN)
    quote_json: str
    completed_klines_json: str
    news_json: str
    financials_json: str
    industry_json: str
    sentiment_json: str

    _aware_as_of = field_validator("as_of")(_require_aware)

    @field_validator(
        "quote_json",
        "completed_klines_json",
        "news_json",
        "financials_json",
        "industry_json",
        "sentiment_json",
    )
    @classmethod
    def validate_json_payload(cls, value: str) -> str:
        try:
            json.loads(
                value,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except json.JSONDecodeError as exc:
            raise ValueError("frozen evidence payload must be valid JSON") from exc
        return value


class E0Sample(_FrozenModel):
    sample_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    decision_at: datetime
    regime: MarketRegime
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=SHA256_PATTERN)

    _aware_decision_at = field_validator("decision_at")(_require_aware)


class E0Manifest(_FrozenModel):
    experiment_id: str = Field(min_length=1)
    created_at: datetime
    code_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    model_id: str = Field(min_length=1)
    a0_prompt_version: str = Field(min_length=1)
    a1_prompt_version: str = Field(min_length=1)
    random_seed: int
    regime_policy: RegimePolicy
    fee_profile: FeeProfile
    position_profile: PositionProfile
    confidence_policy: ConfidencePolicy
    a0_config: A0RunnerConfig
    decision_question: str = Field(min_length=1)
    runner_ids: tuple[RunnerId, ...]
    runner_versions: tuple[tuple[RunnerId, str], ...]
    runner_config_versions: tuple[tuple[RunnerId, str], ...]
    runner_prompt_versions: tuple[tuple[RunnerId, str], ...]
    primary_horizon: int
    auxiliary_horizons: tuple[int, ...]
    candidate_universe_hash: str = Field(pattern=SHA256_PATTERN)
    replacement_order: tuple[str, ...]
    samples: tuple[E0Sample, ...]
    stability_sample_ids: tuple[str, ...]
    fixture_mode: bool = False

    _aware_created_at = field_validator("created_at")(_require_aware)

    @model_validator(mode="after")
    def validate_registered_experiment(self) -> Self:
        if self.runner_ids != tuple(RunnerId):
            raise ValueError("runner_ids must be exactly A0, A1, B0, B1, B3")
        version_tables = {
            "runner_versions": self.runner_versions,
            "runner_config_versions": self.runner_config_versions,
            "runner_prompt_versions": self.runner_prompt_versions,
        }
        for table_name, entries in version_tables.items():
            if tuple(runner_id for runner_id, _ in entries) != tuple(RunnerId):
                raise ValueError(f"{table_name} must cover every runner exactly once")
            if any(not value.strip() or value != value.strip() for _, value in entries):
                raise ValueError(f"{table_name} values must be non-blank and unpadded")
        prompt_versions = dict(self.runner_prompt_versions)
        if (
            prompt_versions[RunnerId.A0] != self.a0_prompt_version
            or prompt_versions[RunnerId.A1] != self.a1_prompt_version
        ):
            raise ValueError("A0/A1 prompt versions must match frozen prompt identities")
        if dict(self.runner_config_versions)[RunnerId.A0] != self.a0_config.version:
            raise ValueError("A0 config version must match frozen A0 configuration")
        if self.primary_horizon != 5 or self.auxiliary_horizons != (1, 20):
            raise ValueError("E0 horizons must be primary 5 and auxiliary 1, 20")
        if not self.fixture_mode and len(self.samples) != 100:
            raise ValueError("real E0 manifest requires exactly 100 samples")
        sample_ids = [sample.sample_id for sample in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("sample IDs must be unique")
        candidate_ids = [sample.candidate_id for sample in self.samples]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        if len(self.stability_sample_ids) != len(set(self.stability_sample_ids)):
            raise ValueError("stability sample IDs must be unique")
        if not set(self.stability_sample_ids).issubset(sample_ids):
            raise ValueError("stability sample IDs must belong to manifest samples")
        if any(
            not candidate_id.strip() or candidate_id != candidate_id.strip()
            for candidate_id in self.replacement_order
        ):
            raise ValueError("replacement_order IDs must be non-blank and unpadded")
        if len(self.replacement_order) != len(set(self.replacement_order)):
            raise ValueError("replacement_order IDs must be unique")
        if not self.fixture_mode:
            if len(self.stability_sample_ids) != 20:
                raise ValueError("real E0 manifest requires exactly 20 stability samples")
            regime_counts = Counter(sample.regime for sample in self.samples)
            if any(regime_counts[regime] != 25 for regime in MarketRegime):
                raise ValueError("real E0 manifest requires exactly 25 samples per regime")
            symbol_counts = Counter(sample.symbol for sample in self.samples)
            if any(count > 2 for count in symbol_counts.values()):
                raise ValueError("real E0 manifest permits at most 2 samples per symbol")
            date_counts = Counter(sample.decision_at.date() for sample in self.samples)
            if any(count > 5 for count in date_counts.values()):
                raise ValueError("real E0 manifest permits at most 5 samples per trade date")
        return self


class RunnerContext(_FrozenModel):
    experiment_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    runner_id: RunnerId
    repetition: int = Field(ge=1, le=3)
    position_fraction: Decimal = Field(gt=0, le=1)
    model_id: str = Field(min_length=1)
    decision_question: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    timeout_seconds: Decimal = Field(gt=0)


class RunnerDecision(_FrozenModel):
    action: DecisionAction
    position_fraction: Decimal = Field(ge=0, le=1)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)
    error_code: str | None = Field(default=None, pattern=ERROR_CODE_PATTERN)
    raw_output_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model_cost: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)


class DecisionRecord(_FrozenModel):
    experiment_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    runner_id: RunnerId
    runner_version: str = Field(min_length=1)
    repetition: int = Field(ge=1, le=3)
    symbol: str = Field(pattern=r"^[0-9]{6}$")
    decision_at: datetime
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_hash: str = Field(pattern=SHA256_PATTERN)
    as_of: datetime
    action: DecisionAction
    position_fraction: Decimal = Field(ge=0, le=1)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    status: RunnerStatus
    error_code: str | None = Field(default=None, pattern=ERROR_CODE_PATTERN)
    reason: str = Field(min_length=1)
    raw_output_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    model_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    code_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    config_version: str = Field(min_length=1)
    regime_policy_version: str = Field(min_length=1)
    fee_profile_version: str = Field(min_length=1)
    position_profile_version: str = Field(min_length=1)
    confidence_policy_version: str = Field(min_length=1)
    configured_position_fraction: Decimal = Field(gt=0, le=1)
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model_cost: Decimal = Field(ge=0)
    freshness_seconds: int = Field(ge=0)

    _aware_decision_at = field_validator("decision_at")(_require_aware)
    _aware_as_of = field_validator("as_of")(_require_aware)
    _aware_started_at = field_validator("started_at")(_require_aware)
    _aware_finished_at = field_validator("finished_at")(_require_aware)

    @model_validator(mode="after")
    def validate_terminal_record(self) -> Self:
        if self.as_of > self.decision_at:
            raise ValueError("future evidence is forbidden")
        if self.decision_at - self.as_of != timedelta(seconds=self.freshness_seconds):
            raise ValueError("freshness_seconds must equal decision_at minus as_of")
        if self.action is DecisionAction.LONG and self.position_fraction <= 0:
            raise ValueError("LONG decision requires a positive position fraction")
        if (
            self.action is DecisionAction.LONG
            and self.position_fraction != self.configured_position_fraction
        ):
            raise ValueError("LONG decision must match configured position fraction")
        if self.action is not DecisionAction.LONG and self.position_fraction != 0:
            raise ValueError("CASH and ABSTAIN decisions require zero position")
        if self.status is RunnerStatus.COMPLETE:
            if self.action is DecisionAction.ABSTAIN:
                raise ValueError("COMPLETE decision cannot abstain")
            if self.error_code is not None:
                raise ValueError("COMPLETE decision cannot carry error_code")
        else:
            if self.action is not DecisionAction.ABSTAIN:
                raise ValueError("non-complete decision must abstain")
            if self.error_code is None:
                raise ValueError("non-complete decision requires error_code")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        return self


class HorizonLabel(_FrozenModel):
    horizon_days: int = Field(gt=0)
    market_return: Decimal | None
    long_net_return: Decimal | None
    entry_price: Decimal | None = Field(default=None, gt=0)
    exit_price: Decimal | None = Field(default=None, gt=0)
    tradable: bool
    error_code: str | None = Field(default=None, pattern=ERROR_CODE_PATTERN)

    @model_validator(mode="after")
    def validate_execution_outcome(self) -> Self:
        outcome = (
            self.market_return,
            self.long_net_return,
            self.entry_price,
            self.exit_price,
        )
        if self.tradable:
            if any(value is None for value in outcome):
                raise ValueError("tradable horizon requires prices and returns")
            if self.error_code is not None:
                raise ValueError("tradable horizon cannot carry error_code")
        else:
            if any(value is not None for value in outcome):
                raise ValueError("untradable horizon cannot carry prices or returns")
            if self.error_code is None:
                raise ValueError("untradable horizon requires error_code")
        return self


class LabelRecord(_FrozenModel):
    experiment_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    fee_profile_version: str = Field(min_length=1)
    position_profile_version: str = Field(min_length=1)
    labels: tuple[HorizonLabel, ...]

    @model_validator(mode="after")
    def validate_horizons(self) -> Self:
        if tuple(label.horizon_days for label in self.labels) != (1, 5, 20):
            raise ValueError("labels must contain exact horizons 1, 5, 20")
        return self


class RunnerMetrics(_FrozenModel):
    runner_id: RunnerId
    denominator: int = Field(ge=0)
    complete_count: int = Field(ge=0)
    abstain_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    timeout_count: int = Field(ge=0)
    direction_accuracy: Decimal | None = Field(default=None, ge=0, le=1)
    balanced_accuracy: Decimal | None = Field(default=None, ge=0, le=1)
    brier_score: Decimal | None = Field(default=None, ge=0)
    ece: Decimal | None = Field(default=None, ge=0)
    net_return: Decimal | None = None
    max_drawdown: Decimal | None = Field(default=None, ge=0)
    model_cost: Decimal = Field(ge=0)


class PairwiseMetrics(_FrozenModel):
    left_runner_id: RunnerId
    right_runner_id: RunnerId
    denominator: int = Field(ge=0)
    executable_pairs: int = Field(ge=0)
    net_return_delta: Decimal | None = None
    brier_delta: Decimal | None = None


class StabilityMetrics(_FrozenModel):
    runner_id: RunnerId
    sample_count: int = Field(ge=0)
    expected_repetitions: int = Field(ge=1)
    complete_repetitions: int = Field(ge=0)
    direction_agreement: Decimal | None = Field(default=None, ge=0, le=1)
    position_range: Decimal | None = Field(default=None, ge=0)
    confidence_stddev: Decimal | None = Field(default=None, ge=0)
    failure_count: int = Field(ge=0)
    timeout_count: int = Field(ge=0)


class E0IntegrityReport(_FrozenModel):
    valid: bool
    checks: tuple[str, ...]
    reasons: tuple[str, ...]
    missing_decision_keys: tuple[str, ...] = ()
    unexpected_decision_keys: tuple[str, ...] = ()
    missing_label_keys: tuple[str, ...] = ()


class E0Adjudication(_FrozenModel):
    verdict: E0Verdict
    reasons: tuple[str, ...]
    predicates: tuple[tuple[str, bool], ...]


class E0Report(_FrozenModel):
    experiment_id: str = Field(min_length=1)
    manifest_hash: str = Field(pattern=IDENTITY_SHA256_PATTERN)
    generated_at: datetime
    primary_horizon: int
    runner_metrics: tuple[RunnerMetrics, ...]
    pairwise_metrics: tuple[PairwiseMetrics, ...]
    stability_metrics: tuple[StabilityMetrics, ...]
    integrity: E0IntegrityReport
    adjudication: E0Adjudication

    _aware_generated_at = field_validator("generated_at")(_require_aware)

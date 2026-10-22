"""Deterministic long-or-cash runners for the E0 benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from src.backtest.e0.models import (
    DecisionAction,
    E0Sample,
    FrozenEvidence,
    RunnerContext,
    RunnerDecision,
    RunnerId,
)

REQUIRED_MOMENTUM_PRICES = 21


class E0RunnerEvidenceError(ValueError):
    """Stable failure raised when frozen runner evidence is unusable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class E0Runner(Protocol):
    """Common asynchronous interface for every E0 participant."""

    runner_id: RunnerId
    version: str

    async def run(
        self,
        sample: E0Sample,
        evidence: FrozenEvidence,
        context: RunnerContext,
    ) -> RunnerDecision: ...


def _validate_version(version: str) -> None:
    if not version.strip() or version != version.strip():
        raise ValueError("runner version must be non-blank and unpadded")


def _validate_inputs(
    runner_id: RunnerId,
    sample: E0Sample,
    evidence: FrozenEvidence,
    context: RunnerContext,
) -> None:
    expected_sample_id = f"{context.experiment_id}:{sample.candidate_id}"
    if (
        context.runner_id is not runner_id
        or context.sample_id != sample.sample_id
        or sample.sample_id != expected_sample_id
    ):
        raise E0RunnerEvidenceError(
            "runner_context_mismatch",
            "runner context does not match the participant and sample",
        )
    if (
        evidence.sample_id != sample.sample_id
        or evidence.symbol != sample.symbol
        or evidence.evidence_snapshot_id != sample.evidence_snapshot_id
        or evidence.evidence_hash != sample.evidence_hash
    ):
        raise E0RunnerEvidenceError(
            "evidence_identity_mismatch",
            "frozen evidence identity does not match the sample",
        )
    if evidence.as_of > sample.decision_at:
        raise E0RunnerEvidenceError(
            "future_evidence_forbidden",
            "frozen evidence must not be newer than the decision",
        )


def _completed_closes(sample: E0Sample, evidence: FrozenEvidence) -> tuple[Decimal, ...]:
    payload = json.loads(evidence.completed_klines_json)
    if not isinstance(payload, list):
        raise E0RunnerEvidenceError(
            "completed_bars_shape_invalid",
            "completed K-lines must be a JSON list",
        )

    parsed: list[tuple[date, Decimal]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise E0RunnerEvidenceError(
                "completed_bars_shape_invalid",
                "every completed K-line must be an object",
            )
        try:
            bar_date = date.fromisoformat(item["date"])
            close = Decimal(str(item["close"]))
        except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
            raise E0RunnerEvidenceError(
                "completed_bars_shape_invalid",
                "completed K-line date and close must be valid",
            ) from exc
        if not close.is_finite() or close <= 0:
            raise E0RunnerEvidenceError(
                "completed_bar_price_invalid",
                "completed K-line close must be positive",
            )
        if bar_date >= sample.decision_at.date():
            raise E0RunnerEvidenceError(
                "future_bar_forbidden",
                "completed K-lines must predate the decision",
            )
        if bar_date >= evidence.as_of.date():
            raise E0RunnerEvidenceError(
                "bar_after_evidence_as_of",
                "date-only K-lines must predate the frozen evidence snapshot",
            )
        parsed.append((bar_date, close))

    if len(parsed) < REQUIRED_MOMENTUM_PRICES:
        raise E0RunnerEvidenceError(
            "insufficient_completed_bars",
            "20-session momentum requires 21 completed closing prices",
        )
    if any(
        left_date >= right_date
        for (left_date, _), (right_date, _) in zip(parsed, parsed[1:])
    ):
        raise E0RunnerEvidenceError(
            "completed_bar_order_invalid",
            "completed K-lines must have unique ascending dates",
        )
    return tuple(close for _, close in parsed)


def _decision(
    action: DecisionAction,
    position_fraction: Decimal,
    reason: str,
) -> RunnerDecision:
    return RunnerDecision(
        action=action,
        position_fraction=position_fraction,
        confidence=None,
        reason=reason,
        error_code=None,
        raw_output_hash=None,
        input_tokens=0,
        output_tokens=0,
        model_cost=Decimal(0),
        latency_ms=0,
    )


@dataclass(frozen=True, slots=True)
class CashRunner:
    """B0: remain in cash for every valid frozen sample."""

    version: str
    runner_id: RunnerId = field(default=RunnerId.B0, init=False)

    def __post_init__(self) -> None:
        _validate_version(self.version)

    async def run(
        self,
        sample: E0Sample,
        evidence: FrozenEvidence,
        context: RunnerContext,
    ) -> RunnerDecision:
        _validate_inputs(self.runner_id, sample, evidence, context)
        return _decision(DecisionAction.CASH, Decimal(0), "deterministic cash baseline")


@dataclass(frozen=True, slots=True)
class BuyHoldRunner:
    """B1: buy at the registered position only when entry is tradable."""

    version: str
    runner_id: RunnerId = field(default=RunnerId.B1, init=False)

    def __post_init__(self) -> None:
        _validate_version(self.version)

    async def run(
        self,
        sample: E0Sample,
        evidence: FrozenEvidence,
        context: RunnerContext,
    ) -> RunnerDecision:
        _validate_inputs(self.runner_id, sample, evidence, context)
        _completed_closes(sample, evidence)
        if sample.entry_tradable:
            return _decision(
                DecisionAction.LONG,
                context.position_fraction,
                "entry tradable in frozen decision-time proof",
            )
        return _decision(
            DecisionAction.CASH,
            Decimal(0),
            "entry untradable in frozen decision-time proof",
        )


@dataclass(frozen=True, slots=True)
class Momentum20Runner:
    """B3: hold long only when the frozen 20-session return is positive."""

    version: str
    runner_id: RunnerId = field(default=RunnerId.B3, init=False)

    def __post_init__(self) -> None:
        _validate_version(self.version)

    async def run(
        self,
        sample: E0Sample,
        evidence: FrozenEvidence,
        context: RunnerContext,
    ) -> RunnerDecision:
        _validate_inputs(self.runner_id, sample, evidence, context)
        closes = _completed_closes(sample, evidence)
        if closes[-1] > closes[-REQUIRED_MOMENTUM_PRICES]:
            return _decision(
                DecisionAction.LONG,
                context.position_fraction,
                "positive frozen 20-session return",
            )
        return _decision(
            DecisionAction.CASH,
            Decimal(0),
            "non-positive frozen 20-session return",
        )

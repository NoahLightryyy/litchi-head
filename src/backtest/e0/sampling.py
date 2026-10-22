"""Point-in-time regime classification and deterministic E0 sampling."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from src.backtest.e0.hashing import sha256_identity
from src.backtest.e0.models import (
    A0RunnerConfig,
    CandidateSnapshot,
    ConfidencePolicy,
    E0Manifest,
    E0Sample,
    FeeProfile,
    MarketRegime,
    PositionProfile,
    RegimePolicy,
    RunnerId,
)


class E0SamplingError(ValueError):
    """Stable candidate classification or manifest selection failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


E0_DECIMAL_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
)


def _window_payload(candidate: CandidateSnapshot) -> dict[str, list[str]]:
    return {
        "dates": [item.isoformat() for item in candidate.return_dates],
        "closes": [str(item) for item in candidate.return_closes],
    }


def classify_regime(
    candidate: CandidateSnapshot,
    policy: RegimePolicy,
) -> MarketRegime:
    """Classify one candidate using only its frozen pre-decision window."""

    required_prices = policy.lookback_trading_days + 1
    if len(candidate.return_closes) < required_prices:
        raise E0SamplingError(
            "regime_window_too_short",
            f"candidate requires at least {required_prices} closes",
        )
    if len(candidate.return_dates) != len(candidate.return_closes):
        raise E0SamplingError("regime_window_shape_invalid", "date/close lengths differ")
    if len(candidate.return_dates) != len(set(candidate.return_dates)):
        raise E0SamplingError("regime_duplicate_date", "return window contains duplicate dates")
    if any(day >= candidate.decision_at.date() for day in candidate.return_dates):
        raise E0SamplingError("regime_future_data", "return window reaches decision time")
    if any(
        left >= right
        for left, right in zip(candidate.return_dates, candidate.return_dates[1:])
    ):
        raise E0SamplingError("regime_date_order_invalid", "return dates are not ordered")
    if candidate.membership_as_of >= candidate.decision_at:
        raise E0SamplingError(
            "membership_future_data",
            "membership proof must predate the decision",
        )
    if any(close <= 0 for close in candidate.return_closes):
        raise E0SamplingError("regime_price_invalid", "return closes must be positive")
    if sha256_identity("return-window", _window_payload(candidate)) != (
        candidate.return_window_hash
    ):
        raise E0SamplingError(
            "regime_window_hash_mismatch",
            "return window hash does not match its content",
        )

    closes = candidate.return_closes[-required_prices:]
    with localcontext(E0_DECIMAL_CONTEXT):
        lookback_return = closes[-1] / closes[0] - Decimal(1)
        daily_returns = tuple(
            current / previous - Decimal(1)
            for previous, current in zip(closes, closes[1:])
        )
        mean_return = sum(daily_returns, Decimal(0)) / Decimal(len(daily_returns))
        sample_variance = sum(
            ((value - mean_return) ** 2 for value in daily_returns),
            Decimal(0),
        ) / Decimal(len(daily_returns) - 1)
        annualized_volatility = Decimal(
            str(math.sqrt(float(sample_variance)) * math.sqrt(252.0))
        )

        if annualized_volatility >= policy.high_volatility_threshold:
            return MarketRegime.HIGH_VOLATILITY
        if lookback_return >= policy.trend_return_threshold:
            return MarketRegime.UP
        if lookback_return <= -policy.trend_return_threshold:
            return MarketRegime.DOWN
        if abs(lookback_return) <= policy.sideways_abs_return_max:
            return MarketRegime.SIDEWAYS
    raise E0SamplingError(
        "regime_unclassified",
        "candidate falls outside every registered regime",
    )


def _bare_identity(prefix: str, value: object) -> str:
    identity = sha256_identity(prefix, value)
    return identity.removeprefix(f"{prefix}:")


def freeze_samples(
    candidates: Sequence[CandidateSnapshot],
    *,
    experiment_id: str,
    created_at: datetime,
    regime_policy: RegimePolicy,
    fee_profile: FeeProfile,
    position_profile: PositionProfile,
    confidence_policy: ConfidencePolicy,
    a0_config: A0RunnerConfig,
    decision_question: str,
    runner_versions: tuple[tuple[RunnerId, str], ...],
    runner_config_versions: tuple[tuple[RunnerId, str], ...],
    runner_prompt_versions: tuple[tuple[RunnerId, str], ...],
    code_commit: str,
    model_id: str,
    a0_prompt_version: str,
    a1_prompt_version: str,
    random_seed: int,
) -> E0Manifest:
    """Freeze one official deterministic 25-by-4 E0 manifest."""

    ordered_candidates = tuple(sorted(candidates, key=lambda item: item.candidate_id))
    candidate_ids = [candidate.candidate_id for candidate in ordered_candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise E0SamplingError(
            "duplicate_candidate_id",
            "candidate universe contains duplicate identities",
        )
    semantic_identities = [
        (
            candidate.symbol,
            candidate.decision_at,
            candidate.evidence_snapshot_id,
            candidate.evidence_hash,
        )
        for candidate in ordered_candidates
    ]
    if len(semantic_identities) != len(set(semantic_identities)):
        raise E0SamplingError(
            "duplicate_candidate_identity",
            "candidate universe contains duplicate semantic identities",
        )

    valid: list[tuple[CandidateSnapshot, MarketRegime]] = []
    exclusions: list[tuple[str, str]] = []
    for candidate in ordered_candidates:
        try:
            valid.append((candidate, classify_regime(candidate, regime_policy)))
        except E0SamplingError as exc:
            exclusions.append((candidate.candidate_id, exc.code))

    shuffled = list(valid)
    random.Random(random_seed).shuffle(shuffled)
    selected: list[tuple[CandidateSnapshot, MarketRegime]] = []
    selected_ids: set[str] = set()
    regime_counts: Counter[MarketRegime] = Counter()
    symbol_counts: Counter[str] = Counter()
    date_counts: Counter[date] = Counter()
    for candidate, regime in shuffled:
        decision_day = candidate.decision_at.date()
        if regime_counts[regime] >= 25:
            continue
        if symbol_counts[candidate.symbol] >= 2 or date_counts[decision_day] >= 5:
            continue
        selected.append((candidate, regime))
        selected_ids.add(candidate.candidate_id)
        regime_counts[regime] += 1
        symbol_counts[candidate.symbol] += 1
        date_counts[decision_day] += 1

    if any(regime_counts[regime] != 25 for regime in MarketRegime):
        raise E0SamplingError(
            "insufficient_regime_candidates",
            "candidate universe cannot satisfy the registered 25-by-4 quotas",
        )

    samples = tuple(
        E0Sample(
            sample_id=f"{experiment_id}:{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            symbol=candidate.symbol,
            decision_at=candidate.decision_at,
            regime=regime,
            evidence_snapshot_id=candidate.evidence_snapshot_id,
            evidence_hash=candidate.evidence_hash,
            entry_tradable=candidate.entry_tradable,
        )
        for candidate, regime in selected
    )
    replacement_order = tuple(
        candidate.candidate_id
        for candidate, _ in shuffled
        if candidate.candidate_id not in selected_ids
    )
    stability_ids = [sample.sample_id for sample in samples]
    random.Random(random_seed ^ 0xE0).shuffle(stability_ids)

    return E0Manifest(
        experiment_id=experiment_id,
        created_at=created_at,
        code_commit=code_commit,
        model_id=model_id,
        a0_prompt_version=a0_prompt_version,
        a1_prompt_version=a1_prompt_version,
        random_seed=random_seed,
        regime_policy=regime_policy,
        fee_profile=fee_profile,
        position_profile=position_profile,
        confidence_policy=confidence_policy,
        a0_config=a0_config,
        decision_question=decision_question,
        runner_ids=tuple(RunnerId),
        runner_versions=runner_versions,
        runner_config_versions=runner_config_versions,
        runner_prompt_versions=runner_prompt_versions,
        primary_horizon=5,
        auxiliary_horizons=(1, 20),
        candidate_universe_hash=_bare_identity(
            "candidate-universe", ordered_candidates
        ),
        candidate_exclusions=tuple(exclusions),
        replacement_order=replacement_order,
        samples=samples,
        stability_sample_ids=tuple(stability_ids[:20]),
        fixture_mode=False,
    )

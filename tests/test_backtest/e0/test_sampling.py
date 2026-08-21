from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal, localcontext

import pytest

from src.backtest.e0.hashing import sha256_identity
from src.backtest.e0.models import (
    A0RunnerConfig,
    CandidateSnapshot,
    ConfidencePolicy,
    FeeProfile,
    MarketRegime,
    PositionProfile,
    RegimePolicy,
    RunnerId,
)
from src.backtest.e0.sampling import (
    E0SamplingError,
    classify_regime,
    freeze_samples,
)

CREATED_AT = datetime(2026, 8, 21, 3, 0, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"


def _policy() -> RegimePolicy:
    return RegimePolicy(
        version="regime:v1",
        lookback_trading_days=20,
        trend_return_threshold=Decimal("0.08"),
        sideways_abs_return_max=Decimal("0.02"),
        high_volatility_threshold=Decimal("0.35"),
    )


def _closes(regime: MarketRegime | None) -> tuple[Decimal, ...]:
    if regime is MarketRegime.UP:
        return tuple(Decimal("100") + Decimal(index) / 2 for index in range(21))
    if regime is MarketRegime.DOWN:
        return tuple(Decimal("100") - Decimal(index) / 2 for index in range(21))
    if regime is MarketRegime.SIDEWAYS:
        return (Decimal("100"),) * 21
    if regime is MarketRegime.HIGH_VOLATILITY:
        return tuple(Decimal("130") if index % 2 else Decimal("100") for index in range(21))
    return tuple(Decimal("100") + Decimal(index) * Decimal("0.15") for index in range(21))


def _candidate(
    candidate_id: str,
    regime: MarketRegime | None,
    *,
    symbol: str = "000001",
    decision_day: date = date(2026, 1, 30),
    closes: tuple[Decimal, ...] | None = None,
    return_dates: tuple[date, ...] | None = None,
    return_window_hash: str | None = None,
) -> CandidateSnapshot:
    window_closes = closes or _closes(regime)
    window_dates = return_dates or tuple(
        decision_day - timedelta(days=21 - index) for index in range(21)
    )
    window_payload = {
        "dates": [item.isoformat() for item in window_dates],
        "closes": [str(item) for item in window_closes],
    }
    return CandidateSnapshot(
        candidate_id=candidate_id,
        symbol=symbol,
        market="SZSE",
        decision_at=datetime.combine(decision_day, datetime.min.time(), tzinfo=UTC),
        membership_as_of=datetime.combine(
            decision_day - timedelta(days=1), datetime.min.time(), tzinfo=UTC
        ),
        membership_proof_id=f"membership:{candidate_id}",
        membership_proof_hash=HASH,
        evidence_snapshot_id=f"evidence:{candidate_id}",
        evidence_hash=HASH,
        return_dates=window_dates,
        return_closes=window_closes,
        return_window_hash=return_window_hash or sha256_identity("return-window", window_payload),
        entry_tradable=True,
    )


@pytest.mark.parametrize(
    ("regime", "expected"),
    [
        (MarketRegime.UP, MarketRegime.UP),
        (MarketRegime.DOWN, MarketRegime.DOWN),
        (MarketRegime.SIDEWAYS, MarketRegime.SIDEWAYS),
        (MarketRegime.HIGH_VOLATILITY, MarketRegime.HIGH_VOLATILITY),
    ],
)
def test_classify_regime_uses_registered_precedence(
    regime: MarketRegime,
    expected: MarketRegime,
) -> None:
    assert classify_regime(_candidate("candidate", regime), _policy()) is expected


def test_classify_regime_rejects_unclassified_candidate() -> None:
    with pytest.raises(E0SamplingError) as exc_info:
        classify_regime(_candidate("candidate", None), _policy())

    assert exc_info.value.code == "regime_unclassified"


def test_classify_regime_rejects_short_window() -> None:
    closes = _closes(MarketRegime.UP)[:-1]
    dates = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(20))

    with pytest.raises(E0SamplingError) as exc_info:
        classify_regime(
            _candidate("candidate", MarketRegime.UP, closes=closes, return_dates=dates),
            _policy(),
        )

    assert exc_info.value.code == "regime_window_too_short"


def test_classify_regime_rejects_future_or_duplicate_dates() -> None:
    candidate = _candidate("candidate", MarketRegime.UP)
    future_dates = (*candidate.return_dates[:-1], candidate.decision_at.date())
    duplicate_dates = (*candidate.return_dates[:-1], candidate.return_dates[-2])

    with pytest.raises(E0SamplingError) as future_error:
        classify_regime(candidate.model_copy(update={"return_dates": future_dates}), _policy())
    with pytest.raises(E0SamplingError) as duplicate_error:
        classify_regime(candidate.model_copy(update={"return_dates": duplicate_dates}), _policy())

    assert future_error.value.code == "regime_future_data"
    assert duplicate_error.value.code == "regime_duplicate_date"


def test_classify_regime_rejects_window_hash_mismatch() -> None:
    with pytest.raises(E0SamplingError) as exc_info:
        classify_regime(
            _candidate(
                "candidate",
                MarketRegime.UP,
                return_window_hash=sha256_identity("return-window", {"wrong": True}),
            ),
            _policy(),
        )

    assert exc_info.value.code == "regime_window_hash_mismatch"


def test_classify_regime_ignores_ambient_decimal_precision() -> None:
    closes = (Decimal("100"),) * 20 + (Decimal("107.999999995"),)
    candidate = _candidate("candidate", None, closes=closes)

    with localcontext() as low_precision:
        low_precision.prec = 6
        try:
            low_result: MarketRegime | str = classify_regime(candidate, _policy())
        except E0SamplingError as exc:
            low_result = exc.code
    with localcontext() as high_precision:
        high_precision.prec = 50
        try:
            high_result: MarketRegime | str = classify_regime(candidate, _policy())
        except E0SamplingError as exc:
            high_result = exc.code

    assert low_result == high_result == "regime_unclassified"


def test_classify_regime_ignores_ambient_decimal_rounding() -> None:
    closes = (Decimal("100"),) * 20 + (Decimal(f"107.{'9' * 60}"),)
    candidate = _candidate("candidate", None, closes=closes)

    outcomes: list[MarketRegime | str] = []
    for rounding in (ROUND_DOWN, ROUND_CEILING):
        with localcontext() as ambient_context:
            ambient_context.prec = 6
            ambient_context.rounding = rounding
            try:
                outcomes.append(classify_regime(candidate, _policy()))
            except E0SamplingError as exc:
                outcomes.append(exc.code)

    assert outcomes == [MarketRegime.UP, MarketRegime.UP]


def _candidate_universe() -> tuple[CandidateSnapshot, ...]:
    candidates: list[CandidateSnapshot] = []
    regimes = tuple(MarketRegime)
    for regime_index, regime in enumerate(regimes):
        for local_index in range(35):
            candidates.append(
                _candidate(
                    f"{regime.value.lower()}-{local_index:02d}",
                    regime,
                    symbol=f"{regime_index * 100 + local_index % 20 + 1:06d}",
                    decision_day=date(2025, 1, 10)
                    + timedelta(days=regime_index * 10 + local_index % 5),
                )
            )
    return tuple(candidates)


def _freeze_kwargs() -> dict[str, object]:
    return {
        "experiment_id": "e0-official",
        "created_at": CREATED_AT,
        "regime_policy": _policy(),
        "fee_profile": FeeProfile(
            version="fees:v1",
            buy_commission_rate=Decimal("0.0003"),
            sell_commission_rate=Decimal("0.0003"),
            minimum_commission=Decimal("5"),
            sell_stamp_tax_rate=Decimal("0.0005"),
            transfer_fee_rate=Decimal("0.00001"),
            slippage_rate=Decimal("0.001"),
        ),
        "position_profile": PositionProfile(
            version="position:v1",
            initial_capital=Decimal("100000"),
            long_fraction=Decimal("0.25"),
        ),
        "confidence_policy": ConfidencePolicy(
            version="confidence:v1",
            high_confidence_threshold=Decimal("0.8"),
            ece_bucket_edges=(Decimal("0"), Decimal("0.5"), Decimal("1")),
            expansion_sample_count=300,
        ),
        "a0_config": A0RunnerConfig(
            version="a0:v1",
            enable_risk=True,
            enable_trader=True,
            enable_reflection=True,
            enable_trust=True,
            enable_mirror=True,
        ),
        "decision_question": "未来五个交易日是否应持有该股票？",
        "runner_versions": tuple(
            (runner_id, f"{runner_id.value.lower()}:v1") for runner_id in RunnerId
        ),
        "runner_config_versions": (
            (RunnerId.A0, "a0:v1"),
            (RunnerId.A1, "a1-config:v1"),
            (RunnerId.B0, "b0-config:v1"),
            (RunnerId.B1, "b1-config:v1"),
            (RunnerId.B3, "b3-config:v1"),
        ),
        "runner_prompt_versions": (
            (RunnerId.A0, "production:abc1234"),
            (RunnerId.A1, "e0-single-agent:v1"),
            (RunnerId.B0, "not-applicable:v1"),
            (RunnerId.B1, "not-applicable:v1"),
            (RunnerId.B3, "not-applicable:v1"),
        ),
        "code_commit": "abc1234",
        "model_id": "deepseek-chat",
        "a0_prompt_version": "production:abc1234",
        "a1_prompt_version": "e0-single-agent:v1",
        "random_seed": 20260821,
    }


def test_freeze_samples_builds_exact_deterministic_manifest() -> None:
    candidates = _candidate_universe()

    first = freeze_samples(candidates, **_freeze_kwargs())
    second = freeze_samples(tuple(reversed(candidates)), **_freeze_kwargs())

    assert first == second
    assert len(first.samples) == 100
    assert {
        regime: sum(sample.regime is regime for sample in first.samples) for regime in MarketRegime
    } == {
        MarketRegime.UP: 25,
        MarketRegime.DOWN: 25,
        MarketRegime.SIDEWAYS: 25,
        MarketRegime.HIGH_VOLATILITY: 25,
    }
    assert (
        max(
            sum(sample.symbol == symbol for sample in first.samples)
            for symbol in {sample.symbol for sample in first.samples}
        )
        <= 2
    )
    assert (
        max(
            sum(sample.decision_at.date() == day for sample in first.samples)
            for day in {sample.decision_at.date() for sample in first.samples}
        )
        <= 5
    )
    assert len(first.replacement_order) == 40
    assert len(first.stability_sample_ids) == 20
    assert first.candidate_universe_hash.startswith("sha256:")


def test_freeze_samples_records_stable_exclusions() -> None:
    candidates = (*_candidate_universe(), _candidate("unclassified", None))

    manifest = freeze_samples(candidates, **_freeze_kwargs())

    assert ("unclassified", "regime_unclassified") in manifest.candidate_exclusions


def test_freeze_samples_rejects_duplicate_semantic_candidate_identity() -> None:
    candidates = list(_candidate_universe())
    candidates.append(candidates[0].model_copy(update={"candidate_id": "duplicate-alias"}))

    with pytest.raises(E0SamplingError) as exc_info:
        freeze_samples(candidates, **_freeze_kwargs())

    assert exc_info.value.code == "duplicate_candidate_identity"


def test_freeze_samples_fails_when_a_regime_cannot_reach_quota() -> None:
    candidates = tuple(
        candidate
        for candidate in _candidate_universe()
        if not (
            candidate.candidate_id.startswith("up-")
            and int(candidate.candidate_id.rsplit("-", 1)[1]) >= 24
        )
    )

    with pytest.raises(E0SamplingError) as exc_info:
        freeze_samples(candidates, **_freeze_kwargs())

    assert exc_info.value.code == "insufficient_regime_candidates"

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.backtest.e0.hashing import canonical_json, sha256_identity
from src.backtest.e0.models import (
    A0RunnerConfig,
    ConfidencePolicy,
    DecisionAction,
    DecisionRecord,
    E0Manifest,
    E0Sample,
    FeeProfile,
    FrozenEvidence,
    HorizonLabel,
    LabelRecord,
    MarketRegime,
    PositionProfile,
    RegimePolicy,
    RunnerId,
    RunnerStatus,
)

AS_OF = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"


def _regime_policy() -> RegimePolicy:
    return RegimePolicy(
        version="regime:v1",
        lookback_trading_days=20,
        trend_return_threshold=Decimal("0.08"),
        sideways_abs_return_max=Decimal("0.02"),
        high_volatility_threshold=Decimal("0.35"),
    )


def _fee_profile() -> FeeProfile:
    return FeeProfile(
        version="fees:v1",
        buy_commission_rate=Decimal("0.0003"),
        sell_commission_rate=Decimal("0.0003"),
        minimum_commission=Decimal("5"),
        sell_stamp_tax_rate=Decimal("0.0005"),
        transfer_fee_rate=Decimal("0.00001"),
        slippage_rate=Decimal("0.001"),
    )


def _position_profile() -> PositionProfile:
    return PositionProfile(
        version="position:v1",
        initial_capital=Decimal("100000"),
        long_fraction=Decimal("0.25"),
    )


def _confidence_policy() -> ConfidencePolicy:
    return ConfidencePolicy(
        version="confidence:v1",
        high_confidence_threshold=Decimal("0.8"),
        ece_bucket_edges=(Decimal("0"), Decimal("0.5"), Decimal("1")),
        expansion_sample_count=300,
    )


def _manifest_values() -> dict[str, object]:
    return {
        "experiment_id": "e0-fixture",
        "created_at": AS_OF,
        "code_commit": "abc1234",
        "model_id": "deepseek-chat",
        "a0_prompt_version": "production:abc1234",
        "a1_prompt_version": "e0-single-agent:v1",
        "random_seed": 20260810,
        "regime_policy": _regime_policy(),
        "fee_profile": _fee_profile(),
        "position_profile": _position_profile(),
        "confidence_policy": _confidence_policy(),
        "a0_config": A0RunnerConfig(
            version="a0:v1",
            enable_risk=True,
            enable_trader=True,
            enable_reflection=True,
            enable_trust=True,
            enable_mirror=True,
        ),
        "decision_question": "未来五个交易日是否应持有该股票？",
        "runner_ids": tuple(RunnerId),
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
        "primary_horizon": 5,
        "auxiliary_horizons": (1, 20),
        "candidate_universe_hash": HASH,
        "candidate_exclusions": (),
        "replacement_order": (),
        "samples": (),
        "stability_sample_ids": (),
        "fixture_mode": True,
    }


def _decision_record(**updates: object) -> DecisionRecord:
    values: dict[str, object] = {
        "experiment_id": "e0-fixture",
        "sample_id": "sample-001",
        "runner_id": RunnerId.A0,
        "runner_version": "a0:v1",
        "repetition": 1,
        "symbol": "000001",
        "decision_at": AS_OF,
        "evidence_snapshot_id": "evidence-001",
        "evidence_hash": HASH,
        "as_of": AS_OF,
        "action": DecisionAction.LONG,
        "position_fraction": Decimal("0.25"),
        "confidence": Decimal("0.7"),
        "status": RunnerStatus.COMPLETE,
        "error_code": None,
        "reason": "positive frozen evidence",
        "raw_output_hash": HASH,
        "model_id": "deepseek-chat",
        "prompt_version": "production:abc1234",
        "code_commit": "abc1234",
        "config_version": "e0-config:v1",
        "regime_policy_version": "regime:v1",
        "fee_profile_version": "fees:v1",
        "position_profile_version": "position:v1",
        "confidence_policy_version": "confidence:v1",
        "configured_position_fraction": Decimal("0.25"),
        "started_at": AS_OF,
        "finished_at": AS_OF,
        "latency_ms": 0,
        "input_tokens": 10,
        "output_tokens": 5,
        "model_cost": Decimal("0.001"),
        "freshness_seconds": 0,
    }
    values.update(updates)
    return DecisionRecord.model_validate(values)


def _sample(
    index: int,
    regime: MarketRegime,
    *,
    symbol: str | None = None,
    decision_at: datetime | None = None,
    candidate_id: str | None = None,
) -> E0Sample:
    return E0Sample(
        sample_id=f"sample-{index:03d}",
        candidate_id=candidate_id or f"candidate-{index:03d}",
        symbol=symbol or f"{index // 2 + 1:06d}",
        decision_at=decision_at or AS_OF + timedelta(days=index // 5),
        regime=regime,
        evidence_snapshot_id=f"evidence-{index:03d}",
        evidence_hash=HASH,
        entry_tradable=True,
    )


def _real_samples() -> tuple[E0Sample, ...]:
    regimes = tuple(MarketRegime)
    return tuple(_sample(index, regimes[index // 25]) for index in range(100))


def _horizon_label(horizon_days: int) -> HorizonLabel:
    return HorizonLabel(
        horizon_days=horizon_days,
        market_return=Decimal("0.01"),
        long_net_return=Decimal("0.009"),
        entry_price=Decimal("10"),
        exit_price=Decimal("10.1"),
        tradable=True,
        error_code=None,
    )


def test_canonical_identity_ignores_mapping_order() -> None:
    left = sha256_identity("manifest", {"b": 2, "a": 1})
    right = sha256_identity("manifest", {"a": 1, "b": 2})

    assert left == right
    assert left.startswith("manifest:sha256:")


def test_canonical_json_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": float("nan")})


def test_real_manifest_requires_every_explicit_policy() -> None:
    values = _manifest_values()
    values.pop("fee_profile")

    with pytest.raises(ValidationError) as exc_info:
        E0Manifest.model_validate(values)

    assert exc_info.value.errors()[0]["loc"] == ("fee_profile",)


def test_fixture_manifest_accepts_explicit_policies_and_fewer_samples() -> None:
    manifest = E0Manifest.model_validate(_manifest_values())

    assert manifest.fixture_mode is True
    assert manifest.runner_ids == tuple(RunnerId)


@pytest.mark.parametrize(
    "replacement_order",
    [("candidate-good", "   "), ("candidate-good", "candidate-good")],
)
def test_manifest_rejects_invalid_replacement_identity(
    replacement_order: tuple[str, ...],
) -> None:
    values = _manifest_values()
    values["replacement_order"] = replacement_order

    with pytest.raises(ValidationError, match="replacement_order"):
        E0Manifest.model_validate(values)


@pytest.mark.parametrize(
    "mutation",
    [
        "regime_quota",
        "symbol_cap",
        "date_cap",
        "candidate_duplicate",
        "semantic_duplicate",
    ],
)
def test_real_manifest_rejects_invalid_official_sample_set(mutation: str) -> None:
    samples = list(_real_samples())
    if mutation == "regime_quota":
        samples[-1] = samples[-1].model_copy(update={"regime": MarketRegime.UP})
    elif mutation == "symbol_cap":
        samples[2] = samples[2].model_copy(update={"symbol": samples[0].symbol})
    elif mutation == "date_cap":
        samples[5] = samples[5].model_copy(update={"decision_at": samples[0].decision_at})
    elif mutation == "candidate_duplicate":
        samples[1] = samples[1].model_copy(
            update={"candidate_id": samples[0].candidate_id}
        )
    else:
        samples[1] = samples[1].model_copy(
            update={
                "symbol": samples[0].symbol,
                "decision_at": samples[0].decision_at,
                "evidence_snapshot_id": samples[0].evidence_snapshot_id,
                "evidence_hash": samples[0].evidence_hash,
            }
        )
    values = _manifest_values()
    values.update(
        {
            "fixture_mode": False,
            "samples": tuple(samples),
            "stability_sample_ids": tuple(
                sample.sample_id for sample in samples[:20]
            ),
        }
    )

    with pytest.raises(ValidationError):
        E0Manifest.model_validate(values)


@pytest.mark.parametrize(
    "candidate_exclusions",
    [
        (("candidate-001", "regime_unclassified"),),
        (("excluded-candidate", "Not stable prose code"),),
    ],
)
def test_manifest_rejects_contradictory_or_unstable_exclusions(
    candidate_exclusions: tuple[tuple[str, str], ...],
) -> None:
    values = _manifest_values()
    values.update(
        {
            "samples": (_sample(1, MarketRegime.UP),),
            "candidate_exclusions": candidate_exclusions,
        }
    )

    with pytest.raises(ValidationError, match="candidate exclusion"):
        E0Manifest.model_validate(values)


def test_decision_record_is_frozen() -> None:
    record = _decision_record()

    with pytest.raises(ValidationError):
        record.action = DecisionAction.CASH


@pytest.mark.parametrize("field", ["decision_at", "as_of", "started_at", "finished_at"])
def test_decision_record_rejects_naive_timestamps(field: str) -> None:
    with pytest.raises(ValidationError):
        _decision_record(**{field: AS_OF.replace(tzinfo=None)})


def test_decision_record_rejects_malformed_evidence_hash() -> None:
    with pytest.raises(ValidationError):
        _decision_record(evidence_hash="sha256:not-a-digest")


def test_decision_record_rejects_future_evidence() -> None:
    with pytest.raises(ValidationError, match="future evidence"):
        _decision_record(as_of=AS_OF + timedelta(seconds=1))


def test_decision_record_rejects_inconsistent_freshness() -> None:
    with pytest.raises(ValidationError, match="freshness_seconds"):
        _decision_record(as_of=AS_OF - timedelta(seconds=30), freshness_seconds=0)


@pytest.mark.parametrize("confidence", [Decimal("-0.01"), Decimal("1.01")])
def test_decision_record_rejects_confidence_outside_unit_interval(
    confidence: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        _decision_record(confidence=confidence)


def test_long_decision_requires_positive_position() -> None:
    with pytest.raises(ValidationError, match="LONG decision requires"):
        _decision_record(position_fraction=Decimal("0"))


def test_long_decision_must_match_manifest_position_fraction() -> None:
    with pytest.raises(ValidationError, match="configured position fraction"):
        _decision_record(position_fraction=Decimal("0.5"))


@pytest.mark.parametrize(
    ("status", "action"),
    [
        (RunnerStatus.ABSTAIN, DecisionAction.ABSTAIN),
        (RunnerStatus.FAILED, DecisionAction.ABSTAIN),
        (RunnerStatus.TIMEOUT, DecisionAction.ABSTAIN),
    ],
)
def test_non_complete_decision_requires_stable_error_code(
    status: RunnerStatus,
    action: DecisionAction,
) -> None:
    with pytest.raises(ValidationError, match="error_code"):
        _decision_record(
            status=status,
            action=action,
            position_fraction=Decimal("0"),
            confidence=None,
            error_code=None,
        )


@pytest.mark.parametrize("field", ["model_id", "decision_question", "code_commit"])
def test_manifest_rejects_blank_audit_identity(field: str) -> None:
    values = _manifest_values()
    values[field] = "       "

    with pytest.raises(ValidationError):
        E0Manifest.model_validate(values)


def test_frozen_evidence_rejects_invalid_json_payload() -> None:
    with pytest.raises(ValidationError, match="valid JSON"):
        FrozenEvidence(
            sample_id="sample-001",
            symbol="000001",
            as_of=AS_OF,
            evidence_snapshot_id="evidence-001",
            evidence_hash=HASH,
            quote_json="not-json",
            completed_klines_json="[]",
            news_json="[]",
            financials_json="{}",
            industry_json="{}",
            sentiment_json="{}",
        )


@pytest.mark.parametrize("invalid_json", ["NaN", "Infinity", "-Infinity"])
def test_frozen_evidence_rejects_non_finite_json(invalid_json: str) -> None:
    with pytest.raises(ValidationError, match="strict JSON"):
        FrozenEvidence(
            sample_id="sample-001",
            symbol="000001",
            as_of=AS_OF,
            evidence_snapshot_id="evidence-001",
            evidence_hash=HASH,
            quote_json=invalid_json,
            completed_klines_json="[]",
            news_json="[]",
            financials_json="{}",
            industry_json="{}",
            sentiment_json="{}",
        )


def test_frozen_evidence_rejects_duplicate_json_keys() -> None:
    with pytest.raises(ValidationError, match="duplicate JSON key"):
        FrozenEvidence(
            sample_id="sample-001",
            symbol="000001",
            as_of=AS_OF,
            evidence_snapshot_id="evidence-001",
            evidence_hash=HASH,
            quote_json='{"price":10,"price":11}',
            completed_klines_json="[]",
            news_json="[]",
            financials_json="{}",
            industry_json="{}",
            sentiment_json="{}",
        )


def test_untradable_horizon_rejects_prices_and_returns() -> None:
    with pytest.raises(ValidationError, match="untradable"):
        HorizonLabel(
            horizon_days=5,
            market_return=Decimal("0.01"),
            long_net_return=None,
            entry_price=None,
            exit_price=None,
            tradable=False,
            error_code="entry_suspended",
        )


def test_tradable_horizon_requires_prices_and_returns() -> None:
    with pytest.raises(ValidationError, match="tradable"):
        HorizonLabel(
            horizon_days=5,
            market_return=None,
            long_net_return=None,
            entry_price=None,
            exit_price=None,
            tradable=True,
            error_code=None,
        )


@pytest.mark.parametrize(
    "labels",
    [
        (),
        (_horizon_label(1), _horizon_label(5), _horizon_label(5)),
        (_horizon_label(1), _horizon_label(5), _horizon_label(10)),
    ],
)
def test_label_record_requires_exact_unique_horizons(
    labels: tuple[HorizonLabel, ...],
) -> None:
    with pytest.raises(ValidationError, match="1, 5, 20"):
        LabelRecord(
            experiment_id="e0-fixture",
            sample_id="sample-001",
            evidence_snapshot_id="evidence-001",
            fee_profile_version="fees:v1",
            position_profile_version="position:v1",
            labels=labels,
        )

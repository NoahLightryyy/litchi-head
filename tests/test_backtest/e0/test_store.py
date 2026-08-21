from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from src.backtest.e0.hashing import canonical_json, sha256_identity
from src.backtest.e0.models import (
    A0RunnerConfig,
    ConfidencePolicy,
    DecisionAction,
    DecisionRecord,
    E0Adjudication,
    E0IntegrityReport,
    E0Manifest,
    E0Report,
    E0Sample,
    E0Verdict,
    FeeProfile,
    HorizonLabel,
    LabelRecord,
    MarketRegime,
    PositionProfile,
    RegimePolicy,
    RunnerId,
    RunnerStatus,
)
from src.backtest.e0.store import (
    E0ArtifactStore,
    E0IntegrityError,
    E0TerminalOverwriteError,
)

AS_OF = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"


def _manifest() -> E0Manifest:
    return E0Manifest(
        experiment_id="e0-store-fixture",
        created_at=AS_OF,
        code_commit="abc1234",
        model_id="deepseek-chat",
        a0_prompt_version="production:abc1234",
        a1_prompt_version="e0-single-agent:v1",
        random_seed=20260810,
        regime_policy=RegimePolicy(
            version="regime:v1",
            lookback_trading_days=20,
            trend_return_threshold=Decimal("0.08"),
            sideways_abs_return_max=Decimal("0.02"),
            high_volatility_threshold=Decimal("0.35"),
        ),
        fee_profile=FeeProfile(
            version="fees:v1",
            buy_commission_rate=Decimal("0.0003"),
            sell_commission_rate=Decimal("0.0003"),
            minimum_commission=Decimal("5"),
            sell_stamp_tax_rate=Decimal("0.0005"),
            transfer_fee_rate=Decimal("0.00001"),
            slippage_rate=Decimal("0.001"),
        ),
        position_profile=PositionProfile(
            version="position:v1",
            initial_capital=Decimal("100000"),
            long_fraction=Decimal("0.25"),
        ),
        confidence_policy=ConfidencePolicy(
            version="confidence:v1",
            high_confidence_threshold=Decimal("0.8"),
            ece_bucket_edges=(Decimal("0"), Decimal("0.5"), Decimal("1")),
            expansion_sample_count=300,
        ),
        a0_config=A0RunnerConfig(
            version="a0:v1",
            enable_risk=True,
            enable_trader=True,
            enable_reflection=True,
            enable_trust=True,
            enable_mirror=True,
        ),
        decision_question="未来五个交易日是否应持有该股票？",
        runner_ids=tuple(RunnerId),
        runner_versions=tuple(
            (runner_id, f"{runner_id.value.lower()}:v1") for runner_id in RunnerId
        ),
        runner_config_versions=(
            (RunnerId.A0, "a0:v1"),
            (RunnerId.A1, "a1-config:v1"),
            (RunnerId.B0, "b0-config:v1"),
            (RunnerId.B1, "b1-config:v1"),
            (RunnerId.B3, "b3-config:v1"),
        ),
        runner_prompt_versions=(
            (RunnerId.A0, "production:abc1234"),
            (RunnerId.A1, "e0-single-agent:v1"),
            (RunnerId.B0, "not-applicable:v1"),
            (RunnerId.B1, "not-applicable:v1"),
            (RunnerId.B3, "not-applicable:v1"),
        ),
        primary_horizon=5,
        auxiliary_horizons=(1, 20),
        candidate_universe_hash=HASH,
        candidate_exclusions=(),
        replacement_order=(),
        samples=(
            E0Sample(
                sample_id="sample-001",
                candidate_id="candidate-001",
                symbol="000001",
                decision_at=AS_OF,
                regime=MarketRegime.UP,
                evidence_snapshot_id="evidence-001",
                evidence_hash=HASH,
            ),
        ),
        stability_sample_ids=(),
        fixture_mode=True,
    )


def _decision(runner_id: RunnerId, **updates: object) -> DecisionRecord:
    prompt_versions = {
        RunnerId.A0: "production:abc1234",
        RunnerId.A1: "e0-single-agent:v1",
        RunnerId.B0: "not-applicable:v1",
        RunnerId.B1: "not-applicable:v1",
        RunnerId.B3: "not-applicable:v1",
    }
    config_versions = {
        RunnerId.A0: "a0:v1",
        RunnerId.A1: "a1-config:v1",
        RunnerId.B0: "b0-config:v1",
        RunnerId.B1: "b1-config:v1",
        RunnerId.B3: "b3-config:v1",
    }
    values: dict[str, object] = {
        "experiment_id": "e0-store-fixture",
        "sample_id": "sample-001",
        "runner_id": runner_id,
        "runner_version": f"{runner_id.value.lower()}:v1",
        "repetition": 1,
        "symbol": "000001",
        "decision_at": AS_OF,
        "evidence_snapshot_id": "evidence-001",
        "evidence_hash": HASH,
        "as_of": AS_OF,
        "action": DecisionAction.CASH,
        "position_fraction": Decimal("0"),
        "confidence": Decimal("0.5"),
        "status": RunnerStatus.COMPLETE,
        "error_code": None,
        "reason": "fixture decision",
        "raw_output_hash": HASH,
        "model_id": "deepseek-chat",
        "prompt_version": prompt_versions[runner_id],
        "code_commit": "abc1234",
        "config_version": config_versions[runner_id],
        "regime_policy_version": "regime:v1",
        "fee_profile_version": "fees:v1",
        "position_profile_version": "position:v1",
        "confidence_policy_version": "confidence:v1",
        "configured_position_fraction": Decimal("0.25"),
        "started_at": AS_OF,
        "finished_at": AS_OF,
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "model_cost": Decimal("0"),
        "freshness_seconds": 0,
    }
    values.update(updates)
    return DecisionRecord.model_validate(values)


def _label_record(**updates: object) -> LabelRecord:
    labels = tuple(
        HorizonLabel(
            horizon_days=horizon,
            market_return=Decimal("0.01"),
            long_net_return=Decimal("0.009"),
            entry_price=Decimal("10"),
            exit_price=Decimal("10.1"),
            tradable=True,
            error_code=None,
        )
        for horizon in (1, 5, 20)
    )
    values: dict[str, object] = {
        "experiment_id": "e0-store-fixture",
        "sample_id": "sample-001",
        "evidence_snapshot_id": "evidence-001",
        "fee_profile_version": "fees:v1",
        "position_profile_version": "position:v1",
        "labels": labels,
    }
    values.update(updates)
    return LabelRecord.model_validate(values)


def _report(manifest_hash: str) -> E0Report:
    return E0Report(
        experiment_id="e0-store-fixture",
        manifest_hash=manifest_hash,
        generated_at=AS_OF,
        primary_horizon=5,
        runner_metrics=(),
        pairwise_metrics=(),
        stability_metrics=(),
        integrity=E0IntegrityReport(valid=True, checks=("all_hashes",), reasons=()),
        adjudication=E0Adjudication(
            verdict=E0Verdict.INSUFFICIENT_EVIDENCE,
            reasons=("fixture",),
            predicates=(("integrity_valid", True),),
        ),
    )


def _record_line(prefix: str, record: BaseModel) -> str:
    return canonical_json(
        {
            "record": record.model_dump(mode="json"),
            "record_hash": sha256_identity(prefix, record),
        }
    )


def _complete_store(tmp_path: Path) -> E0ArtifactStore:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    for runner_id in RunnerId:
        store.append_decision(_decision(runner_id))
    store.append_label(_label_record())
    return store


def test_create_publishes_exact_manifest_and_hash(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")

    store.create(_manifest())

    assert store.load_manifest() == _manifest()
    assert (store.root / "manifest.sha256").read_text(encoding="utf-8").startswith(
        "manifest:sha256:"
    )


@pytest.mark.parametrize("failure_target", ["manifest.sha256", "experiment"])
def test_create_replace_failure_leaves_no_partial_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_target: str,
) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    real_replace = os.replace

    def fail_selected_replace(source: str | Path, target: str | Path) -> None:
        if Path(target).name == failure_target:
            raise OSError("injected create replace failure")
        real_replace(source, target)

    monkeypatch.setattr("src.backtest.e0.store.os.replace", fail_selected_replace)

    with pytest.raises(OSError, match="injected create"):
        store.create(_manifest())

    assert not store.root.exists()
    assert list(tmp_path.glob(".experiment-*")) == []


def test_identical_decision_replay_is_byte_stable(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    decision = _decision(RunnerId.A0)
    store.append_decision(decision)
    before = (store.root / "decisions.jsonl").read_bytes()

    store.append_decision(decision)

    assert (store.root / "decisions.jsonl").read_bytes() == before
    assert store.completed_decision_keys() == {
        ("sample-001", RunnerId.A0, 1)
    }


def test_conflicting_decision_replay_is_rejected(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    store.append_decision(_decision(RunnerId.A0))

    with pytest.raises(E0IntegrityError, match="conflicting decision"):
        store.append_decision(_decision(RunnerId.A0, reason="changed"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runner_version", "other-runner:v1"),
        ("config_version", "other-config:v1"),
        ("prompt_version", "other-prompt:v1"),
    ],
)
def test_decision_versions_must_match_manifest(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())

    with pytest.raises(E0IntegrityError, match="version"):
        store.append_decision(_decision(RunnerId.A0, **{field: value}))


def test_unregistered_repetition_is_rejected(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())

    with pytest.raises(E0IntegrityError, match="expected denominator"):
        store.append_decision(_decision(RunnerId.A0, repetition=2))


def test_duplicate_decision_key_in_ledger_is_rejected(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    first = _decision(RunnerId.A0)
    second = _decision(RunnerId.A0, reason="different but correctly hashed")
    (store.root / "decisions.jsonl").write_text(
        f"{_record_line('decision', first)}\n{_record_line('decision', second)}\n",
        encoding="utf-8",
    )

    with pytest.raises(E0IntegrityError, match="duplicate decision key"):
        store.completed_decision_keys()


def test_manifest_tampering_is_reported(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    (store.root / "manifest.json").write_text("{}", encoding="utf-8")

    integrity = store.verify()

    assert integrity.valid is False
    assert "manifest_hash_mismatch" in integrity.reasons


def test_decision_hash_tampering_is_reported(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    store.append_decision(_decision(RunnerId.A0))
    path = store.root / "decisions.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace("fixture decision", "tampered"),
        encoding="utf-8",
    )

    integrity = store.verify()

    assert integrity.valid is False
    assert "decision_integrity_failure" in integrity.reasons


def test_invalid_utf8_ledger_returns_integrity_report(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    (store.root / "decisions.jsonl").write_bytes(b"\xff\xfe")

    integrity = store.verify()

    assert integrity.valid is False
    assert "decision_integrity_failure" in integrity.reasons


def test_missing_decision_stays_in_integrity_denominator(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    for runner_id in tuple(RunnerId)[:-1]:
        store.append_decision(_decision(runner_id))

    integrity = store.verify()

    assert integrity.valid is False
    assert integrity.missing_decision_keys == ("sample-001:B3:1",)


def test_label_cannot_be_published_before_all_decisions(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())

    with pytest.raises(E0IntegrityError, match="all decisions"):
        store.append_label(_label_record())


def test_label_evidence_identity_must_match_manifest(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    for runner_id in RunnerId:
        store.append_decision(_decision(runner_id))

    with pytest.raises(E0IntegrityError, match="evidence snapshot"):
        store.append_label(_label_record(evidence_snapshot_id="other-evidence"))


def test_rehashed_label_identity_tampering_is_reported(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    tampered = _label_record(evidence_snapshot_id="other-evidence")
    (store.root / "labels.jsonl").write_text(
        f"{_record_line('label', tampered)}\n",
        encoding="utf-8",
    )

    integrity = store.verify()

    assert integrity.valid is False
    assert "label_integrity_failure" in integrity.reasons


def test_report_cannot_be_published_before_all_labels(tmp_path: Path) -> None:
    store = E0ArtifactStore(tmp_path / "experiment")
    store.create(_manifest())
    for runner_id in RunnerId:
        store.append_decision(_decision(runner_id))
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")

    with pytest.raises(E0IntegrityError, match="all labels"):
        store.publish_report(_report(manifest_hash), "fixture report")


def test_terminal_report_cannot_be_overwritten(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    store.publish_report(_report(manifest_hash), "fixture report")

    with pytest.raises(E0TerminalOverwriteError):
        store.publish_report(_report(manifest_hash), "different")


def test_terminal_experiment_rejects_ledger_append(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    store.publish_report(_report(manifest_hash), "fixture report")

    with pytest.raises(E0TerminalOverwriteError):
        store.append_decision(_decision(RunnerId.A0))
    with pytest.raises(E0TerminalOverwriteError):
        store.append_label(_label_record())


def test_terminal_decision_ledger_rehash_tampering_is_reported(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    store.publish_report(_report(manifest_hash), "fixture report")
    decisions = [_decision(runner_id) for runner_id in RunnerId]
    decisions[0] = decisions[0].model_copy(update={"reason": "rehashed tampering"})
    (store.root / "decisions.jsonl").write_text(
        "".join(f"{_record_line('decision', record)}\n" for record in decisions),
        encoding="utf-8",
    )

    integrity = store.verify()

    assert integrity.valid is False
    assert "terminal_integrity_failure" in integrity.reasons


@pytest.mark.parametrize("ledger_name", ["decisions.jsonl", "labels.jsonl"])
def test_deleted_terminal_ledger_returns_integrity_report(
    tmp_path: Path,
    ledger_name: str,
) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    store.publish_report(_report(manifest_hash), "fixture report")
    (store.root / ledger_name).unlink()

    integrity = store.verify()

    assert integrity.valid is False
    assert "terminal_integrity_failure" in integrity.reasons


def test_terminal_markdown_tampering_is_reported(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    store.publish_report(_report(manifest_hash), "fixture report")
    (store.root / "report.md").write_text("tampered", encoding="utf-8")

    integrity = store.verify()

    assert integrity.valid is False
    assert "terminal_integrity_failure" in integrity.reasons


def test_partial_report_without_terminal_is_reported(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    (store.root / "report.md").write_text("partial", encoding="utf-8")

    integrity = store.verify()

    assert integrity.valid is False
    assert "terminal_integrity_failure" in integrity.reasons


def test_report_refuses_tampered_decision_ledger(tmp_path: Path) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    path = store.root / "decisions.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace("fixture decision", "tampered"),
        encoding="utf-8",
    )

    with pytest.raises(E0IntegrityError, match="integrity"):
        store.publish_report(_report(manifest_hash), "fixture report")


def test_report_publication_rolls_back_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _complete_store(tmp_path)
    manifest_hash = (store.root / "manifest.sha256").read_text(encoding="utf-8")
    real_replace = os.replace

    def fail_on_markdown(source: str | Path, target: str | Path) -> None:
        if Path(target).name == "report.md":
            raise OSError("injected replace failure")
        real_replace(source, target)

    monkeypatch.setattr("src.backtest.e0.store.os.replace", fail_on_markdown)

    with pytest.raises(OSError, match="injected"):
        store.publish_report(_report(manifest_hash), "fixture report")

    assert not (store.root / "report.json").exists()
    assert not (store.root / "report.md").exists()
    assert not (store.root / "terminal.json").exists()

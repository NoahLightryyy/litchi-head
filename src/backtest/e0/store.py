"""Immutable, resume-safe artifact storage for E0 experiments."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.backtest.e0.hashing import canonical_json, sha256_identity
from src.backtest.e0.models import (
    DecisionRecord,
    E0IntegrityReport,
    E0Manifest,
    E0Report,
    LabelRecord,
    RunnerId,
)


class E0StoreError(RuntimeError):
    """Base error for E0 artifact persistence."""


class E0IntegrityError(E0StoreError):
    """Raised when frozen artifact integrity cannot be proven."""


class E0TerminalOverwriteError(E0StoreError):
    """Raised when code attempts to replace a terminal experiment."""


RecordT = TypeVar("RecordT", bound=BaseModel)
DecisionKey = tuple[str, RunnerId, int]


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"strict JSON forbids non-finite constant {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: str) -> object:
    return json.loads(
        raw,
        parse_constant=_reject_json_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=path.parent) as staged:
            staged.write(payload)
            staged.flush()
            os.fsync(staged.fileno())
            staged_path = Path(staged.name)
        os.replace(staged_path, path)
        staged_path = None
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


def _record_line(prefix: str, record: BaseModel) -> str:
    record_hash = sha256_identity(prefix, record)
    return canonical_json(
        {
            "record": record.model_dump(mode="json"),
            "record_hash": record_hash,
        }
    )


class E0ArtifactStore:
    """Own one append-only E0 experiment directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def _manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def _manifest_hash_path(self) -> Path:
        return self.root / "manifest.sha256"

    @property
    def _decisions_path(self) -> Path:
        return self.root / "decisions.jsonl"

    @property
    def _labels_path(self) -> Path:
        return self.root / "labels.jsonl"

    def create(self, manifest: E0Manifest) -> None:
        """Atomically publish a new experiment manifest."""

        if self.root.exists():
            raise E0StoreError(f"experiment directory already exists: {self.root}")
        self.root.parent.mkdir(parents=True, exist_ok=True)
        staged_root = Path(
            tempfile.mkdtemp(prefix=f".{self.root.name}-", dir=self.root.parent)
        )
        try:
            _atomic_write(
                staged_root / "manifest.json",
                canonical_json(manifest).encode("utf-8"),
            )
            _atomic_write(
                staged_root / "manifest.sha256",
                sha256_identity("manifest", manifest).encode("utf-8"),
            )
            os.replace(staged_root, self.root)
        except Exception:
            shutil.rmtree(staged_root, ignore_errors=True)
            raise

    def load_manifest(self) -> E0Manifest:
        """Load the manifest only when its bytes match the frozen identity."""

        if not self._manifest_path.is_file() or not self._manifest_hash_path.is_file():
            raise E0IntegrityError("manifest files are missing")
        try:
            raw = self._manifest_path.read_text(encoding="utf-8")
            expected = self._manifest_hash_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise E0IntegrityError("manifest files are unreadable") from exc
        raw_identity = f"manifest:sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
        if raw_identity != expected:
            raise E0IntegrityError("manifest_hash_mismatch")
        try:
            manifest = E0Manifest.model_validate(_strict_json(raw))
        except (ValueError, ValidationError) as exc:
            raise E0IntegrityError("manifest is invalid") from exc
        if sha256_identity("manifest", manifest) != expected:
            raise E0IntegrityError("manifest_hash_mismatch")
        if canonical_json(manifest) != raw:
            raise E0IntegrityError("manifest bytes are not canonical")
        return manifest

    def append_decision(self, record: DecisionRecord) -> None:
        self._ensure_mutable()
        manifest = self.load_manifest()
        self._validate_decision_identity(record, manifest)
        if self._decision_key(record) not in self._expected_decision_keys(manifest):
            raise E0IntegrityError("decision key is outside the expected denominator")
        records = self._read_decisions()
        key = self._decision_key(record)
        existing = {self._decision_key(item): item for item in records}
        if key in existing:
            if existing[key] == record:
                return
            raise E0IntegrityError(f"conflicting decision replay: {key}")
        records.append(record)
        self._write_records(self._decisions_path, "decision", records)

    def append_label(self, record: LabelRecord) -> None:
        self._ensure_mutable()
        manifest = self.load_manifest()
        if self.completed_decision_keys() != self._expected_decision_keys(manifest):
            raise E0IntegrityError("all decisions must exist before labels")
        samples = {sample.sample_id: sample for sample in manifest.samples}
        sample = samples.get(record.sample_id)
        if sample is None or record.experiment_id != manifest.experiment_id:
            raise E0IntegrityError("label sample identity does not match manifest")
        if record.evidence_snapshot_id != sample.evidence_snapshot_id:
            raise E0IntegrityError("label evidence snapshot does not match manifest")
        if record.fee_profile_version != manifest.fee_profile.version:
            raise E0IntegrityError("label fee profile does not match manifest")
        if record.position_profile_version != manifest.position_profile.version:
            raise E0IntegrityError("label position profile does not match manifest")
        records = self._read_labels()
        existing = {item.sample_id: item for item in records}
        if record.sample_id in existing:
            if existing[record.sample_id] == record:
                return
            raise E0IntegrityError(f"conflicting label replay: {record.sample_id}")
        records.append(record)
        self._write_records(self._labels_path, "label", records)

    def publish_report(self, report: E0Report, markdown: str) -> None:
        targets = (
            self.root / "report.json",
            self.root / "report.md",
            self.root / "terminal.json",
        )
        if any(path.exists() for path in targets):
            raise E0TerminalOverwriteError("terminal experiment cannot be overwritten")
        manifest = self.load_manifest()
        manifest_hash = self._manifest_hash_path.read_text(encoding="utf-8")
        if report.experiment_id != manifest.experiment_id:
            raise E0IntegrityError("report experiment does not match manifest")
        if report.manifest_hash != manifest_hash:
            raise E0IntegrityError("report manifest hash does not match manifest")
        labels = self._read_labels()
        if {label.sample_id for label in labels} != {
            sample.sample_id for sample in manifest.samples
        }:
            raise E0IntegrityError("all labels must exist before report publication")
        integrity = self.verify()
        if not integrity.valid:
            raise E0IntegrityError("artifact integrity must be complete before report")

        report_json = canonical_json(report).encode("utf-8")
        markdown_bytes = markdown.encode("utf-8")
        terminal = canonical_json(
            {
                "experiment_id": manifest.experiment_id,
                "manifest_hash": manifest_hash,
                "decisions_sha256": hashlib.sha256(
                    self._decisions_path.read_bytes()
                ).hexdigest(),
                "labels_sha256": hashlib.sha256(
                    self._labels_path.read_bytes()
                ).hexdigest(),
                "report_hash": sha256_identity("report", report),
                "markdown_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
            }
        ).encode("utf-8")
        self._publish_terminal_files(
            ((targets[0], report_json), (targets[1], markdown_bytes), (targets[2], terminal))
        )

    def completed_decision_keys(self) -> frozenset[DecisionKey]:
        records = self._read_decisions()
        return frozenset(self._decision_key(record) for record in records)

    def verify(self) -> E0IntegrityReport:
        checks: list[str] = []
        reasons: list[str] = []
        try:
            manifest = self.load_manifest()
            checks.append("manifest_hash")
        except E0IntegrityError as exc:
            reason = str(exc)
            if "manifest_hash_mismatch" in reason:
                reasons.append("manifest_hash_mismatch")
            else:
                reasons.append("manifest_invalid")
            return E0IntegrityReport(valid=False, checks=tuple(checks), reasons=tuple(reasons))

        decisions: list[DecisionRecord] = []
        labels: list[LabelRecord] = []
        try:
            decisions = self._read_decisions()
            for record in decisions:
                self._validate_decision_identity(record, manifest)
            checks.append("decision_hashes")
        except E0IntegrityError:
            reasons.append("decision_integrity_failure")
        try:
            labels = self._read_labels()
            for record in labels:
                self._validate_label_identity(record, manifest)
            checks.append("label_hashes")
        except E0IntegrityError:
            reasons.append("label_integrity_failure")

        actual_decisions = frozenset(self._decision_key(record) for record in decisions)
        missing_decisions = tuple(
            self._format_decision_key(key)
            for key in sorted(
                self._expected_decision_keys(manifest) - actual_decisions,
                key=lambda item: (item[0], item[1].value, item[2]),
            )
        )
        unexpected_decisions = tuple(
            self._format_decision_key(key)
            for key in sorted(
                actual_decisions - self._expected_decision_keys(manifest),
                key=lambda item: (item[0], item[1].value, item[2]),
            )
        )
        expected_label_ids = {sample.sample_id for sample in manifest.samples}
        actual_label_ids = {label.sample_id for label in labels}
        missing_labels = tuple(sorted(expected_label_ids - actual_label_ids))
        if missing_decisions:
            reasons.append("missing_decisions")
        if unexpected_decisions:
            reasons.append("unexpected_decisions")
        if missing_labels:
            reasons.append("missing_labels")
        try:
            if self._verify_terminal_files(manifest):
                checks.append("terminal_hashes")
        except E0IntegrityError:
            reasons.append("terminal_integrity_failure")
        return E0IntegrityReport(
            valid=not reasons,
            checks=tuple(checks),
            reasons=tuple(reasons),
            missing_decision_keys=missing_decisions,
            unexpected_decision_keys=unexpected_decisions,
            missing_label_keys=missing_labels,
        )

    @staticmethod
    def _decision_key(record: DecisionRecord) -> DecisionKey:
        return (record.sample_id, record.runner_id, record.repetition)

    @staticmethod
    def _format_decision_key(key: DecisionKey) -> str:
        return f"{key[0]}:{key[1].value}:{key[2]}"

    @staticmethod
    def _expected_decision_keys(manifest: E0Manifest) -> frozenset[DecisionKey]:
        primary = {
            (sample.sample_id, runner_id, 1)
            for sample in manifest.samples
            for runner_id in manifest.runner_ids
        }
        stability = {
            (sample_id, runner_id, repetition)
            for sample_id in manifest.stability_sample_ids
            for runner_id in (RunnerId.A0, RunnerId.A1)
            for repetition in (2, 3)
        }
        return frozenset(primary | stability)

    @staticmethod
    def _validate_decision_identity(
        record: DecisionRecord,
        manifest: E0Manifest,
    ) -> None:
        samples = {sample.sample_id: sample for sample in manifest.samples}
        sample = samples.get(record.sample_id)
        if sample is None or record.runner_id not in manifest.runner_ids:
            raise E0IntegrityError("decision key does not belong to manifest")
        if record.experiment_id != manifest.experiment_id:
            raise E0IntegrityError("decision experiment does not match manifest")
        if (
            record.symbol != sample.symbol
            or record.decision_at != sample.decision_at
            or record.evidence_snapshot_id != sample.evidence_snapshot_id
            or record.evidence_hash != sample.evidence_hash
        ):
            raise E0IntegrityError("decision sample evidence does not match manifest")
        if record.code_commit != manifest.code_commit:
            raise E0IntegrityError("decision code commit does not match manifest")
        if record.model_id != manifest.model_id:
            raise E0IntegrityError("decision model does not match manifest")
        if record.regime_policy_version != manifest.regime_policy.version:
            raise E0IntegrityError("decision regime policy does not match manifest")
        if record.fee_profile_version != manifest.fee_profile.version:
            raise E0IntegrityError("decision fee profile does not match manifest")
        if record.position_profile_version != manifest.position_profile.version:
            raise E0IntegrityError("decision position profile does not match manifest")
        if record.confidence_policy_version != manifest.confidence_policy.version:
            raise E0IntegrityError("decision confidence policy does not match manifest")
        if record.configured_position_fraction != manifest.position_profile.long_fraction:
            raise E0IntegrityError("decision position fraction does not match manifest")
        if record.runner_version != dict(manifest.runner_versions)[record.runner_id]:
            raise E0IntegrityError("decision runner version does not match manifest")
        if record.config_version != dict(manifest.runner_config_versions)[record.runner_id]:
            raise E0IntegrityError("decision config version does not match manifest")
        if record.prompt_version != dict(manifest.runner_prompt_versions)[record.runner_id]:
            raise E0IntegrityError("decision prompt version does not match manifest")

    @staticmethod
    def _validate_label_identity(record: LabelRecord, manifest: E0Manifest) -> None:
        samples = {sample.sample_id: sample for sample in manifest.samples}
        sample = samples.get(record.sample_id)
        if sample is None or record.experiment_id != manifest.experiment_id:
            raise E0IntegrityError("label sample identity does not match manifest")
        if record.evidence_snapshot_id != sample.evidence_snapshot_id:
            raise E0IntegrityError("label evidence snapshot does not match manifest")
        if record.fee_profile_version != manifest.fee_profile.version:
            raise E0IntegrityError("label fee profile does not match manifest")
        if record.position_profile_version != manifest.position_profile.version:
            raise E0IntegrityError("label position profile does not match manifest")

    def _read_decisions(self) -> list[DecisionRecord]:
        records = self._read_records(
            self._decisions_path,
            prefix="decision",
            parser=DecisionRecord.model_validate,
        )
        keys = [self._decision_key(record) for record in records]
        if len(keys) != len(set(keys)):
            raise E0IntegrityError("duplicate decision key")
        return records

    def _read_labels(self) -> list[LabelRecord]:
        records = self._read_records(
            self._labels_path,
            prefix="label",
            parser=LabelRecord.model_validate,
        )
        keys = [record.sample_id for record in records]
        if len(keys) != len(set(keys)):
            raise E0IntegrityError("duplicate label key")
        return records

    def _verify_terminal_files(self, manifest: E0Manifest) -> bool:
        report_path = self.root / "report.json"
        markdown_path = self.root / "report.md"
        terminal_path = self.root / "terminal.json"
        paths = (report_path, markdown_path, terminal_path)
        present = tuple(path.is_file() for path in paths)
        if not any(present):
            return False
        if not all(present):
            raise E0IntegrityError("terminal artifact set is partial")
        try:
            report_raw = report_path.read_text(encoding="utf-8")
            report = E0Report.model_validate(_strict_json(report_raw))
            terminal_raw = terminal_path.read_text(encoding="utf-8")
            terminal = _strict_json(terminal_raw)
            decisions_bytes = self._decisions_path.read_bytes()
            labels_bytes = self._labels_path.read_bytes()
            manifest_hash = self._manifest_hash_path.read_text(encoding="utf-8")
            markdown_bytes = markdown_path.read_bytes()
        except (OSError, ValueError, ValidationError, UnicodeDecodeError) as exc:
            raise E0IntegrityError("terminal artifact is invalid") from exc
        if not isinstance(terminal, dict) or set(terminal) != {
            "decisions_sha256",
            "experiment_id",
            "labels_sha256",
            "manifest_hash",
            "markdown_sha256",
            "report_hash",
        }:
            raise E0IntegrityError("terminal marker schema is invalid")
        expected_terminal = {
            "decisions_sha256": hashlib.sha256(decisions_bytes).hexdigest(),
            "experiment_id": manifest.experiment_id,
            "labels_sha256": hashlib.sha256(labels_bytes).hexdigest(),
            "manifest_hash": manifest_hash,
            "markdown_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
            "report_hash": sha256_identity("report", report),
        }
        if terminal != expected_terminal:
            raise E0IntegrityError("terminal marker hashes do not match artifacts")
        if report.experiment_id != manifest.experiment_id:
            raise E0IntegrityError("terminal report experiment does not match manifest")
        if report.manifest_hash != manifest_hash:
            raise E0IntegrityError("terminal report manifest hash does not match")
        if canonical_json(report) != report_raw or canonical_json(terminal) != terminal_raw:
            raise E0IntegrityError("terminal artifacts are not canonical")
        return True

    def _ensure_mutable(self) -> None:
        terminal_paths = (
            self.root / "report.json",
            self.root / "report.md",
            self.root / "terminal.json",
        )
        if any(path.exists() for path in terminal_paths):
            raise E0TerminalOverwriteError("terminal experiment cannot be mutated")

    @staticmethod
    def _read_records(
        path: Path,
        *,
        prefix: str,
        parser: Callable[[Any], RecordT],
    ) -> list[RecordT]:
        if not path.exists():
            return []
        records: list[RecordT] = []
        seen_hashes: set[str] = set()
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                payload = _strict_json(line)
                if not isinstance(payload, dict) or set(payload) != {
                    "record",
                    "record_hash",
                }:
                    raise E0IntegrityError(f"invalid {prefix} record envelope")
                record = parser(payload["record"])
                record_hash = payload["record_hash"]
                if not isinstance(record_hash, str):
                    raise E0IntegrityError(f"invalid {prefix} record hash")
                if sha256_identity(prefix, record) != record_hash:
                    raise E0IntegrityError(f"{prefix} record hash mismatch")
                if record_hash in seen_hashes:
                    raise E0IntegrityError(f"duplicate {prefix} record hash")
                seen_hashes.add(record_hash)
                records.append(record)
        except (
            json.JSONDecodeError,
            OSError,
            UnicodeDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            if isinstance(exc, E0IntegrityError):
                raise
            raise E0IntegrityError(f"invalid {prefix} record file") from exc
        return records

    @staticmethod
    def _write_records(
        path: Path,
        prefix: str,
        records: Iterable[BaseModel],
    ) -> None:
        body = "".join(f"{_record_line(prefix, record)}\n" for record in records)
        _atomic_write(path, body.encode("utf-8"))

    @staticmethod
    def _publish_terminal_files(files: Iterable[tuple[Path, bytes]]) -> None:
        staged: list[tuple[Path, Path]] = []
        published: list[Path] = []
        try:
            for target, payload in files:
                with tempfile.NamedTemporaryFile(delete=False, dir=target.parent) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                    staged.append((Path(handle.name), target))
            for source, target in staged:
                os.replace(source, target)
                published.append(target)
        except Exception:
            for target in published:
                target.unlink(missing_ok=True)
            raise
        finally:
            for source, _ in staged:
                source.unlink(missing_ok=True)

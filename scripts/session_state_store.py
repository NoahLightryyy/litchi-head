"""Immutable, project-scoped storage for verified session snapshots."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from scripts.session_state_models import (
    SessionSnapshotV2,
    normalize_identity_path,
    path_key,
)

_MAX_SNAPSHOT_BYTES = 1024 * 1024
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|secret)\b[\"']?\s*[:=]\s*"
        r"[\"']?[^\s\"']{8,}"
    ),
)


class SnapshotStoreError(RuntimeError):
    """Raised when a session snapshot cannot be safely stored or read."""


class LegacySnapshot(BaseModel):
    """Non-executable metadata recovered from a legacy handover file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    project_root: str
    saved_at_label: str | None
    next_step_executable: bool = False


def contains_secret(value: object) -> bool:
    """Return whether JSON-compatible data contains a likely credential."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return any(pattern.search(text) is not None for pattern in _SECRET_PATTERNS)


def snapshot_directory(root: Path, project: Path, worktree: Path) -> Path:
    """Return the non-reversible project/worktree namespace below ``root``."""
    return root / "v2" / path_key(project) / path_key(worktree)


def write_snapshot(root: Path, snapshot: SessionSnapshotV2) -> Path:
    """Atomically write one immutable UTF-8 v2 snapshot."""
    payload = snapshot.model_dump(mode="json")
    if contains_secret(payload):
        raise SnapshotStoreError("snapshot contains a suspected secret field")

    directory = snapshot_directory(
        root, Path(snapshot.project_root), Path(snapshot.worktree_path)
    )
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    if destination.exists():
        raise SnapshotStoreError("snapshot already exists and is immutable")

    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as error:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise SnapshotStoreError(f"atomic replace failed: {type(error).__name__}") from error
    return destination


def load_v2(path: Path) -> SessionSnapshotV2:
    """Load and validate a bounded v2 snapshot without exposing its contents."""
    try:
        if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
            raise SnapshotStoreError("snapshot exceeds the 1 MiB limit")
        return SessionSnapshotV2.model_validate_json(path.read_bytes())
    except SnapshotStoreError:
        raise
    except (OSError, UnicodeError, ValidationError, ValueError) as error:
        raise SnapshotStoreError(
            f"snapshot load failed: {type(error).__name__}"
        ) from error


def discover_v2(root: Path, project: Path, worktree: Path) -> tuple[Path, ...]:
    """Find every valid in-scope snapshot in chronological order."""
    directory = snapshot_directory(root, project, worktree)
    if not directory.exists():
        return ()
    loaded = [(load_v2(path).saved_at, path) for path in directory.glob("*-session.json")]
    return tuple(path for _, path in sorted(loaded, key=lambda item: (item[0], str(item[1]))))


def discover_legacy(root: Path, project: Path) -> tuple[LegacySnapshot, ...]:
    """Return matching legacy files as quarantined, non-executable history."""
    expected = normalize_identity_path(project)
    project_pattern = re.compile(r"^\*\*Project:\*\*\s*(.+?)\s*$", re.MULTILINE)
    date_pattern = re.compile(r"^# Session:\s*(.+?)\s*$", re.MULTILINE)
    matches: list[LegacySnapshot] = []
    for path in sorted(root.glob("*-session.tmp")):
        try:
            if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            project_match = project_pattern.search(text)
            if project_match is None:
                continue
            candidate_project = Path(project_match.group(1).strip())
            if normalize_identity_path(candidate_project) != expected:
                continue
            date_match = date_pattern.search(text)
            resolved_path = path.resolve(strict=True)
            resolved_project = candidate_project.resolve(strict=True)
        except (OSError, ValueError):
            continue
        matches.append(
            LegacySnapshot(
                path=str(resolved_path),
                project_root=str(resolved_project),
                saved_at_label=date_match.group(1).strip() if date_match else None,
            )
        )
    return tuple(matches)

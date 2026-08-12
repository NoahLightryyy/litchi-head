"""Factories shared by session snapshot contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def valid_snapshot_payload(tmp_path: Path) -> dict[str, object]:
    """Return a minimally valid session snapshot payload."""
    evidence = {"path": "docs/01-guides/HANDOVER.md", "sha256": "a" * 64}
    return {
        "snapshot_id": "snapshot_01",
        "saved_at": datetime.now(UTC),
        "project_root": str(tmp_path),
        "worktree_path": str(tmp_path),
        "branch": "codex/session-recovery",
        "git_head": "b" * 40,
        "git_dirty": False,
        "dirty_paths": (),
        "handover": evidence,
        "latest_work_log": None,
        "sdd_progress": None,
        "topic": "Freeze snapshot contracts",
        "handoff": {"exact_next_step": "Run the recovery verifier."},
    }


def valid_repository_payload(tmp_path: Path) -> dict[str, object]:
    """Return a minimally valid repository state payload."""
    evidence = {"path": "docs/01-guides/HANDOVER.md", "sha256": "a" * 64}
    return {
        "project_root": str(tmp_path),
        "worktree_path": str(tmp_path),
        "branch": "codex/session-recovery",
        "git_head": "b" * 40,
        "git_dirty": False,
        "dirty_paths": (),
        "handover": evidence,
        "latest_work_log": None,
        "sdd_progress": None,
    }

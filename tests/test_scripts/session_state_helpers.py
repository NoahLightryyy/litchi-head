"""Factories shared by session snapshot contract tests."""

from __future__ import annotations

import subprocess
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


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Git in a temporary test repository."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def write(repo: Path, relative: str, content: str) -> Path:
    """Write UTF-8 fixture content below a temporary repository."""
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def init_repo(tmp_path: Path) -> Path:
    """Create a committed repository with all session evidence candidates."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.name", "Session State Test")
    git(repo, "config", "user.email", "session-state@example.test")
    write(repo, "README.md", "initial readme\n")
    write(repo, "docs/01-guides/HANDOVER.md", "handover\n")
    write(repo, "docs/04-changelog/logs/2026-08-10/2026-08-10-1.md", "work log\n")
    write(repo, ".superpowers/sdd/2026-08-10-task/progress.md", "progress\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial session evidence")
    return repo

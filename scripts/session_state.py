"""Fail-closed validation for repository-scoped session snapshots."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.session_state_git import (  # noqa: E402
    GitInspectionError,
    collect_repository_state,
    is_ancestor,
)
from scripts.session_state_models import (  # noqa: E402
    HandoffPayload,
    RepositoryState,
    SessionSnapshotV2,
    SnapshotStatus,
    ValidationResult,
)
from scripts.session_state_store import (  # noqa: E402
    SnapshotStoreError,
    discover_legacy,
    discover_v2,
    load_v2,
)


def build_snapshot(
    state: RepositoryState,
    topic: str,
    handoff: HandoffPayload,
    saved_at: datetime,
) -> SessionSnapshotV2:
    """Build a v2 snapshot from one already-collected repository state."""
    compact_time = saved_at.strftime("%Y%m%dT%H%M%S%f%z")
    return SessionSnapshotV2(
        snapshot_id=f"{compact_time}-{state.git_head[:7]}",
        saved_at=saved_at,
        project_root=state.project_root,
        worktree_path=state.worktree_path,
        branch=state.branch,
        git_head=state.git_head,
        git_dirty=state.git_dirty,
        dirty_paths=state.dirty_paths,
        handover=state.handover,
        latest_work_log=state.latest_work_log,
        sdd_progress=state.sdd_progress,
        topic=topic,
        handoff=handoff,
    )


def _validation_failure(
    status: SnapshotStatus,
    snapshot_path: Path,
    diagnostic: str,
) -> ValidationResult:
    return ValidationResult(
        status=status,
        snapshot_path=str(snapshot_path),
        diagnostics=(diagnostic,),
        handoff=None,
    )


def validate_snapshot(
    repo: Path,
    snapshot_path: Path,
    current: RepositoryState,
    now: datetime,
    allow_old: bool = False,
) -> ValidationResult:
    """Validate one snapshot in fail-closed precedence order."""
    try:
        snapshot = load_v2(snapshot_path)
        if (
            snapshot.project_root != current.project_root
            or snapshot.worktree_path != current.worktree_path
        ):
            return _validation_failure(
                SnapshotStatus.PROJECT_MISMATCH,
                snapshot_path,
                "project/worktree identity differs",
            )
        if snapshot.branch != current.branch:
            return _validation_failure(
                SnapshotStatus.BRANCH_MISMATCH, snapshot_path, "branch differs"
            )
        if snapshot.git_head != current.git_head:
            if is_ancestor(repo, snapshot.git_head, current.git_head):
                return _validation_failure(
                    SnapshotStatus.REPO_AHEAD,
                    snapshot_path,
                    "repository advanced after snapshot",
                )
            return _validation_failure(
                SnapshotStatus.HEAD_DIVERGED,
                snapshot_path,
                "snapshot HEAD is not an ancestor of current HEAD",
            )
        if snapshot.dirty_paths != current.dirty_paths:
            return _validation_failure(
                SnapshotStatus.DIRTY_MISMATCH,
                snapshot_path,
                "dirty path set differs",
            )
        if (snapshot.handover, snapshot.latest_work_log, snapshot.sdd_progress) != (
            current.handover,
            current.latest_work_log,
            current.sdd_progress,
        ):
            return _validation_failure(
                SnapshotStatus.EVIDENCE_CHANGED,
                snapshot_path,
                "handover/log/SDD evidence changed",
            )

        age_days = (now - snapshot.saved_at).days
        warnings = (f"snapshot is {age_days} days old",) if age_days > 7 else ()
        return ValidationResult(
            status=SnapshotStatus.MATCH,
            snapshot_path=str(snapshot_path),
            diagnostics=("snapshot matches current repository evidence",),
            warnings=warnings,
            requires_user_confirmation=bool(warnings),
            handoff=snapshot.handoff if allow_old or not warnings else None,
        )
    except (GitInspectionError, SnapshotStoreError, OSError, ValueError) as error:
        return _validation_failure(
            SnapshotStatus.MALFORMED,
            snapshot_path,
            f"session validation failed: {type(error).__name__}",
        )


def inspect_sessions(
    repo: Path,
    session_root: Path,
    now: datetime,
    current: RepositoryState | None = None,
    allow_old: bool = False,
) -> ValidationResult:
    """Inspect the newest in-scope v2 snapshot, or quarantine matching legacy state."""
    try:
        observed = current or collect_repository_state(repo)
        project = Path(observed.project_root)
        worktree = Path(observed.worktree_path)
        candidates = discover_v2(session_root, project, worktree)
        if candidates:
            return validate_snapshot(
                repo,
                candidates[-1],
                observed,
                now,
                allow_old=allow_old,
            )
        legacy = discover_legacy(session_root, project)
        if legacy:
            return ValidationResult(
                status=SnapshotStatus.LEGACY_UNVERIFIABLE,
                snapshot_path=legacy[-1].path,
                diagnostics=(
                    "legacy snapshot has no verifiable Git/evidence identity",
                ),
                handoff=None,
            )
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=("no matching session snapshot",),
            handoff=None,
        )
    except (GitInspectionError, SnapshotStoreError, OSError, ValueError) as error:
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=(f"session inspection failed: {type(error).__name__}",),
            handoff=None,
        )

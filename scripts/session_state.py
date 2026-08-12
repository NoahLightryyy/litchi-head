"""Fail-closed validation for repository-scoped session snapshots."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

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
    ValidationFailureReason,
    ValidationResult,
)
from scripts.session_state_store import (  # noqa: E402
    SnapshotStoreError,
    discover_legacy,
    discover_v2,
    load_v2,
    write_snapshot,
)

_STALE_STATUSES = frozenset(
    {
        SnapshotStatus.REPO_AHEAD,
        SnapshotStatus.HEAD_DIVERGED,
        SnapshotStatus.BRANCH_MISMATCH,
        SnapshotStatus.DIRTY_MISMATCH,
        SnapshotStatus.EVIDENCE_CHANGED,
        SnapshotStatus.PROJECT_MISMATCH,
        SnapshotStatus.LEGACY_UNVERIFIABLE,
    }
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
    failure_reason: ValidationFailureReason | None = None,
) -> ValidationResult:
    return ValidationResult(
        status=status,
        snapshot_path=str(snapshot_path),
        diagnostics=(diagnostic,),
        handoff=None,
        failure_reason=failure_reason,
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

        elapsed = now - snapshot.saved_at
        if elapsed < timedelta(0):
            return _validation_failure(
                SnapshotStatus.MALFORMED,
                snapshot_path,
                "snapshot saved_at is in the future",
                ValidationFailureReason.CORRUPT_SNAPSHOT,
            )
        warnings = (
            (f"snapshot is {elapsed.days} days old",)
            if elapsed > timedelta(days=7)
            else ()
        )
        return ValidationResult(
            status=SnapshotStatus.MATCH,
            snapshot_path=str(snapshot_path),
            diagnostics=("snapshot matches current repository evidence",),
            warnings=warnings,
            requires_user_confirmation=bool(warnings),
            handoff=snapshot.handoff if allow_old or not warnings else None,
        )
    except GitInspectionError as error:
        return _validation_failure(
            SnapshotStatus.MALFORMED,
            snapshot_path,
            f"session validation failed: {type(error).__name__}",
            ValidationFailureReason.OPERATIONAL_FAILURE,
        )
    except (SnapshotStoreError, ValueError) as error:
        return _validation_failure(
            SnapshotStatus.MALFORMED,
            snapshot_path,
            f"session validation failed: {type(error).__name__}",
            ValidationFailureReason.CORRUPT_SNAPSHOT,
        )
    except OSError as error:
        return _validation_failure(
            SnapshotStatus.MALFORMED,
            snapshot_path,
            f"session validation failed: {type(error).__name__}",
            ValidationFailureReason.OPERATIONAL_FAILURE,
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
            failure_reason=ValidationFailureReason.NO_CANDIDATE,
        )
    except (SnapshotStoreError, ValueError) as error:
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=(f"session inspection failed: {type(error).__name__}",),
            handoff=None,
            failure_reason=ValidationFailureReason.CORRUPT_SNAPSHOT,
        )
    except (GitInspectionError, OSError) as error:
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=(f"session inspection failed: {type(error).__name__}",),
            handoff=None,
            failure_reason=ValidationFailureReason.OPERATIONAL_FAILURE,
        )


def render_report(result: ValidationResult, current: RepositoryState) -> str:
    """Render a stable human-readable report without quarantined handoff data."""
    lines = [
        f"STATUS: {result.status.value}",
        f"WORKTREE: {current.worktree_path}",
        f"BRANCH: {current.branch}",
        f"HEAD: {current.git_head}",
        f"SNAPSHOT: {result.snapshot_path or 'none'}",
    ]
    lines.extend(f"DIAGNOSTIC: {item}" for item in result.diagnostics)
    lines.extend(f"WARNING: {item}" for item in result.warnings)
    if result.status is SnapshotStatus.MATCH and result.handoff is not None:
        lines.append(f"NEXT STEP: {result.handoff.exact_next_step}")
    return "\n".join(lines)


def exit_code(result: ValidationResult) -> int:
    """Map a validation result to the documented stable process exit code."""
    if result.status is SnapshotStatus.MATCH and result.handoff is not None:
        return 0
    if (
        result.status in _STALE_STATUSES
        or result.requires_user_confirmation
        or result.failure_reason is ValidationFailureReason.NO_CANDIDATE
    ):
        return 2
    return 3


class CliArgumentError(ValueError):
    """Raised for malformed CLI invocations without exposing user input."""


class _SessionArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError from None


def build_parser() -> argparse.ArgumentParser:
    """Build the save/inspect command-line contract."""
    parser = _SessionArgumentParser(description="Git-verified session snapshot tool")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect")
    inspect.add_argument("--repo", type=Path, required=True)
    inspect.add_argument("--session-root", type=Path, required=True)
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--allow-old", action="store_true")

    save = commands.add_parser("save")
    save.add_argument("--repo", type=Path, required=True)
    save.add_argument("--session-root", type=Path, required=True)
    save.add_argument("--topic", required=True)
    save.add_argument("--payload", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Save or inspect a repository-scoped snapshot."""
    try:
        args = build_parser().parse_args(argv)
        if args.command == "save":
            handoff = HandoffPayload.model_validate_json(
                args.payload.read_text(encoding="utf-8")
            )
            state = collect_repository_state(args.repo)
            snapshot = build_snapshot(
                state,
                topic=args.topic,
                handoff=handoff,
                saved_at=datetime.now().astimezone(),
            )
            destination = write_snapshot(args.session_root, snapshot)
            print(destination)
            return 0

        current = collect_repository_state(args.repo)
        result = inspect_sessions(
            args.repo,
            args.session_root,
            datetime.now().astimezone(),
            current=current,
            allow_old=args.allow_old,
        )
        output = (
            result.model_dump_json(indent=2)
            if args.json
            else render_report(result, current)
        )
        print(output)
        return exit_code(result)
    except (
        CliArgumentError,
        GitInspectionError,
        OSError,
        SnapshotStoreError,
        UnicodeError,
        ValidationError,
    ) as error:
        print(f"ERROR: {type(error).__name__}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

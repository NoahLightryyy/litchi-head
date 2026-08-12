"""Behavioral tests for fail-closed session snapshot validation."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.session_state import build_snapshot, inspect_sessions, validate_snapshot
from scripts.session_state_git import GitInspectionError, collect_repository_state
from scripts.session_state_models import HandoffPayload, SnapshotStatus
from scripts.session_state_store import load_v2, snapshot_directory, write_snapshot
from tests.test_scripts.session_state_helpers import git, init_repo, write

NOW = datetime(2026, 8, 11, 2, 0, tzinfo=UTC)


def run_cli(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts/session_state.py"), *args],
        capture_output=True,
        cwd=repo_root,
        text=True,
        check=False,
    )


def save_current(repo: Path, root: Path, saved_at: datetime = NOW) -> Path:
    state = collect_repository_state(repo)
    snapshot = build_snapshot(
        state,
        topic="recovery",
        handoff=HandoffPayload(exact_next_step="continue E0"),
        saved_at=saved_at,
    )
    return write_snapshot(root, snapshot)


def test_build_snapshot_uses_precise_zoned_id_and_copies_repository_evidence(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    write(repo, "dirty.txt", "evidence\n")
    state = collect_repository_state(repo)
    saved_at = datetime(2026, 8, 11, 10, 2, 3, 4, tzinfo=timezone(timedelta(hours=8)))
    handoff = HandoffPayload(
        current_state=("ready",),
        failed_approaches=("global mtime",),
        open_questions=("none",),
        exact_next_step="continue E0",
    )

    snapshot = build_snapshot(state, "recovery", handoff, saved_at)
    one_microsecond_later = build_snapshot(
        state,
        "recovery",
        handoff,
        saved_at + timedelta(microseconds=1),
    )

    assert snapshot.snapshot_id == f"20260811T100203000004+0800-{state.git_head[:7]}"
    assert one_microsecond_later.snapshot_id != snapshot.snapshot_id
    assert snapshot.saved_at == saved_at
    assert snapshot.project_root == state.project_root
    assert snapshot.worktree_path == state.worktree_path
    assert snapshot.branch == state.branch
    assert snapshot.git_head == state.git_head
    assert snapshot.git_dirty == state.git_dirty
    assert snapshot.dirty_paths == state.dirty_paths
    assert snapshot.handover == state.handover
    assert snapshot.latest_work_log == state.latest_work_log
    assert snapshot.sdd_progress == state.sdd_progress
    assert snapshot.topic == "recovery"
    assert snapshot.handoff == handoff


def test_matching_snapshot_can_expose_handoff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions")

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.MATCH
    assert result.handoff is not None
    assert result.handoff.exact_next_step == "continue E0"
    assert result.requires_user_confirmation is False
    assert result.warnings == ()


def test_repo_ahead_quarantines_old_next_step(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions")
    write(repo, "next.txt", "next\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "newer")

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.REPO_AHEAD
    assert result.handoff is None


def test_dirty_path_change_fails_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions")
    write(repo, "untracked.txt", "dirty\n")

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.DIRTY_MISMATCH
    assert result.handoff is None


def test_same_dirty_path_with_changed_evidence_fails_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    write(repo, "docs/01-guides/HANDOVER.md", "dirty version one\n")
    path = save_current(repo, root)
    write(repo, "docs/01-guides/HANDOVER.md", "dirty version two\n")

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.EVIDENCE_CHANGED
    assert result.handoff is None


def test_old_but_matching_snapshot_requires_confirmation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions", NOW - timedelta(days=8))
    current = collect_repository_state(repo)

    blocked = validate_snapshot(repo, path, current, NOW)
    approved = validate_snapshot(repo, path, current, NOW, allow_old=True)

    assert blocked.status is SnapshotStatus.MATCH
    assert blocked.requires_user_confirmation is True
    assert blocked.warnings == ("snapshot is 8 days old",)
    assert blocked.handoff is None
    assert approved.status is SnapshotStatus.MATCH
    assert approved.requires_user_confirmation is True
    assert approved.warnings == ("snapshot is 8 days old",)
    assert approved.handoff is not None


def test_snapshot_exactly_seven_days_old_remains_fresh(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions", NOW - timedelta(days=7))

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.MATCH
    assert result.requires_user_confirmation is False
    assert result.warnings == ()
    assert result.handoff is not None


def test_snapshot_over_seven_days_by_one_microsecond_requires_confirmation(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    saved_at = NOW - timedelta(days=7, microseconds=1)
    path = save_current(repo, tmp_path / "sessions", saved_at)

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.MATCH
    assert result.requires_user_confirmation is True
    assert result.warnings == ("snapshot is 7 days old",)
    assert result.handoff is None


def test_future_snapshot_fails_closed_without_handoff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions", NOW + timedelta(microseconds=1))

    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.diagnostics == ("snapshot saved_at is in the future",)
    assert result.handoff is None


def test_branch_project_and_diverged_head_are_distinct(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    write(repo, "linear.txt", "linear\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "linear")
    path = save_current(repo, root)
    current = collect_repository_state(repo)

    branch = validate_snapshot(repo, path, current.model_copy(update={"branch": "other"}), NOW)
    project = validate_snapshot(
        repo,
        path,
        current.model_copy(update={"project_root": str(tmp_path / "other")}),
        NOW,
    )
    git(repo, "reset", "--hard", "HEAD~1")
    write(repo, "alternate.txt", "alternate\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "alternate")
    diverged = validate_snapshot(repo, path, collect_repository_state(repo), NOW)

    assert branch.status is SnapshotStatus.BRANCH_MISMATCH
    assert branch.handoff is None
    assert project.status is SnapshotStatus.PROJECT_MISMATCH
    assert project.handoff is None
    assert diverged.status is SnapshotStatus.HEAD_DIVERGED
    assert diverged.handoff is None


def test_malformed_snapshot_hides_body_and_handoff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    current = collect_repository_state(repo)
    directory = snapshot_directory(
        tmp_path / "sessions", Path(current.project_root), Path(current.worktree_path)
    )
    directory.mkdir(parents=True)
    hidden = "private-next-step"
    path = directory / "bad-session.json"
    path.write_text(f'{{"handoff":"{hidden}"', encoding="utf-8")

    result = validate_snapshot(repo, path, current, NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.handoff is None
    assert hidden not in " ".join(result.diagnostics)
    assert result.diagnostics == ("session validation failed: SnapshotStoreError",)


def test_ancestry_error_is_class_only_and_hides_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions")
    current = collect_repository_state(repo).model_copy(update={"git_head": "f" * 40})
    hidden = "private ancestry detail"

    def fail_ancestry(*_args: object) -> bool:
        raise GitInspectionError(hidden)

    monkeypatch.setattr("scripts.session_state.is_ancestor", fail_ancestry)

    result = validate_snapshot(repo, path, current, NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.handoff is None
    assert hidden not in " ".join(result.diagnostics)
    assert result.diagnostics == ("session validation failed: GitInspectionError",)


def test_nonexistent_snapshot_head_is_malformed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    path = save_current(repo, root)
    broken = load_v2(path).model_copy(
        update={"snapshot_id": "missing-head", "git_head": "f" * 40}
    )
    broken_path = write_snapshot(root, broken)

    result = validate_snapshot(repo, broken_path, collect_repository_state(repo), NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.handoff is None
    assert result.diagnostics == ("session validation failed: GitInspectionError",)


def test_legacy_incident_never_returns_td_072_as_diagnostic_or_executable(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "2026-07-30-intraday-handover-session.tmp").write_text(
        f"# Session: 2026-07-30\n**Project:** {repo}\n## Exact Next Step\nTD-072\n",
        encoding="utf-8",
    )

    result = inspect_sessions(repo, root, NOW)

    assert result.status is SnapshotStatus.LEGACY_UNVERIFIABLE
    assert result.handoff is None
    assert "TD-072" not in " ".join(result.diagnostics)


def test_no_matching_candidate_is_malformed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    result = inspect_sessions(repo, tmp_path / "sessions", NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.snapshot_path is None
    assert result.handoff is None
    assert result.diagnostics == ("no matching session snapshot",)


def test_newest_v2_candidate_takes_priority_over_legacy(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    older = save_current(repo, root, NOW - timedelta(minutes=2))
    newer = save_current(repo, root, NOW - timedelta(minutes=1))
    (root / "2099-legacy-session.tmp").write_text(
        f"# Session: 2099\n**Project:** {repo}\n## Exact Next Step\nTD-072\n",
        encoding="utf-8",
    )

    result = inspect_sessions(repo, root, NOW)

    assert result.status is SnapshotStatus.MATCH
    assert result.snapshot_path == str(newer)
    assert result.snapshot_path != str(older)
    assert result.handoff is not None


def test_inspection_boundary_error_is_class_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path)
    hidden = "private repository detail"

    def fail_collection(_repo: Path) -> object:
        raise OSError(hidden)

    monkeypatch.setattr("scripts.session_state.collect_repository_state", fail_collection)

    result = inspect_sessions(repo, tmp_path / "sessions", NOW)

    assert result.status is SnapshotStatus.MALFORMED
    assert result.handoff is None
    assert hidden not in " ".join(result.diagnostics)
    assert result.diagnostics == ("session inspection failed: OSError",)


def test_save_then_inspect_json_round_trip_has_pure_stdout(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"exact_next_step": "continue E0"}), encoding="utf-8"
    )
    project_repo = Path(__file__).resolve().parents[2]

    saved = run_cli(
        project_repo,
        "save",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
        "--topic",
        "recovery",
        "--payload",
        str(payload),
    )
    inspected = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
        "--json",
    )

    assert saved.returncode == 0
    assert saved.stderr == ""
    assert inspected.returncode == 0
    assert inspected.stderr == ""
    report = json.loads(inspected.stdout)
    assert report["status"] == "MATCH"
    assert report["handoff"]["exact_next_step"] == "continue E0"


def test_inspect_stale_snapshot_returns_exit_2_and_hides_next_step(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    save_current(repo, root)
    write(repo, "new.txt", "new\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "advance")
    project_repo = Path(__file__).resolve().parents[2]

    result = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
    )

    assert result.returncode == 2
    assert "STATUS: REPO_AHEAD" in result.stdout
    assert "continue E0" not in result.stdout
    assert result.stderr == ""


def test_save_rejects_payload_with_unknown_fields_without_echoing_payload(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    payload = tmp_path / "payload.json"
    payload.write_text(
        '{"exact_next_step":"safe","token":"secret-value"}', encoding="utf-8"
    )
    project_repo = Path(__file__).resolve().parents[2]

    result = run_cli(
        project_repo,
        "save",
        "--repo",
        str(repo),
        "--session-root",
        str(tmp_path / "sessions"),
        "--topic",
        "recovery",
        "--payload",
        str(payload),
    )

    assert result.returncode == 3
    assert result.stdout == ""
    assert result.stderr == "ERROR: ValidationError\n"
    assert "secret-value" not in result.stderr


def test_old_match_requires_explicit_allow_old(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    save_current(repo, root, datetime.now(UTC) - timedelta(days=8))
    project_repo = Path(__file__).resolve().parents[2]

    blocked = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
    )
    approved = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
        "--allow-old",
    )

    assert blocked.returncode == 2
    assert "STATUS: MATCH" in blocked.stdout
    assert "snapshot is 8 days old" in blocked.stdout
    assert "continue E0" not in blocked.stdout
    assert approved.returncode == 0
    assert "NEXT STEP: continue E0" in approved.stdout


def test_inspect_legacy_cli_returns_exit_2_without_next_step(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "2026-07-30-intraday-handover-session.tmp").write_text(
        f"# Session: 2026-07-30\n**Project:** {repo}\n## Exact Next Step\nTD-072\n",
        encoding="utf-8",
    )
    project_repo = Path(__file__).resolve().parents[2]

    result = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(root),
    )

    assert result.returncode == 2
    assert "STATUS: LEGACY_UNVERIFIABLE" in result.stdout
    assert "2026-07-30-intraday-handover-session.tmp" in result.stdout
    assert "TD-072" not in result.stdout


def test_inspect_git_failure_reports_only_stable_exception_class(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "broken-repo"
    repo.mkdir()
    hidden = "private-git-stderr-secret"
    (repo / ".git").write_text(f"gitdir: ../{hidden}\n", encoding="utf-8")
    project_repo = Path(__file__).resolve().parents[2]

    result = run_cli(
        project_repo,
        "inspect",
        "--repo",
        str(repo),
        "--session-root",
        str(tmp_path / "sessions"),
    )

    assert result.returncode == 3
    assert result.stdout == ""
    assert result.stderr == "ERROR: GitInspectionError\n"
    assert hidden not in result.stderr

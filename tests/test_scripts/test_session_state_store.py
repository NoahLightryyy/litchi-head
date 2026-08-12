"""Tests for immutable, scoped session snapshot storage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.session_state_models import HandoffPayload, SessionSnapshotV2
from scripts.session_state_store import (
    SnapshotStoreError,
    contains_secret,
    discover_legacy,
    discover_v2,
    load_v2,
    snapshot_directory,
    write_snapshot,
)


def make_snapshot(
    project: Path,
    worktree: Path,
    *,
    snapshot_id: str = "20260811T093000+0800-aaaaaaa",
    next_step: str = "inspect",
) -> SessionSnapshotV2:
    return SessionSnapshotV2(
        snapshot_id=snapshot_id,
        saved_at=datetime(2026, 8, 11, 1, 30, tzinfo=UTC),
        project_root=str(project.resolve()),
        worktree_path=str(worktree.resolve()),
        branch="main",
        git_head="a" * 40,
        git_dirty=False,
        dirty_paths=(),
        handover=None,
        latest_work_log=None,
        sdd_progress=None,
        topic="recovery",
        handoff=HandoffPayload(exact_next_step=next_step),
    )


def test_v2_write_load_and_discovery_are_scoped_by_project_and_worktree(tmp_path: Path) -> None:
    project = tmp_path / "project"
    worktree = project / "worktree"
    other = tmp_path / "other"
    worktree.mkdir(parents=True)
    other.mkdir()

    path = write_snapshot(tmp_path / "sessions", make_snapshot(project, worktree))

    assert discover_v2(tmp_path / "sessions", project, worktree) == (path,)
    assert discover_v2(tmp_path / "sessions", other, other) == ()
    assert load_v2(path).snapshot_id.startswith("20260811")


def test_atomic_replace_failure_preserves_prior_bytes_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    previous = write_snapshot(root, make_snapshot(project, project))
    previous_bytes = previous.read_bytes()
    directory = previous.parent

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("blocked")

    monkeypatch.setattr("scripts.session_state_store.os.replace", fail_replace)

    with pytest.raises(SnapshotStoreError, match="atomic replace"):
        write_snapshot(root, make_snapshot(project, project, snapshot_id="second-snapshot"))

    assert previous.read_bytes() == previous_bytes
    assert list(directory.glob("tmp*")) == []


def test_suspected_secret_in_handoff_is_rejected_without_echoing_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = "sk-live-12345678901234567890"

    with pytest.raises(SnapshotStoreError) as caught:
        write_snapshot(tmp_path / "sessions", make_snapshot(project, project, next_step=secret))

    assert secret not in str(caught.value)
    assert contains_secret(secret)
    assert contains_secret({"api-key": "abcdefgh"})


def test_matching_legacy_header_is_history_without_retaining_next_step(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    legacy = tmp_path / "2026-07-30-old-session.tmp"
    legacy.write_text(
        f"# Session: 2026-07-30\n**Project:** {project}\n## Exact Next Step\nTD-072\n",
        encoding="utf-8",
    )

    candidates = discover_legacy(tmp_path, project)

    assert len(candidates) == 1
    assert candidates[0].project_root == str(project.resolve())
    assert candidates[0].saved_at_label == "2026-07-30"
    assert candidates[0].next_step_executable is False
    assert "TD-072" not in candidates[0].model_dump_json()


def test_duplicate_destination_is_rejected_as_immutable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = make_snapshot(project, project)
    write_snapshot(tmp_path / "sessions", snapshot)

    with pytest.raises(SnapshotStoreError, match="snapshot already exists and is immutable"):
        write_snapshot(tmp_path / "sessions", snapshot)


@pytest.mark.parametrize("malformed", [True, False])
def test_malformed_or_oversize_v2_fails_closed_without_body_values(
    tmp_path: Path, malformed: bool
) -> None:
    path = tmp_path / "snapshot-session.json"
    hidden_value = "private-body-value"
    if malformed:
        path.write_text('{"handoff":"private-body-value"', encoding="utf-8")
    else:
        path.write_bytes(
            ("{" + '"payload":"' + hidden_value + "x" * (1024 * 1024) + '"}').encode("utf-8")
        )

    with pytest.raises(SnapshotStoreError) as caught:
        load_v2(path)

    assert hidden_value not in str(caught.value)


def test_discovery_fails_closed_for_malformed_in_scope_snapshot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    directory = snapshot_directory(root, project, project)
    directory.mkdir(parents=True)
    (directory / "broken-session.json").write_text("{", encoding="utf-8")

    with pytest.raises(SnapshotStoreError, match="snapshot load failed"):
        discover_v2(root, project, project)


def test_malformed_out_of_project_and_oversize_legacy_are_skipped(tmp_path: Path) -> None:
    project = tmp_path / "project"
    other = tmp_path / "other"
    project.mkdir()
    other.mkdir()
    (tmp_path / "malformed-session.tmp").write_text("not a session", encoding="utf-8")
    (tmp_path / "other-session.tmp").write_text(f"**Project:** {other}\n", encoding="utf-8")
    (tmp_path / "large-session.tmp").write_bytes(b"x" * (1024 * 1024 + 1))

    assert discover_legacy(tmp_path, project) == ()


def test_snapshot_id_cannot_escape_scoped_destination(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    path = write_snapshot(root, make_snapshot(project, project, snapshot_id="safe-snapshot"))

    assert path.parent == snapshot_directory(root, project, project)
    assert path.is_relative_to(root / "v2")

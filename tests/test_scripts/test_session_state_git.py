"""Tests for fail-closed Git repository state collection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.session_state_models import normalize_identity_path
from tests.test_scripts.session_state_helpers import git, init_repo, write


def test_collect_repository_state_records_git_identity_dirty_paths_and_evidence(
    tmp_path: Path,
) -> None:
    from scripts.session_state_git import collect_repository_state

    repo = init_repo(tmp_path)
    write(repo, "untracked.txt", "untracked\n")

    state = collect_repository_state(repo)

    assert state.project_root == normalize_identity_path(repo)
    assert state.worktree_path == normalize_identity_path(repo)
    assert state.branch == "main"
    assert len(state.git_head) == 40
    assert state.git_dirty is True
    assert state.dirty_paths == ("untracked.txt",)
    assert state.handover is not None
    assert state.handover.path == "docs/01-guides/HANDOVER.md"
    assert state.latest_work_log is not None
    assert state.latest_work_log.path == "docs/04-changelog/logs/2026-08-10/2026-08-10-1.md"
    assert state.sdd_progress is not None
    assert state.sdd_progress.path == ".superpowers/sdd/2026-08-10-task/progress.md"


def test_collect_repository_state_records_both_rename_paths(tmp_path: Path) -> None:
    from scripts.session_state_git import collect_repository_state

    repo = init_repo(tmp_path)
    git(repo, "mv", "README.md", "RENAMED.md")

    assert collect_repository_state(repo).dirty_paths == ("README.md", "RENAMED.md")


def test_is_ancestor_uses_git_merge_base_exit_contract(tmp_path: Path) -> None:
    from scripts.session_state_git import is_ancestor

    repo = init_repo(tmp_path)
    older = git(repo, "rev-parse", "HEAD").stdout.strip()
    write(repo, "second.md", "second\n")
    git(repo, "add", "second.md")
    git(repo, "commit", "-m", "second")
    newer = git(repo, "rev-parse", "HEAD").stdout.strip()

    assert is_ancestor(repo, older, newer) is True
    assert is_ancestor(repo, newer, older) is False


def test_collect_repository_state_rejects_non_repository(tmp_path: Path) -> None:
    from scripts.session_state_git import GitInspectionError, collect_repository_state

    with pytest.raises(GitInspectionError, match="repository identity"):
        collect_repository_state(tmp_path)


def test_hash_evidence_rejects_path_outside_repository(tmp_path: Path) -> None:
    from scripts.session_state_git import GitInspectionError, hash_evidence

    repo = init_repo(tmp_path)
    outside = write(tmp_path, "outside.md", "outside\n")

    with pytest.raises(GitInspectionError, match="escapes repository"):
        hash_evidence(repo, outside)


def test_parse_porcelain_z_rejects_truncated_rename() -> None:
    from scripts.session_state_git import GitInspectionError, parse_porcelain_z

    with pytest.raises(GitInspectionError, match="truncated"):
        parse_porcelain_z("R  destination.txt\0")


def test_parse_porcelain_z_rejects_malformed_short_record() -> None:
    from scripts.session_state_git import GitInspectionError, parse_porcelain_z

    with pytest.raises(GitInspectionError, match="malformed"):
        parse_porcelain_z("M \0")


def test_parse_porcelain_z_rejects_unknown_status_code() -> None:
    from scripts.session_state_git import GitInspectionError, parse_porcelain_z

    with pytest.raises(GitInspectionError, match="malformed"):
        parse_porcelain_z("ZZ unknown.txt\0")


@pytest.mark.parametrize("output", ("?M mixed.txt\0", "A! mixed.txt\0", "U  tracked.txt\0"))
def test_parse_porcelain_z_rejects_invalid_complete_status_pairs(output: str) -> None:
    from scripts.session_state_git import GitInspectionError, parse_porcelain_z

    with pytest.raises(GitInspectionError, match="malformed"):
        parse_porcelain_z(output)


@pytest.mark.parametrize(
    ("output", "expected"),
    (
        ("M  ordinary.txt\0", ("ordinary.txt",)),
        ("T  type-changed.txt\0", ("type-changed.txt",)),
        ("R  destination.txt\0source.txt\0", ("destination.txt", "source.txt")),
        ("C  destination.txt\0source.txt\0", ("destination.txt", "source.txt")),
        ("UU conflict.txt\0", ("conflict.txt",)),
        ("?? untracked.txt\0", ("untracked.txt",)),
        ("!! ignored.txt\0", ("ignored.txt",)),
    ),
)
def test_parse_porcelain_z_accepts_complete_valid_status_pairs(
    output: str, expected: tuple[str, ...]
) -> None:
    from scripts.session_state_git import parse_porcelain_z

    assert parse_porcelain_z(output) == expected


def test_is_ancestor_rejects_git_errors(tmp_path: Path) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitInspectionError, is_ancestor

    repo = init_repo(tmp_path)
    with patch.object(session_state_git, "_git", return_value=session_state_git._GitOutput("", 2)):
        with pytest.raises(GitInspectionError, match="ancestry"):
            is_ancestor(repo, "a" * 40, "b" * 40)

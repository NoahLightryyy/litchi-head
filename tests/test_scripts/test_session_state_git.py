"""Tests for fail-closed Git repository state collection."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
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
    from scripts.session_state_git import GitOperationalError, is_ancestor

    repo = init_repo(tmp_path)
    with patch.object(
        session_state_git,
        "_git",
        side_effect=(
            session_state_git._GitOutput("a" * 40, 0),
            session_state_git._GitOutput("", 2),
        ),
    ):
        with pytest.raises(GitOperationalError, match="ancestry"):
            is_ancestor(repo, "a" * 40, "b" * 40)


def test_is_ancestor_classifies_missing_snapshot_head_without_parsing_stderr(
    tmp_path: Path,
) -> None:
    from scripts.session_state_git import SnapshotGitHeadMissingError, is_ancestor

    repo = init_repo(tmp_path)
    current = git(repo, "rev-parse", "HEAD").stdout.strip()

    with pytest.raises(SnapshotGitHeadMissingError):
        is_ancestor(repo, "f" * 40, current)


def test_git_process_launch_failure_preserves_operational_origin(
    tmp_path: Path,
) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    hidden = "private-process-launch-detail"
    with patch.object(session_state_git.subprocess, "run", side_effect=OSError(hidden)):
        with pytest.raises(GitOperationalError) as caught:
            collect_repository_state(tmp_path)

    assert hidden not in str(caught.value)


def test_git_failure_exception_discards_stdout_stderr_and_cause(tmp_path: Path) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    hidden = "private-git-process-detail"
    failed = CompletedProcess(
        args=["git"], returncode=128, stdout=hidden, stderr=hidden
    )
    with patch.object(session_state_git.subprocess, "run", return_value=failed):
        with pytest.raises(GitOperationalError) as caught:
            collect_repository_state(tmp_path)

    assert hidden not in str(caught.value)
    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_git_launch_exception_discards_original_cause(tmp_path: Path) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    hidden = "private-launch-cause"
    with patch.object(
        session_state_git.subprocess, "run", side_effect=PermissionError(hidden)
    ):
        with pytest.raises(GitOperationalError) as caught:
            collect_repository_state(tmp_path)

    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_evidence_read_io_is_sanitized_as_git_operational(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.session_state_git import GitOperationalError, hash_evidence

    repo = init_repo(tmp_path)
    evidence = repo / "README.md"
    hidden = "private-evidence-device-detail"
    original_read_bytes = Path.read_bytes

    def fail_evidence_read(path: Path) -> bytes:
        if path == evidence:
            raise PermissionError(hidden)
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_evidence_read)

    with pytest.raises(GitOperationalError) as caught:
        hash_evidence(repo, evidence)

    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_evidence_enumeration_io_is_sanitized_as_git_operational(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.session_state_git import GitOperationalError, find_latest_work_log

    hidden = "private-evidence-enumeration-detail"

    def fail_glob(_path: Path, _pattern: str) -> object:
        raise PermissionError(hidden)

    monkeypatch.setattr(Path, "glob", fail_glob)

    with pytest.raises(GitOperationalError) as caught:
        find_latest_work_log(tmp_path)

    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_handover_stat_io_is_sanitized_as_git_operational(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    repo = init_repo(tmp_path)
    handover = repo / "docs/01-guides/HANDOVER.md"
    hidden = "private-handover-stat-detail"
    original_is_file = Path.is_file

    def fail_handover_stat(path: Path) -> bool:
        if path == handover:
            raise PermissionError(hidden)
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", fail_handover_stat)

    with pytest.raises(GitOperationalError) as caught:
        collect_repository_state(repo)

    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_git_output_decode_failure_is_sanitized(tmp_path: Path) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    hidden = "private-git-decode-detail"
    decode_error = UnicodeDecodeError("utf-8", hidden.encode(), 0, 1, hidden)
    with patch.object(session_state_git.subprocess, "run", side_effect=decode_error):
        with pytest.raises(GitOperationalError) as caught:
            collect_repository_state(tmp_path)

    assert hidden not in str(caught.value)
    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None


def test_repository_identity_normalization_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import session_state_git
    from scripts.session_state_git import GitOperationalError, collect_repository_state

    repo = init_repo(tmp_path)
    hidden = "private-identity-normalization-detail"

    def fail_identity(_path: Path) -> str:
        raise PermissionError(hidden)

    monkeypatch.setattr(session_state_git, "normalize_identity_path", fail_identity)

    with pytest.raises(GitOperationalError) as caught:
        collect_repository_state(repo)

    assert hidden not in repr(caught.value.args)
    assert caught.value.__cause__ is None

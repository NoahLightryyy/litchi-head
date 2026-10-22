"""Tests for immutable, scoped session snapshot storage."""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BufferedReader
from pathlib import Path
from typing import Any, Iterator, cast

import pytest

from scripts import session_state_store
from scripts.session_state_models import HandoffPayload, SessionSnapshotV2
from scripts.session_state_store import (
    CorruptSnapshotError,
    SnapshotStoreError,
    SnapshotStoreOperationalError,
    contains_secret,
    discover_legacy,
    discover_v2,
    load_v2,
    snapshot_directory,
    write_snapshot,
)

SUSPECTED_CREDENTIALS = (
    pytest.param("sk-proj-0123456789abcdefghij", id="openai-sk"),
    pytest.param("api_key = abcdefghijklmnop", id="generic-api-key"),
    pytest.param("token: x", id="generic-token"),
    pytest.param("password=abcdefghijklmnop", id="generic-password"),
    pytest.param("secret: abcdefghijklmnop", id="generic-secret"),
    pytest.param("-----BEGIN PRIVATE KEY-----", id="pem-pkcs8"),
    pytest.param("-----BEGIN RSA PRIVATE KEY-----", id="pem-rsa"),
    pytest.param(
        "postgresql://service-user:correct-horse-battery@db.internal/app",
        id="authenticated-uri",
    ),
    pytest.param(
        "postgresql://:x@db.internal/app",
        id="authenticated-uri-without-username",
    ),
    pytest.param(
        "Server=db.internal;User Id=service;Password=x;Database=app",
        id="semicolon-connection-string",
    ),
    pytest.param(
        "Pwd=x;Server=db.internal;User Id=service",
        id="pwd-first-connection-string",
    ),
    pytest.param("AKIAIOSFODNN7EXAMPLE", id="aws-akia-access-key-id"),
    pytest.param("ASIAIOSFODNN7EXAMPLE", id="aws-asia-access-key-id"),
    pytest.param(
        "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        id="aws-secret-access-key",
    ),
    pytest.param(
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
        id="quoted-aws-secret-access-key",
    ),
    pytest.param("ghp_0123456789abcdefghijklmnopqrstuvwxyz", id="github-ghp"),
    pytest.param("gho_0123456789abcdefghijklmnopqrstuvwxyz", id="github-gho"),
    pytest.param("ghu_0123456789abcdefghijklmnopqrstuvwxyz", id="github-ghu"),
    pytest.param("ghs_0123456789abcdefghijklmnopqrstuvwxyz", id="github-ghs"),
    pytest.param("ghr_0123456789abcdefghijklmnopqrstuvwxyz", id="github-ghr"),
    pytest.param(
        "github_pat_11AA0abcdefghijklmnopqrstuvwx",
        id="github-fine-grained",
    ),
)

ALLOWED_RECOVERY_PROSE = (
    pytest.param("Review the token budget before continuing", id="token-budget"),
    pytest.param("Document the password policy", id="password-policy"),
    pytest.param("Generate a secret-free snapshot", id="secret-free"),
)

HANDCRAFTED_CREDENTIALS = (
    pytest.param(
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        id="quoted-aws-secret-access-key",
    ),
    pytest.param(
        "Pwd=round1-connection-value;Server=db.internal;User Id=service",
        "round1-connection-value",
        id="pwd-first-connection-string",
    ),
    pytest.param(
        "postgresql://:round1-uri-value@db.internal/app",
        "round1-uri-value",
        id="authenticated-uri-without-username",
    ),
)


def assert_sanitized_exception_chain(
    error: BaseException, *hidden_values: str
) -> None:
    """Require a public exception to retain no nested private exception objects."""
    pending = [error]
    visited: list[BaseException] = []
    while pending:
        current = pending.pop()
        if any(current is seen for seen in visited):
            continue
        visited.append(current)
        for hidden in hidden_values:
            assert hidden not in str(current)
            assert hidden not in repr(current.args)
        pending.extend(
            nested
            for nested in (current.__cause__, current.__context__)
            if nested is not None
        )
    assert visited == [error]


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


@contextmanager
def directory_redirection(link: Path, target: Path) -> Iterator[None]:
    """Create and safely remove a real directory redirection for this platform."""
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            pytest.skip(f"junction unavailable: exit {completed.returncode}")
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        yield
    finally:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


def test_write_rejects_preexisting_v2_reparse_component(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    root.mkdir()
    redirected = tmp_path / "redirected-v2"
    redirected.mkdir()

    with directory_redirection(root / "v2", redirected):
        with pytest.raises(SnapshotStoreOperationalError, match="snapshot scope"):
            write_snapshot(root, make_snapshot(project, project))

    assert list(redirected.iterdir()) == []


def test_discovery_rejects_preexisting_worktree_reparse_component(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    directory = snapshot_directory(root, project, project)
    directory.parent.mkdir(parents=True)
    redirected = tmp_path / "redirected-worktree"
    redirected.mkdir()

    with directory_redirection(directory, redirected):
        with pytest.raises(SnapshotStoreOperationalError, match="snapshot scope"):
            discover_v2(root, project, project)


def test_snapshot_serialization_unicode_error_is_sanitized(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    hidden = "private-serialization-payload"
    snapshot = make_snapshot(project, project).model_copy(
        update={
            "handoff": HandoffPayload.model_construct(
                exact_next_step=f"{hidden}\ud800"
            )
        }
    )

    with pytest.raises(
        SnapshotStoreOperationalError, match="snapshot serialization failed"
    ) as caught:
        write_snapshot(tmp_path / "sessions", snapshot)

    assert_sanitized_exception_chain(caught.value, hidden)


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


def test_atomic_publish_failure_preserves_prior_bytes_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    previous = write_snapshot(root, make_snapshot(project, project))
    previous_bytes = previous.read_bytes()
    directory = previous.parent

    def fail_publish(_source: object, _destination: object) -> None:
        raise OSError("blocked")

    monkeypatch.setattr("scripts.session_state_store.os.link", fail_publish)

    with pytest.raises(SnapshotStoreError, match="atomic publish") as caught:
        write_snapshot(root, make_snapshot(project, project, snapshot_id="second-snapshot"))

    assert_sanitized_exception_chain(caught.value, "blocked")
    assert previous.read_bytes() == previous_bytes
    assert list(directory.glob("tmp*")) == []


@pytest.mark.parametrize(("credential_text", "bare_credential"), HANDCRAFTED_CREDENTIALS)
def test_handcrafted_v2_credentials_are_rejected_without_leaking_body(
    tmp_path: Path, credential_text: str, bare_credential: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    path = tmp_path / "handcrafted-session.json"
    serialized_body = make_snapshot(
        project, project, next_step=credential_text
    ).model_dump_json()
    path.write_text(serialized_body, encoding="utf-8")

    with pytest.raises(SnapshotStoreError, match="suspected secret") as caught:
        load_v2(path)

    assert_sanitized_exception_chain(
        caught.value,
        bare_credential,
        credential_text,
        serialized_body,
    )


@pytest.mark.parametrize("suspected_secret", SUSPECTED_CREDENTIALS)
def test_scanner_contract_rejects_credentials_on_write_and_load(
    tmp_path: Path, suspected_secret: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    snapshot = make_snapshot(project, project, next_step=suspected_secret)

    assert contains_secret(suspected_secret)
    with pytest.raises(SnapshotStoreError, match="suspected secret") as write_error:
        write_snapshot(root, snapshot)
    assert_sanitized_exception_chain(write_error.value, suspected_secret)

    handcrafted = tmp_path / "handcrafted-session.json"
    handcrafted.write_text(snapshot.model_dump_json(), encoding="utf-8")
    with pytest.raises(SnapshotStoreError, match="suspected secret") as load_error:
        load_v2(handcrafted)
    assert_sanitized_exception_chain(load_error.value, suspected_secret)


@pytest.mark.parametrize("ordinary_prose", ALLOWED_RECOVERY_PROSE)
def test_scanner_contract_allows_ordinary_recovery_prose(
    tmp_path: Path, ordinary_prose: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = make_snapshot(project, project, next_step=ordinary_prose)

    assert not contains_secret(ordinary_prose)
    path = write_snapshot(tmp_path / "sessions", snapshot)
    assert load_v2(path).handoff.exact_next_step == ordinary_prose


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
    hidden = "private-duplicate-snapshot"
    snapshot = make_snapshot(project, project, snapshot_id=hidden)
    write_snapshot(tmp_path / "sessions", snapshot)

    with pytest.raises(
        SnapshotStoreError, match="snapshot already exists and is immutable"
    ) as caught:
        write_snapshot(tmp_path / "sessions", snapshot)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_concurrent_destination_creation_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    hidden = "private-concurrent-snapshot"
    snapshot = make_snapshot(project, project, snapshot_id=hidden)
    directory = snapshot_directory(root, project, project)
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    concurrent_bytes = b"concurrent immutable snapshot"
    original_link = session_state_store.os.link

    def create_destination_then_link(source: Path, target: Path) -> None:
        target.write_bytes(concurrent_bytes)
        original_link(source, target)

    monkeypatch.setattr(session_state_store.os, "link", create_destination_then_link)

    with pytest.raises(
        SnapshotStoreError, match="snapshot already exists and is immutable"
    ) as caught:
        write_snapshot(root, snapshot)

    assert_sanitized_exception_chain(caught.value, hidden)
    assert destination.read_bytes() == concurrent_bytes
    assert list(destination.parent.glob("tmp*")) == []


def test_temp_cleanup_failure_rolls_back_published_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    snapshot = make_snapshot(project, project)
    directory = snapshot_directory(root, project, project)
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    original_unlink = Path.unlink

    def fail_temp_unlink(path: Path, missing_ok: bool = False) -> None:
        if path.name.startswith("tmp"):
            raise OSError("cleanup blocked")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_temp_unlink)

    with pytest.raises(SnapshotStoreError, match="atomic publish cleanup failed") as caught:
        write_snapshot(root, snapshot)

    assert_sanitized_exception_chain(caught.value, "cleanup blocked")
    assert not destination.exists()


def test_cleanup_and_rollback_failure_has_stable_integrity_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = "sk-live-12345678901234567890"
    snapshot = make_snapshot(project, project, next_step="not-secret")

    def fail_unlink(_path: Path, missing_ok: bool = False) -> None:
        raise OSError("cleanup blocked")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(SnapshotStoreError, match="atomic publish integrity failure") as caught:
        write_snapshot(tmp_path / "sessions", snapshot)

    assert secret not in str(caught.value)
    assert_sanitized_exception_chain(caught.value, "cleanup blocked")


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point contract")
def test_windows_load_delegates_reparse_rejection_to_opened_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "reparse-session.json"
    called: list[Path] = []

    def reject_reparse(path: Path) -> int:
        called.append(path)
        raise SnapshotStoreError("snapshot must be a regular file")

    monkeypatch.setattr(session_state_store, "_open_windows_snapshot_file", reject_reparse)

    with pytest.raises(SnapshotStoreError, match="regular file"):
        load_v2(target)

    assert called == [target]


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point contract")
def test_windows_reparse_point_is_rejected_by_opened_handle(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "source-session.json"
    source.write_text(make_snapshot(project, project).model_dump_json(), encoding="utf-8")
    replacement = tmp_path / "replacement-session.json"
    try:
        replacement.symlink_to(source)
    except OSError as error:
        pytest.skip(f"symlink unavailable: {type(error).__name__}")

    with pytest.raises(SnapshotStoreError, match="snapshot must be a regular file"):
        load_v2(replacement)


def test_load_uses_one_capped_handle_read_when_file_grows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "growing-session.json"
    path.write_bytes(b"{}")
    original_open = session_state_store.os.open
    original_fdopen = session_state_store.os.fdopen
    read_sizes: list[int] = []

    class TrackedHandle:
        def __init__(self, handle: BufferedReader) -> None:
            self._handle = handle

        def __enter__(self) -> TrackedHandle:
            return self

        def __exit__(self, *args: object) -> None:
            self._handle.close()

        def close(self) -> None:
            self._handle.close()

        def fileno(self) -> int:
            return self._handle.fileno()

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            assert size == 1024 * 1024 + 1
            return b"x" * size

    def tracked_open(target: Path, flags: int) -> int:
        return original_open(target, flags)

    def tracked_fdopen(descriptor: int, mode: str) -> TrackedHandle:
        handle = cast(BufferedReader, cast(Any, original_fdopen)(descriptor, mode))
        return TrackedHandle(handle)

    def fail_unbounded_read(_target: Path) -> bytes:
        raise AssertionError("load_v2 must not call Path.read_bytes")

    monkeypatch.setattr(session_state_store.os, "open", tracked_open)
    monkeypatch.setattr(session_state_store.os, "fdopen", tracked_fdopen)
    monkeypatch.setattr(Path, "read_bytes", fail_unbounded_read)

    with pytest.raises(SnapshotStoreError, match="1 MiB"):
        load_v2(path)

    assert read_sizes == [1024 * 1024 + 1]


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

    assert_sanitized_exception_chain(caught.value, hidden_value)


def test_discovery_fails_closed_for_malformed_in_scope_snapshot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    directory = snapshot_directory(root, project, project)
    directory.mkdir(parents=True)
    (directory / "broken-session.json").write_text("{", encoding="utf-8")

    with pytest.raises(SnapshotStoreError, match="snapshot load failed") as caught:
        discover_v2(root, project, project)

    assert_sanitized_exception_chain(caught.value, "{")


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


def test_invalid_snapshot_bytes_preserve_corrupt_origin(tmp_path: Path) -> None:
    path = tmp_path / "invalid-session.json"
    path.write_bytes(b'\xff{"private":"payload"}')

    with pytest.raises(CorruptSnapshotError) as caught:
        load_v2(path)

    assert "private" not in str(caught.value)
    assert_sanitized_exception_chain(caught.value, "private")


def test_snapshot_read_permission_failure_preserves_operational_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unreadable-session.json"
    hidden = "private-device-detail"

    def fail_open(_path: Path) -> BufferedReader:
        raise PermissionError(hidden)

    monkeypatch.setattr(session_state_store, "_open_snapshot_file", fail_open)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        load_v2(path)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_snapshot_discovery_permission_failure_preserves_operational_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    directory = snapshot_directory(tmp_path / "sessions", project, project)
    hidden = "private-directory-detail"
    original_stat = Path.stat

    def fail_target_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if path == directory:
            raise PermissionError(hidden)
        return original_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", fail_target_stat)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_v2(tmp_path / "sessions", project, project)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_legacy_discovery_permission_failure_preserves_operational_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    legacy = tmp_path / "private-session.tmp"
    legacy.write_text(f"**Project:** {project}\n", encoding="utf-8")
    hidden = "private-legacy-device-detail"
    original_stat = Path.stat

    def fail_legacy_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if path == legacy:
            raise PermissionError(hidden)
        return original_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", fail_legacy_stat)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_legacy(tmp_path, project)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_legacy_candidate_with_missing_claimed_project_is_skipped(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    missing = tmp_path / "retired-project"
    (tmp_path / "stale-session.tmp").write_text(
        f"**Project:** {missing}\n", encoding="utf-8"
    )
    matching = tmp_path / "matching-session.tmp"
    matching.write_text(f"**Project:** {project}\n", encoding="utf-8")

    assert discover_legacy(tmp_path, project)[0].path == str(matching.resolve())


def test_store_operational_exception_discards_io_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unreadable-session.json"
    hidden = "private-store-cause"

    def fail_open(_path: Path) -> BufferedReader:
        raise PermissionError(hidden)

    monkeypatch.setattr(session_state_store, "_open_snapshot_file", fail_open)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        load_v2(path)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_snapshot_directory_creation_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    directory = snapshot_directory(root, project, project)
    hidden = "private-directory-creation-detail"
    original_mkdir = Path.mkdir

    def fail_directory_mkdir(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if path == directory:
            raise PermissionError(hidden)
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fail_directory_mkdir)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        write_snapshot(root, make_snapshot(project, project))

    assert_sanitized_exception_chain(caught.value, hidden)


def test_store_root_enumeration_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    hidden = "private-root-enumeration-detail"

    def fail_root_glob(_path: Path, _pattern: str) -> object:
        raise PermissionError(hidden)

    monkeypatch.setattr(Path, "glob", fail_root_glob)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_legacy(tmp_path, project)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_v2_scope_resolution_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    hidden = "private-scope-resolution-detail"

    def fail_scope(_path: Path) -> str:
        raise PermissionError(hidden)

    monkeypatch.setattr(session_state_store, "path_key", fail_scope)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_v2(tmp_path / "sessions", project, project)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_legacy_scope_resolution_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    hidden = "private-legacy-scope-detail"

    def fail_identity(_path: Path) -> str:
        raise PermissionError(hidden)

    monkeypatch.setattr(session_state_store, "normalize_identity_path", fail_identity)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_legacy(tmp_path, project)

    assert_sanitized_exception_chain(caught.value, hidden)


def test_legacy_candidate_identity_io_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    candidate_project = tmp_path / "candidate-project"
    project.mkdir()
    candidate_project.mkdir()
    (tmp_path / "candidate-session.tmp").write_text(
        f"**Project:** {candidate_project}\n", encoding="utf-8"
    )
    hidden = "private-candidate-identity-detail"
    original_identity = session_state_store.normalize_identity_path

    def fail_candidate_identity(path: Path) -> str:
        if path == candidate_project:
            raise PermissionError(hidden)
        return original_identity(path)

    monkeypatch.setattr(
        session_state_store, "normalize_identity_path", fail_candidate_identity
    )

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        discover_legacy(tmp_path, project)

    assert_sanitized_exception_chain(caught.value, hidden)


@pytest.mark.parametrize("failure_site", ("path_key", "resolve"))
def test_snapshot_directory_sanitizes_scope_resolution_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_site: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    hidden = f"private-snapshot-directory-{failure_site}"

    if failure_site == "path_key":

        def fail_path_key(_path: Path) -> str:
            raise PermissionError(hidden)

        monkeypatch.setattr(session_state_store, "path_key", fail_path_key)
    else:
        original_resolve = Path.resolve

        def fail_project_resolve(path: Path, *, strict: bool = False) -> Path:
            if path == project:
                raise PermissionError(hidden)
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", fail_project_resolve)

    with pytest.raises(SnapshotStoreOperationalError) as caught:
        snapshot_directory(tmp_path / "sessions", project, project)

    assert_sanitized_exception_chain(caught.value, hidden)

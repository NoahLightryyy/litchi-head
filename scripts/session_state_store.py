"""Immutable, project-scoped storage for verified session snapshots."""

from __future__ import annotations

import ctypes
import json
import os
import re
import stat
import tempfile
from contextlib import closing
from pathlib import Path
from typing import BinaryIO, Callable, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from scripts.session_state_models import (
    SessionSnapshotV2,
    normalize_identity_path,
    path_key,
)

_MAX_SNAPSHOT_BYTES = 1024 * 1024
_WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|secret)\b[\"']?\s*[:=]\s*"
        r"[\"']?[^\s\"',;]+"
    ),
    re.compile(r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@?#]*:[^@\s/?#]+@"),
    re.compile(r"(?i)(?:^|;)\s*(?:password|pwd)\s*=\s*[^;\s\"']+"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(
        r"(?i)\baws_secret_access_key\b[\"']?\s*[:=]\s*"
        r"[\"']?[A-Za-z0-9/+=]{40}"
    ),
    re.compile(
        r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9]{20,}\b"
        r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    ),
)
_T = TypeVar("_T")


class SnapshotStoreError(RuntimeError):
    """Raised when a session snapshot cannot be safely stored or read."""


class CorruptSnapshotError(SnapshotStoreError):
    """Raised when snapshot bytes or schema are intrinsically invalid."""


class SnapshotStoreOperationalError(SnapshotStoreError):
    """Raised when the environment prevents snapshot storage access."""


class LegacySnapshot(BaseModel):
    """Non-executable metadata recovered from a legacy handover file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    project_root: str
    saved_at_label: str | None
    next_step_executable: bool = False


def _store_io(action: Callable[[], _T], diagnostic: str) -> _T:
    """Translate filesystem I/O only after its private exception context ends."""
    try:
        result = action()
    except OSError:
        failure = SnapshotStoreOperationalError(diagnostic)
    else:
        return result
    raise failure


def _read_legacy_candidate(path: Path) -> tuple[str, Path] | None:
    """Read one bounded legacy candidate while preserving the pre-read size gate."""
    if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
        return None
    return (
        path.read_text(encoding="utf-8-sig", errors="replace"),
        path.resolve(strict=True),
    )


def contains_secret(value: object) -> bool:
    """Return whether JSON-compatible data contains a likely credential."""
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    pending = [value]
    raw_strings: list[str] = []
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            raw_strings.append(current)
        elif isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return any(
        pattern.search(text) is not None
        for text in (serialized, *raw_strings)
        for pattern in _SECRET_PATTERNS
    )


def _reject_suspected_secret(value: object) -> None:
    """Apply the shared snapshot scanner without retaining credential values."""
    if contains_secret(value):
        raise SnapshotStoreError("snapshot contains a suspected secret field")


def snapshot_directory(root: Path, project: Path, worktree: Path) -> Path:
    """Return the non-reversible project/worktree namespace below ``root``."""
    return _store_io(
        lambda: root / "v2" / path_key(project) / path_key(worktree),
        "snapshot scope resolution failed",
    )


def _reject_existing_scope_redirections(root: Path, directory: Path) -> None:
    """Reject redirections already present in the scoped directory chain."""
    components = (root, root / "v2", directory.parent, directory)

    def inspect() -> None:
        for component in components:
            try:
                metadata = os.lstat(component)
            except FileNotFoundError:
                continue
            is_reparse_point = bool(
                getattr(metadata, "st_file_attributes", 0)
                & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT
            )
            if stat.S_ISLNK(metadata.st_mode) or is_reparse_point:
                raise SnapshotStoreOperationalError(
                    "snapshot scope contains a redirection"
                )

    _store_io(inspect, "snapshot scope validation failed")


def write_snapshot(root: Path, snapshot: SessionSnapshotV2) -> Path:
    """Atomically write one immutable UTF-8 v2 snapshot."""
    encoded: bytes | None = None
    serialization_failure: SnapshotStoreOperationalError | None = None
    try:
        payload = snapshot.model_dump(mode="json")
        _reject_suspected_secret(payload)
        encoded = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    except SnapshotStoreError:
        raise
    except UnicodeError:
        serialization_failure = SnapshotStoreOperationalError(
            "snapshot serialization failed"
        )
    if serialization_failure is not None:
        raise serialization_failure
    if encoded is None:
        raise SnapshotStoreOperationalError("snapshot serialization failed")

    directory = snapshot_directory(
        root, Path(snapshot.project_root), Path(snapshot.worktree_path)
    )
    _reject_existing_scope_redirections(root, directory)
    _store_io(
        lambda: directory.mkdir(parents=True, exist_ok=True),
        "snapshot directory creation failed",
    )
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    except FileExistsError:
        publish_failure = SnapshotStoreError(
            "snapshot already exists and is immutable"
        )
    except OSError:
        publish_failure = SnapshotStoreOperationalError("atomic publish failed")
    else:
        publish_failure = None
    if publish_failure is not None:
        _remove_temporary(temporary)
        raise publish_failure
    cleanup_failure: SnapshotStoreError | None = None
    try:
        _remove_temporary(temporary)
    except SnapshotStoreError as error:
        cleanup_failure = error
    if cleanup_failure is not None:
        rollback_failed = False
        try:
            destination.unlink()
        except OSError:
            rollback_failed = True
        if rollback_failed:
            raise SnapshotStoreOperationalError("atomic publish integrity failure")
        raise cleanup_failure
    return destination


def _remove_temporary(temporary: Path | None) -> None:
    if temporary is None:
        return
    _store_io(temporary.unlink, "atomic publish cleanup failed")


def _open_windows_snapshot_file(path: Path) -> int:
    """Open a Windows file without following a reparse point."""
    from ctypes import WinDLL, byref, get_last_error, wintypes

    create_file = WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    get_attributes = WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    get_attributes.argtypes = (
        wintypes.HANDLE,
        wintypes.INT,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    get_attributes.restype = wintypes.BOOL
    close_handle = WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    file_flag_open_reparse_point = 0x00200000
    file_attribute_normal = 0x00000080
    generic_read = 0x80000000
    open_existing = 3
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    invalid_handle_value = wintypes.HANDLE(-1).value

    handle = create_file(
        str(path),
        generic_read,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_attribute_normal | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle_value:
        raise OSError(get_last_error(), "CreateFileW failed")

    class _FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    info = _FileAttributeTagInfo()
    file_attribute_tag_info = 9
    if not get_attributes(handle, file_attribute_tag_info, byref(info), ctypes.sizeof(info)):
        close_handle(handle)
        raise OSError(get_last_error(), "GetFileInformationByHandleEx failed")
    if info.FileAttributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT:
        close_handle(handle)
        raise CorruptSnapshotError("snapshot must be a regular file")
    import msvcrt

    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        close_handle(handle)
        raise


def _open_snapshot_file(path: Path) -> BinaryIO:
    if os.name == "nt":
        descriptor = _open_windows_snapshot_file(path)
    else:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    return os.fdopen(descriptor, "rb")


def load_v2(path: Path) -> SessionSnapshotV2:
    """Load and validate a bounded v2 snapshot without exposing its contents."""
    loaded: SessionSnapshotV2 | None = None
    failure: SnapshotStoreError | None = None
    try:
        with closing(_open_snapshot_file(path)) as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise CorruptSnapshotError("snapshot must be a regular file")
            encoded = handle.read(_MAX_SNAPSHOT_BYTES + 1)
        if len(encoded) > _MAX_SNAPSHOT_BYTES:
            raise CorruptSnapshotError("snapshot exceeds the 1 MiB limit")
        loaded = SessionSnapshotV2.model_validate_json(encoded)
        _reject_suspected_secret(loaded.model_dump(mode="json"))
    except SnapshotStoreError:
        raise
    except OSError:
        failure = SnapshotStoreOperationalError("snapshot access failed")
    except (UnicodeError, ValidationError, ValueError):
        failure = CorruptSnapshotError("snapshot load failed")
    if failure is not None:
        raise failure
    if loaded is None:
        raise CorruptSnapshotError("snapshot load failed")
    return loaded


def discover_v2(root: Path, project: Path, worktree: Path) -> tuple[Path, ...]:
    """Find every valid in-scope snapshot in chronological order."""
    loaded: list[tuple[object, Path]] | None = None
    failure: SnapshotStoreOperationalError | None = None
    try:
        directory = snapshot_directory(root, project, worktree)
        _reject_existing_scope_redirections(root, directory)
        if not directory.exists():
            return ()
        loaded = [
            (load_v2(path).saved_at, path)
            for path in directory.glob("*-session.json")
        ]
    except SnapshotStoreError:
        raise
    except OSError:
        failure = SnapshotStoreOperationalError("snapshot discovery failed")
    if failure is not None:
        raise failure
    if loaded is None:
        raise SnapshotStoreOperationalError("snapshot discovery failed")
    return tuple(path for _, path in sorted(loaded, key=lambda item: (item[0], str(item[1]))))


def discover_legacy(root: Path, project: Path) -> tuple[LegacySnapshot, ...]:
    """Return matching legacy files as quarantined, non-executable history."""
    expected = _store_io(
        lambda: normalize_identity_path(project), "legacy project access failed"
    )
    project_pattern = re.compile(r"^\*\*Project:\*\*\s*(.+?)\s*$", re.MULTILINE)
    date_pattern = re.compile(r"^# Session:\s*(.+?)\s*$", re.MULTILINE)
    matches: list[LegacySnapshot] = []
    legacy_paths = _store_io(
        lambda: sorted(root.glob("*-session.tmp")),
        "legacy snapshot discovery failed",
    )
    for path in legacy_paths:
        candidate = _store_io(
            lambda: _read_legacy_candidate(path),
            "legacy snapshot discovery failed",
        )
        if candidate is None:
            continue
        text, resolved_path = candidate
        project_match = project_pattern.search(text)
        if project_match is None:
            continue
        candidate_project = Path(project_match.group(1).strip())
        candidate_failure: SnapshotStoreOperationalError | None = None
        try:
            candidate_identity = normalize_identity_path(candidate_project)
            resolved_project = candidate_project.resolve(strict=True)
        except FileNotFoundError:
            continue
        except OSError:
            candidate_failure = SnapshotStoreOperationalError(
                "legacy project identity failed"
            )
        except ValueError:
            continue
        if candidate_failure is not None:
            raise candidate_failure
        if candidate_identity != expected:
            continue
        date_match = date_pattern.search(text)
        matches.append(
            LegacySnapshot(
                path=str(resolved_path),
                project_root=str(resolved_project),
                saved_at_label=date_match.group(1).strip() if date_match else None,
            )
        )
    return tuple(matches)

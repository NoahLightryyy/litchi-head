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
from typing import BinaryIO

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
        r"[\"']?[^\s\"']{8,}"
    ),
)


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


def contains_secret(value: object) -> bool:
    """Return whether JSON-compatible data contains a likely credential."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return any(pattern.search(text) is not None for pattern in _SECRET_PATTERNS)


def snapshot_directory(root: Path, project: Path, worktree: Path) -> Path:
    """Return the non-reversible project/worktree namespace below ``root``."""
    return root / "v2" / path_key(project) / path_key(worktree)


def write_snapshot(root: Path, snapshot: SessionSnapshotV2) -> Path:
    """Atomically write one immutable UTF-8 v2 snapshot."""
    payload = snapshot.model_dump(mode="json")
    if contains_secret(payload):
        raise SnapshotStoreError("snapshot contains a suspected secret field")

    directory = snapshot_directory(
        root, Path(snapshot.project_root), Path(snapshot.worktree_path)
    )
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    except FileExistsError as error:
        _remove_temporary(temporary)
        raise SnapshotStoreError("snapshot already exists and is immutable") from error
    except OSError as error:
        _remove_temporary(temporary)
        raise SnapshotStoreError(f"atomic publish failed: {type(error).__name__}") from error
    try:
        _remove_temporary(temporary)
    except SnapshotStoreError as cleanup_error:
        try:
            destination.unlink()
        except OSError as rollback_error:
            raise SnapshotStoreError("atomic publish integrity failure") from rollback_error
        raise cleanup_error
    return destination


def _remove_temporary(temporary: Path | None) -> None:
    if temporary is None:
        return
    try:
        temporary.unlink()
    except OSError as error:
        raise SnapshotStoreError(
            f"atomic publish cleanup failed: {type(error).__name__}"
        ) from error


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
    try:
        with closing(_open_snapshot_file(path)) as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise CorruptSnapshotError("snapshot must be a regular file")
            encoded = handle.read(_MAX_SNAPSHOT_BYTES + 1)
        if len(encoded) > _MAX_SNAPSHOT_BYTES:
            raise CorruptSnapshotError("snapshot exceeds the 1 MiB limit")
        return SessionSnapshotV2.model_validate_json(encoded)
    except SnapshotStoreError:
        raise
    except OSError as error:
        raise SnapshotStoreOperationalError(
            f"snapshot access failed: {type(error).__name__}"
        ) from error
    except (UnicodeError, ValidationError, ValueError) as error:
        raise CorruptSnapshotError(
            f"snapshot load failed: {type(error).__name__}"
        ) from error


def discover_v2(root: Path, project: Path, worktree: Path) -> tuple[Path, ...]:
    """Find every valid in-scope snapshot in chronological order."""
    directory = snapshot_directory(root, project, worktree)
    try:
        if not directory.exists():
            return ()
        loaded = [
            (load_v2(path).saved_at, path)
            for path in directory.glob("*-session.json")
        ]
    except SnapshotStoreError:
        raise
    except OSError as error:
        raise SnapshotStoreOperationalError(
            f"snapshot discovery failed: {type(error).__name__}"
        ) from error
    return tuple(path for _, path in sorted(loaded, key=lambda item: (item[0], str(item[1]))))


def discover_legacy(root: Path, project: Path) -> tuple[LegacySnapshot, ...]:
    """Return matching legacy files as quarantined, non-executable history."""
    expected = normalize_identity_path(project)
    project_pattern = re.compile(r"^\*\*Project:\*\*\s*(.+?)\s*$", re.MULTILINE)
    date_pattern = re.compile(r"^# Session:\s*(.+?)\s*$", re.MULTILINE)
    matches: list[LegacySnapshot] = []
    for path in sorted(root.glob("*-session.tmp")):
        try:
            if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            resolved_path = path.resolve(strict=True)
        except OSError as error:
            raise SnapshotStoreOperationalError(
                f"legacy snapshot discovery failed: {type(error).__name__}"
            ) from error
        project_match = project_pattern.search(text)
        if project_match is None:
            continue
        candidate_project = Path(project_match.group(1).strip())
        try:
            candidate_identity = normalize_identity_path(candidate_project)
            resolved_project = candidate_project.resolve(strict=True)
        except FileNotFoundError:
            continue
        except OSError as error:
            raise SnapshotStoreOperationalError(
                f"legacy project identity failed: {type(error).__name__}"
            ) from error
        except ValueError:
            continue
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

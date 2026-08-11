# Session Recovery Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, project/worktree-scoped session snapshot tool and make both global Codex Skills and litchi-head workflow rules use Git-verified recovery instead of “globally newest file” recovery.

**Architecture:** Repository-owned Python modules provide the testable v2 snapshot contract, Git/evidence collection, atomic storage, candidate validation, and CLI. Global `resume-session`/`save-session` Skills orchestrate that CLI when available and otherwise follow an equally strict read-only fallback; project documents define Git/worktree as the fact source and snapshots as disposable cache.

**Tech Stack:** Python 3.12+, Pydantic 2, standard-library `argparse`/`hashlib`/`json`/`pathlib`/`subprocess`/`tempfile`, Pytest 8, Git CLI, Markdown Skills and project workflow documents.

## Global Constraints

- Add no runtime or development dependency.
- Every Python function and Pydantic field has complete type annotations; Ruff and Pyright remain clean.
- `inspect` is read-only and must never run `checkout`, `reset`, `clean`, `merge`, `commit`, or `push`.
- A legacy `.tmp` snapshot can only produce `LEGACY_UNVERIFIABLE`; it can never expose an executable next step.
- Git command failure, malformed data, path escape, identity mismatch, or evidence mismatch fails closed with a stable diagnostic.
- Windows path identity is case-insensitive after absolute resolution; different worktrees remain distinct.
- Snapshot JSON is UTF-8, schema version `2`, secret-free, project/worktree scoped, and written by same-directory atomic replacement.
- Direct desktop-window exit remains outside the guaranteed automation boundary; do not claim an unavailable lifecycle hook.
- Implement every behavioral task with a witnessed RED → GREEN cycle and commit after its reviewer gate.
- Preserve unrelated user changes, do not push, and do not delete or rewrite legacy session files.
- Use `apply_patch` for edits and `python scripts/check.py --full` for the final project gate.

---

## File Map

| File | Responsibility |
|:-----|:---------------|
| `scripts/session_state_models.py` | v2 Pydantic contracts, status enum, normalized path/key helpers, stable public types |
| `scripts/session_state_git.py` | Git identity/status/ancestry collection and evidence file hashing/discovery |
| `scripts/session_state_store.py` | Secret scan, atomic v2 write/load/discovery, legacy header discovery |
| `scripts/session_state.py` | Snapshot builder, consistency state machine, human/JSON reports, CLI exit codes |
| `tests/test_scripts/session_state_helpers.py` | Temporary Git repo, commit, worktree, evidence, and payload fixtures shared by tests |
| `tests/test_scripts/test_session_state_models.py` | Contract, path identity, and key tests |
| `tests/test_scripts/test_session_state_git.py` | Git/evidence collection and fail-closed tests |
| `tests/test_scripts/test_session_state_store.py` | Atomic storage, secret rejection, scoped discovery, legacy parsing tests |
| `tests/test_scripts/test_session_state.py` | Validation state machine, CLI, and 2026-08-10 incident regression |
| `docs/01-guides/workflow/SESSION_RECOVERY.md` | Project-owned canonical recovery and save operator guide |
| `C:/Users/rog/.agents/skills/source-command-resume-session/SKILL.md` | Global recovery orchestration and strict fallback |
| `C:/Users/rog/.agents/skills/source-command-save-session/SKILL.md` | Global v2 save orchestration and trigger contract |

---

### Task 1: Freeze Snapshot Contracts and Path Identity

**Files:**
- Create: `scripts/session_state_models.py`
- Create: `tests/test_scripts/session_state_helpers.py`
- Create: `tests/test_scripts/test_session_state_models.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `Field`, `ConfigDict`; standard-library `datetime`, `Enum`, `hashlib`, `pathlib`.
- Produces: `SnapshotStatus`, `EvidenceRef`, `HandoffPayload`, `SessionSnapshotV2`, `RepositoryState`, `ValidationResult`, `normalize_identity_path(path: Path) -> str`, and `path_key(path: Path) -> str`.

- [ ] **Step 1: Write failing contract and path tests**

```python
# tests/test_scripts/test_session_state_models.py
from datetime import UTC, datetime
from pathlib import Path

import os

import pytest
from pydantic import ValidationError

from scripts.session_state_models import (
    EvidenceRef,
    HandoffPayload,
    SessionSnapshotV2,
    SnapshotStatus,
    normalize_identity_path,
    path_key,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows path identity contract")
def test_windows_identity_is_case_insensitive(tmp_path: Path) -> None:
    assert normalize_identity_path(tmp_path) == normalize_identity_path(
        Path(str(tmp_path).swapcase())
    )


def test_path_key_is_stable_and_does_not_expose_the_path(tmp_path: Path) -> None:
    first = path_key(tmp_path)
    second = path_key(tmp_path)
    assert first == second
    assert len(first) == 24
    assert tmp_path.name.casefold() not in first


def test_snapshot_rejects_naive_saved_at(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="saved_at"):
        SessionSnapshotV2(
            snapshot_id="snapshot-1",
            saved_at=datetime(2026, 8, 11, 9, 30),
            project_root=str(tmp_path),
            worktree_path=str(tmp_path),
            branch="main",
            git_head="a" * 40,
            git_dirty=False,
            dirty_paths=(),
            handover=None,
            latest_work_log=None,
            sdd_progress=None,
            topic="recovery",
            handoff=HandoffPayload(exact_next_step="run inspect"),
        )


def test_snapshot_contract_is_immutable_and_forbids_unknown_fields(tmp_path: Path) -> None:
    snapshot = SessionSnapshotV2(
        snapshot_id="snapshot-1",
        saved_at=datetime(2026, 8, 11, 1, 30, tzinfo=UTC),
        project_root=str(tmp_path),
        worktree_path=str(tmp_path),
        branch="main",
        git_head="a" * 40,
        git_dirty=False,
        dirty_paths=(),
        handover=EvidenceRef(path="docs/01-guides/HANDOVER.md", sha256="b" * 64),
        latest_work_log=None,
        sdd_progress=None,
        topic="recovery",
        handoff=HandoffPayload(exact_next_step="run inspect"),
    )
    assert snapshot.schema_version == 2
    assert SnapshotStatus.LEGACY_UNVERIFIABLE.value == "LEGACY_UNVERIFIABLE"
    with pytest.raises(ValidationError):
        snapshot.model_copy(update={"unknown": True}).model_validate(
            {**snapshot.model_dump(), "unknown": True}
        )


def test_snapshot_id_cannot_escape_its_directory(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="snapshot_id"):
        SessionSnapshotV2(
            snapshot_id="../escape",
            saved_at=datetime(2026, 8, 11, 1, 30, tzinfo=UTC),
            project_root=str(tmp_path),
            worktree_path=str(tmp_path),
            branch="main",
            git_head="a" * 40,
            git_dirty=False,
            dirty_paths=(),
            handover=None,
            latest_work_log=None,
            sdd_progress=None,
            topic="recovery",
            handoff=HandoffPayload(exact_next_step="inspect"),
        )
```

- [ ] **Step 2: Run the tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_state_models.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'scripts.session_state_models'`.

- [ ] **Step 3: Implement immutable contracts and helpers**

```python
# scripts/session_state_models.py
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SnapshotStatus(StrEnum):
    MATCH = "MATCH"
    REPO_AHEAD = "REPO_AHEAD"
    HEAD_DIVERGED = "HEAD_DIVERGED"
    BRANCH_MISMATCH = "BRANCH_MISMATCH"
    DIRTY_MISMATCH = "DIRTY_MISMATCH"
    EVIDENCE_CHANGED = "EVIDENCE_CHANGED"
    PROJECT_MISMATCH = "PROJECT_MISMATCH"
    LEGACY_UNVERIFIABLE = "LEGACY_UNVERIFIABLE"
    MALFORMED = "MALFORMED"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceRef(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HandoffPayload(FrozenModel):
    current_state: tuple[str, ...] = ()
    failed_approaches: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    exact_next_step: str = Field(min_length=1)


class RepositoryState(FrozenModel):
    project_root: str
    worktree_path: str
    branch: str
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dirty: bool
    dirty_paths: tuple[str, ...]
    handover: EvidenceRef | None
    latest_work_log: EvidenceRef | None
    sdd_progress: EvidenceRef | None

    @model_validator(mode="after")
    def dirty_flag_matches_paths(self) -> "RepositoryState":
        if self.git_dirty != bool(self.dirty_paths):
            raise ValueError("git_dirty must match dirty_paths")
        return self


class SessionSnapshotV2(FrozenModel):
    schema_version: int = Field(default=2, ge=2, le=2)
    snapshot_id: str = Field(pattern=r"^[A-Za-z0-9+_-]{1,96}$")
    saved_at: datetime
    project_root: str
    worktree_path: str
    branch: str
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dirty: bool
    dirty_paths: tuple[str, ...]
    handover: EvidenceRef | None
    latest_work_log: EvidenceRef | None
    sdd_progress: EvidenceRef | None
    topic: str = Field(min_length=1)
    handoff: HandoffPayload

    @field_validator("saved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("saved_at must include a timezone")
        return value

    @model_validator(mode="after")
    def dirty_flag_matches_paths(self) -> "SessionSnapshotV2":
        if self.git_dirty != bool(self.dirty_paths):
            raise ValueError("git_dirty must match dirty_paths")
        return self


class ValidationResult(FrozenModel):
    status: SnapshotStatus
    snapshot_path: str | None
    diagnostics: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    requires_user_confirmation: bool = False
    handoff: HandoffPayload | None = None


def normalize_identity_path(path: Path) -> str:
    resolved = str(path.resolve(strict=True))
    normalized = os.path.normcase(os.path.normpath(resolved))
    return normalized.casefold() if os.name == "nt" else normalized


def path_key(path: Path) -> str:
    identity = normalize_identity_path(path).encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:24]
```

- [ ] **Step 4: Run focused tests and witness GREEN**

Run: `python -m pytest tests/test_scripts/test_session_state_models.py -q`

Expected: all tests pass.

- [ ] **Step 5: Run local quality checks and commit**

Run: `ruff check scripts/session_state_models.py tests/test_scripts/test_session_state_models.py tests/test_scripts/session_state_helpers.py`

Commit:

```powershell
git add scripts/session_state_models.py tests/test_scripts/session_state_helpers.py tests/test_scripts/test_session_state_models.py
git commit -m "feat: define session snapshot contracts"
```

---

### Task 2: Collect Git Identity, Dirty Paths, and Evidence

**Files:**
- Create: `scripts/session_state_git.py`
- Modify: `tests/test_scripts/session_state_helpers.py`
- Create: `tests/test_scripts/test_session_state_git.py`

**Interfaces:**
- Consumes: `EvidenceRef`, `RepositoryState`, `normalize_identity_path` from Task 1.
- Produces: `GitInspectionError`, `collect_repository_state(repo: Path) -> RepositoryState`, `is_ancestor(repo: Path, older: str, newer: str) -> bool`, `hash_evidence(repo: Path, path: Path) -> EvidenceRef`, `find_latest_work_log(repo: Path) -> Path | None`, and `find_latest_sdd_progress(repo: Path) -> Path | None`.

- [ ] **Step 1: Add temporary Git repository helpers**

```python
# tests/test_scripts/session_state_helpers.py
from __future__ import annotations

import subprocess
from pathlib import Path


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], capture_output=True, check=check, cwd=repo, text=True
    )


def write(repo: Path, relative: str, content: str) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write(repo, "README.md", "base\n")
    write(repo, "docs/01-guides/HANDOVER.md", "handover\n")
    write(repo, "docs/04-changelog/logs/2026-08-10/2026-08-10.md", "log\n")
    write(repo, ".superpowers/sdd/2026-08-10-task/progress.md", "progress\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo
```

- [ ] **Step 2: Write failing Git and evidence tests**

```python
# tests/test_scripts/test_session_state_git.py
from pathlib import Path

import pytest

from scripts.session_state_git import (
    GitInspectionError,
    collect_repository_state,
    hash_evidence,
    is_ancestor,
    parse_porcelain_z,
)
from tests.test_scripts.session_state_helpers import git, init_repo, write


def test_collects_branch_head_dirty_paths_and_evidence(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    write(repo, "new.txt", "untracked\n")
    state = collect_repository_state(repo)
    assert state.branch == "main"
    assert len(state.git_head) == 40
    assert state.git_dirty is True
    assert state.dirty_paths == ("new.txt",)
    assert state.handover is not None
    assert state.handover.path == "docs/01-guides/HANDOVER.md"
    assert state.latest_work_log is not None
    assert state.sdd_progress is not None


def test_rename_records_source_and_destination(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "mv", "README.md", "RENAMED.md")
    state = collect_repository_state(repo)
    assert state.dirty_paths == ("README.md", "RENAMED.md")


def test_is_ancestor_distinguishes_linear_history(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    older = git(repo, "rev-parse", "HEAD").stdout.strip()
    write(repo, "next.txt", "next\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "next")
    newer = git(repo, "rev-parse", "HEAD").stdout.strip()
    assert is_ancestor(repo, older, newer) is True
    assert is_ancestor(repo, newer, older) is False


def test_git_failure_is_not_treated_as_empty_state(tmp_path: Path) -> None:
    with pytest.raises(GitInspectionError, match="repository identity"):
        collect_repository_state(tmp_path)


def test_evidence_cannot_escape_repository(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    outside = write(tmp_path, "outside.txt", "outside\n")
    with pytest.raises(GitInspectionError, match="escapes repository"):
        hash_evidence(repo, outside)


def test_truncated_rename_status_fails_closed() -> None:
    with pytest.raises(GitInspectionError, match="truncated rename"):
        parse_porcelain_z("R  destination.txt\0")
```

- [ ] **Step 3: Run focused tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_state_git.py -q`

Expected: collection fails because `scripts.session_state_git` does not exist.

- [ ] **Step 4: Implement fail-closed Git and evidence collection**

```python
# scripts/session_state_git.py
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from scripts.session_state_models import EvidenceRef, RepositoryState, normalize_identity_path


class GitInspectionError(RuntimeError):
    pass


def _git(
    repo: Path,
    operation: str,
    *args: str,
    ok: tuple[int, ...] = (0,),
    strip: bool = True,
) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, cwd=repo, text=True
    )
    if result.returncode not in ok:
        detail = " ".join((result.stderr or result.stdout).strip().splitlines())
        raise GitInspectionError(
            f"{operation} failed (exit {result.returncode}): {detail or 'no diagnostic output'}"
        )
    return result.stdout.strip() if strip else result.stdout


def parse_porcelain_z(output: str) -> tuple[str, ...]:
    records = output.split("\0")
    if records and records[-1] == "":
        records.pop()
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        if len(record) < 4 or record[2] != " ":
            raise GitInspectionError("working-tree status returned malformed porcelain data")
        status = record[:2]
        paths.add(record[3:].replace("\\", "/"))
        if "R" in status or "C" in status:
            index += 1
            if index >= len(records) or not records[index]:
                raise GitInspectionError("working-tree status returned a truncated rename")
            paths.add(records[index].replace("\\", "/"))
        index += 1
    return tuple(sorted(paths))


def hash_evidence(repo: Path, path: Path) -> EvidenceRef:
    resolved_repo = repo.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(resolved_repo).as_posix()
    except ValueError as error:
        raise GitInspectionError(f"evidence path escapes repository: {resolved}") from error
    return EvidenceRef(path=relative, sha256=hashlib.sha256(resolved.read_bytes()).hexdigest())


def find_latest_work_log(repo: Path) -> Path | None:
    root = repo / "docs/04-changelog/logs"
    candidates = sorted(root.glob("????-??-??/????-??-??*.md")) if root.exists() else []
    return candidates[-1] if candidates else None


def find_latest_sdd_progress(repo: Path) -> Path | None:
    root = repo / ".superpowers/sdd"
    candidates = list(root.glob("*/progress.md")) if root.exists() else []
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.as_posix())) if candidates else None


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        capture_output=True,
        cwd=repo,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = " ".join((result.stderr or result.stdout).strip().splitlines())
    raise GitInspectionError(f"commit ancestry failed (exit {result.returncode}): {detail}")


def collect_repository_state(repo: Path) -> RepositoryState:
    worktree = Path(_git(repo, "repository identity", "rev-parse", "--show-toplevel"))
    common_dir_raw = Path(_git(repo, "common Git directory", "rev-parse", "--git-common-dir"))
    common_dir = common_dir_raw if common_dir_raw.is_absolute() else worktree / common_dir_raw
    common_dir = common_dir.resolve(strict=True)
    project_root = common_dir.parent if common_dir.name == ".git" else worktree
    branch = _git(repo, "branch identity", "symbolic-ref", "--quiet", "--short", "HEAD")
    head = _git(repo, "HEAD identity", "rev-parse", "--verify", "HEAD")
    status = _git(
        repo,
        "working-tree status",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        strip=False,
    )
    dirty_paths = parse_porcelain_z(status)
    handover_path = worktree / "docs/01-guides/HANDOVER.md"
    log_path = find_latest_work_log(worktree)
    sdd_path = find_latest_sdd_progress(worktree)
    return RepositoryState(
        project_root=normalize_identity_path(project_root),
        worktree_path=normalize_identity_path(worktree),
        branch=branch,
        git_head=head,
        git_dirty=bool(dirty_paths),
        dirty_paths=dirty_paths,
        handover=hash_evidence(worktree, handover_path) if handover_path.exists() else None,
        latest_work_log=hash_evidence(worktree, log_path) if log_path else None,
        sdd_progress=hash_evidence(worktree, sdd_path) if sdd_path else None,
    )
```

- [ ] **Step 5: Run tests, Ruff, and commit**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_git.py -q
ruff check scripts/session_state_git.py tests/test_scripts/test_session_state_git.py tests/test_scripts/session_state_helpers.py
```

Expected: all tests and Ruff pass.

Commit:

```powershell
git add scripts/session_state_git.py tests/test_scripts/session_state_helpers.py tests/test_scripts/test_session_state_git.py
git commit -m "feat: inspect session repository evidence"
```

---

### Task 3: Add Scoped Atomic Storage and Legacy Quarantine

**Files:**
- Create: `scripts/session_state_store.py`
- Create: `tests/test_scripts/test_session_state_store.py`

**Interfaces:**
- Consumes: `SessionSnapshotV2`, `normalize_identity_path`, and `path_key` from Task 1.
- Produces: `SnapshotStoreError`, `LegacySnapshot`, `snapshot_directory(root: Path, project: Path, worktree: Path) -> Path`, `write_snapshot(root: Path, snapshot: SessionSnapshotV2) -> Path`, `discover_v2(root: Path, project: Path, worktree: Path) -> tuple[Path, ...]`, `load_v2(path: Path) -> SessionSnapshotV2`, `discover_legacy(root: Path, project: Path) -> tuple[LegacySnapshot, ...]`, and `contains_secret(value: object) -> bool`.

- [ ] **Step 1: Write failing storage and legacy tests**

```python
# tests/test_scripts/test_session_state_store.py
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.session_state_models import HandoffPayload, SessionSnapshotV2
from scripts.session_state_store import (
    SnapshotStoreError,
    discover_legacy,
    discover_v2,
    load_v2,
    write_snapshot,
)


def make_snapshot(project: Path, worktree: Path, *, next_step: str = "inspect") -> SessionSnapshotV2:
    return SessionSnapshotV2(
        snapshot_id="20260811T093000+0800-" + "a" * 7,
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


def test_write_and_discover_are_scoped_by_project_and_worktree(tmp_path: Path) -> None:
    project = tmp_path / "project"
    worktree = project / "worktree"
    other = tmp_path / "other"
    worktree.mkdir(parents=True)
    other.mkdir()
    path = write_snapshot(tmp_path / "sessions", make_snapshot(project, worktree))
    assert discover_v2(tmp_path / "sessions", project, worktree) == (path,)
    assert discover_v2(tmp_path / "sessions", other, other) == ()
    assert load_v2(path).snapshot_id.startswith("20260811")


def test_atomic_replace_failure_preserves_previous_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "sessions"
    snapshot = make_snapshot(project, project)
    previous = write_snapshot(root, snapshot)
    previous_bytes = previous.read_bytes()
    monkeypatch.setattr("scripts.session_state_store.os.replace", lambda *_: (_ for _ in ()).throw(OSError("blocked")))
    with pytest.raises(SnapshotStoreError, match="atomic replace"):
        write_snapshot(
            root,
            snapshot.model_copy(update={"snapshot_id": "second-snapshot", "topic": "changed"}),
        )
    assert previous.read_bytes() == previous_bytes


def test_secret_is_rejected_without_echoing_value(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = "sk-live-12345678901234567890"
    with pytest.raises(SnapshotStoreError) as caught:
        write_snapshot(tmp_path / "sessions", make_snapshot(project, project, next_step=secret))
    assert secret not in str(caught.value)


def test_legacy_snapshot_is_only_project_matched_history(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    legacy = tmp_path / "2026-07-30-old-session.tmp"
    legacy.write_text(f"# Session\n**Project:** {project}\n## Exact Next Step\nTD-072\n", encoding="utf-8")
    candidates = discover_legacy(tmp_path, project)
    assert len(candidates) == 1
    assert candidates[0].project_root == str(project.resolve())
    assert candidates[0].next_step_executable is False


def test_existing_snapshot_is_immutable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    snapshot = make_snapshot(project, project)
    write_snapshot(tmp_path / "sessions", snapshot)
    with pytest.raises(SnapshotStoreError, match="already exists"):
        write_snapshot(tmp_path / "sessions", snapshot)
```

- [ ] **Step 2: Run focused tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_state_store.py -q`

Expected: collection fails because `scripts.session_state_store` does not exist.

- [ ] **Step 3: Implement storage, secret scan, and legacy parser**

```python
# scripts/session_state_store.py
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from scripts.session_state_models import SessionSnapshotV2, normalize_identity_path, path_key

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s]{8,}"),
)


class SnapshotStoreError(RuntimeError):
    pass


class LegacySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: str
    project_root: str
    saved_at_label: str | None
    next_step_executable: bool = False


def contains_secret(value: object) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def snapshot_directory(root: Path, project: Path, worktree: Path) -> Path:
    return root / "v2" / path_key(project) / path_key(worktree)


def write_snapshot(root: Path, snapshot: SessionSnapshotV2) -> Path:
    payload = snapshot.model_dump(mode="json")
    if contains_secret(payload):
        raise SnapshotStoreError("snapshot contains a suspected secret field")
    directory = snapshot_directory(
        root, Path(snapshot.project_root), Path(snapshot.worktree_path)
    )
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{snapshot.snapshot_id}-session.json"
    if destination.exists():
        raise SnapshotStoreError("snapshot already exists and is immutable")
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise SnapshotStoreError(f"atomic replace failed: {type(error).__name__}") from error
    return destination


def load_v2(path: Path) -> SessionSnapshotV2:
    try:
        if path.stat().st_size > 1024 * 1024:
            raise SnapshotStoreError("snapshot exceeds the 1 MiB limit")
        return SessionSnapshotV2.model_validate_json(path.read_text(encoding="utf-8"))
    except SnapshotStoreError:
        raise
    except (OSError, ValidationError) as error:
        raise SnapshotStoreError(
            f"snapshot load failed: {type(error).__name__}"
        ) from error


def discover_v2(root: Path, project: Path, worktree: Path) -> tuple[Path, ...]:
    directory = snapshot_directory(root, project, worktree)
    if not directory.exists():
        return ()
    loaded = [(load_v2(path).saved_at, path) for path in directory.glob("*-session.json")]
    return tuple(path for _, path in sorted(loaded, key=lambda item: (item[0], str(item[1]))))


def discover_legacy(root: Path, project: Path) -> tuple[LegacySnapshot, ...]:
    expected = normalize_identity_path(project)
    project_pattern = re.compile(r"^\*\*Project:\*\*\s*(.+?)\s*$", re.MULTILINE)
    date_pattern = re.compile(r"^# Session:\s*(.+?)\s*$", re.MULTILINE)
    matches: list[LegacySnapshot] = []
    for path in sorted(root.glob("*-session.tmp")):
        try:
            if path.stat().st_size > 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            project_match = project_pattern.search(text)
            if project_match is None:
                continue
            candidate_project = Path(project_match.group(1).strip())
            if normalize_identity_path(candidate_project) != expected:
                continue
            date_match = date_pattern.search(text)
        except (OSError, ValueError):
            continue
        matches.append(
            LegacySnapshot(
                path=str(path.resolve(strict=True)),
                project_root=str(candidate_project.resolve(strict=True)),
                saved_at_label=date_match.group(1).strip() if date_match else None,
            )
        )
    return tuple(matches)
```

- [ ] **Step 4: Run tests, Ruff, and commit**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_store.py -q
ruff check scripts/session_state_store.py tests/test_scripts/test_session_state_store.py
```

Expected: all tests and Ruff pass.

Commit:

```powershell
git add scripts/session_state_store.py tests/test_scripts/test_session_state_store.py
git commit -m "feat: store scoped session snapshots"
```

---

### Task 4: Implement the Fail-Closed Validation State Machine

**Files:**
- Create: `scripts/session_state.py`
- Create: `tests/test_scripts/test_session_state.py`

**Interfaces:**
- Consumes: all public types/functions from Tasks 1-3.
- Produces: `build_snapshot(state: RepositoryState, topic: str, handoff: HandoffPayload, saved_at: datetime) -> SessionSnapshotV2`, `validate_snapshot(repo: Path, snapshot_path: Path, current: RepositoryState, now: datetime, allow_old: bool = False) -> ValidationResult`, `inspect_sessions(repo: Path, session_root: Path, now: datetime, current: RepositoryState | None = None, allow_old: bool = False) -> ValidationResult`, `render_report(result: ValidationResult, current: RepositoryState) -> str`, and `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing state-machine tests**

```python
# tests/test_scripts/test_session_state.py
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.session_state import build_snapshot, inspect_sessions, validate_snapshot
from scripts.session_state_git import GitInspectionError, collect_repository_state
from scripts.session_state_models import HandoffPayload, SnapshotStatus
from scripts.session_state_store import load_v2, snapshot_directory, write_snapshot
from tests.test_scripts.session_state_helpers import git, init_repo, write


NOW = datetime(2026, 8, 11, 2, 0, tzinfo=UTC)


def save_current(repo: Path, root: Path, saved_at: datetime = NOW) -> Path:
    state = collect_repository_state(repo)
    snapshot = build_snapshot(
        state,
        topic="recovery",
        handoff=HandoffPayload(exact_next_step="continue E0"),
        saved_at=saved_at,
    )
    return write_snapshot(root, snapshot)


def test_matching_snapshot_can_expose_handoff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions")
    current = collect_repository_state(repo)
    result = validate_snapshot(repo, path, current, NOW)
    assert result.status is SnapshotStatus.MATCH
    assert result.handoff is not None
    assert result.handoff.exact_next_step == "continue E0"


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
    dirty = validate_snapshot(repo, path, collect_repository_state(repo), NOW)
    assert dirty.status is SnapshotStatus.DIRTY_MISMATCH


def test_same_dirty_path_with_changed_evidence_fails_closed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    write(repo, "docs/01-guides/HANDOVER.md", "dirty version one\n")
    path = save_current(repo, root)
    write(repo, "docs/01-guides/HANDOVER.md", "dirty version two\n")
    evidence = validate_snapshot(repo, path, collect_repository_state(repo), NOW)
    assert evidence.status is SnapshotStatus.EVIDENCE_CHANGED


def test_old_but_matching_snapshot_requires_confirmation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    path = save_current(repo, tmp_path / "sessions", NOW - timedelta(days=8))
    result = validate_snapshot(repo, path, collect_repository_state(repo), NOW)
    assert result.status is SnapshotStatus.MATCH
    assert result.requires_user_confirmation is True
    assert result.warnings == ("snapshot is 8 days old",)
    assert result.handoff is None
    approved = validate_snapshot(repo, path, collect_repository_state(repo), NOW, allow_old=True)
    assert approved.handoff is not None


def test_branch_project_and_diverged_head_are_distinct(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    write(repo, "linear.txt", "linear\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "linear")
    path = save_current(repo, root)
    current = collect_repository_state(repo)
    branch = validate_snapshot(repo, path, current.model_copy(update={"branch": "other"}), NOW)
    assert branch.status is SnapshotStatus.BRANCH_MISMATCH
    project = validate_snapshot(
        repo, path, current.model_copy(update={"project_root": str(tmp_path / "other")}), NOW
    )
    assert project.status is SnapshotStatus.PROJECT_MISMATCH
    git(repo, "reset", "--hard", "HEAD~1")
    write(repo, "alternate.txt", "alternate\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "alternate")
    diverged = validate_snapshot(repo, path, collect_repository_state(repo), NOW)
    assert diverged.status is SnapshotStatus.HEAD_DIVERGED


def test_malformed_snapshot_and_git_error_hide_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    current = collect_repository_state(repo)
    directory = snapshot_directory(root, Path(current.project_root), Path(current.worktree_path))
    directory.mkdir(parents=True)
    (directory / "bad-session.json").write_text("{bad", encoding="utf-8")
    malformed = inspect_sessions(repo, root, NOW, current=current)
    assert malformed.status is SnapshotStatus.MALFORMED
    assert malformed.handoff is None
    for child in directory.iterdir():
        child.unlink()
    path = save_current(repo, root)
    monkeypatch.setattr(
        "scripts.session_state.is_ancestor",
        lambda *_: (_ for _ in ()).throw(GitInspectionError("ancestry unavailable")),
    )
    snapshot_state = collect_repository_state(repo)
    advanced = snapshot_state.model_copy(update={"git_head": "f" * 40})
    failed = validate_snapshot(repo, path, advanced, NOW)
    assert failed.status is SnapshotStatus.MALFORMED
    assert failed.handoff is None


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


def test_legacy_incident_never_returns_td_072_as_executable(tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run focused tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_state.py -q`

Expected: collection fails because the new public functions are missing.

- [ ] **Step 3: Implement snapshot building and ordered validation**

```python
# scripts/session_state.py
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


def validate_snapshot(
    repo: Path,
    snapshot_path: Path,
    current: RepositoryState,
    now: datetime,
    allow_old: bool = False,
) -> ValidationResult:
    try:
        snapshot = load_v2(snapshot_path)
    except SnapshotStoreError as error:
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=str(snapshot_path),
            diagnostics=(str(error),),
        )
    common = {"snapshot_path": str(snapshot_path), "handoff": None}
    if snapshot.project_root != current.project_root or snapshot.worktree_path != current.worktree_path:
        return ValidationResult(status=SnapshotStatus.PROJECT_MISMATCH, diagnostics=("project/worktree identity differs",), **common)
    if snapshot.branch != current.branch:
        return ValidationResult(status=SnapshotStatus.BRANCH_MISMATCH, diagnostics=("branch differs",), **common)
    if snapshot.git_head != current.git_head:
        try:
            ancestor = is_ancestor(repo, snapshot.git_head, current.git_head)
        except GitInspectionError as error:
            return ValidationResult(
                status=SnapshotStatus.MALFORMED,
                diagnostics=(str(error),),
                **common,
            )
        if ancestor:
            return ValidationResult(status=SnapshotStatus.REPO_AHEAD, diagnostics=("repository advanced after snapshot",), **common)
        return ValidationResult(status=SnapshotStatus.HEAD_DIVERGED, diagnostics=("snapshot HEAD is not an ancestor of current HEAD",), **common)
    if snapshot.dirty_paths != current.dirty_paths:
        return ValidationResult(status=SnapshotStatus.DIRTY_MISMATCH, diagnostics=("dirty path set differs",), **common)
    if (snapshot.handover, snapshot.latest_work_log, snapshot.sdd_progress) != (
        current.handover, current.latest_work_log, current.sdd_progress
    ):
        return ValidationResult(status=SnapshotStatus.EVIDENCE_CHANGED, diagnostics=("handover/log/SDD evidence changed",), **common)
    age_days = (now - snapshot.saved_at).days
    warning = (f"snapshot is {age_days} days old",) if age_days > 7 else ()
    return ValidationResult(
        status=SnapshotStatus.MATCH,
        snapshot_path=str(snapshot_path),
        diagnostics=("snapshot matches current repository evidence",),
        warnings=warning,
        requires_user_confirmation=bool(warning),
        handoff=snapshot.handoff if allow_old or not warning else None,
    )


def inspect_sessions(
    repo: Path,
    session_root: Path,
    now: datetime,
    current: RepositoryState | None = None,
    allow_old: bool = False,
) -> ValidationResult:
    try:
        observed = current or collect_repository_state(repo)
        project = Path(observed.project_root)
        worktree = Path(observed.worktree_path)
        candidates = discover_v2(session_root, project, worktree)
        if candidates:
            return validate_snapshot(
                repo, candidates[-1], observed, now, allow_old=allow_old
            )
        legacy = discover_legacy(session_root, project)
        if legacy:
            candidate = legacy[-1]
            return ValidationResult(
                status=SnapshotStatus.LEGACY_UNVERIFIABLE,
                snapshot_path=candidate.path,
                diagnostics=("legacy snapshot has no verifiable Git/evidence identity",),
            )
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=("no matching session snapshot",),
        )
    except (GitInspectionError, SnapshotStoreError, OSError, ValueError) as error:
        return ValidationResult(
            status=SnapshotStatus.MALFORMED,
            snapshot_path=None,
            diagnostics=(f"session inspection failed: {type(error).__name__}",),
        )
```

- [ ] **Step 4: Run tests and witness GREEN**

Run: `python -m pytest tests/test_scripts/test_session_state.py -q`

Expected: all state-machine and incident tests pass.

- [ ] **Step 5: Run all session-state tests and commit**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py -q
ruff check scripts/session_state*.py tests/test_scripts/test_session_state*.py tests/test_scripts/session_state_helpers.py
```

Expected: all tests and Ruff pass.

Commit:

```powershell
git add scripts/session_state.py tests/test_scripts/test_session_state.py
git commit -m "feat: validate session recovery state"
```

---

### Task 5: Add Save/Inspect CLI and Stable Reports

**Files:**
- Modify: `scripts/session_state.py`
- Modify: `tests/test_scripts/test_session_state.py`

**Interfaces:**
- Consumes: `build_snapshot`, `inspect_sessions`, `write_snapshot`, and `HandoffPayload`.
- Produces CLI commands:
  - `python scripts/session_state.py inspect --repo PATH --session-root PATH [--json] [--allow-old]`
  - `python scripts/session_state.py save --repo PATH --session-root PATH --topic TEXT --payload PATH`
- Exit codes: `0=fresh MATCH/explicitly approved old MATCH/save success`, `2=confirmation required/stale/mismatch/legacy/no candidate`, `3=malformed/operational failure`.

- [ ] **Step 1: Write failing CLI tests**

```python
# append to tests/test_scripts/test_session_state.py
import json
import subprocess
import sys


def run_cli(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts/session_state.py"), *args],
        capture_output=True,
        cwd=repo_root,
        text=True,
    )


def test_save_then_inspect_json_round_trip(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"exact_next_step": "continue E0"}), encoding="utf-8")
    project_repo = Path(__file__).resolve().parents[2]
    saved = run_cli(
        project_repo, "save", "--repo", str(repo), "--session-root", str(root),
        "--topic", "recovery", "--payload", str(payload)
    )
    assert saved.returncode == 0
    inspected = run_cli(
        project_repo, "inspect", "--repo", str(repo), "--session-root", str(root), "--json"
    )
    assert inspected.returncode == 0
    report = json.loads(inspected.stdout)
    assert report["status"] == "MATCH"
    assert report["handoff"]["exact_next_step"] == "continue E0"


def test_inspect_stale_snapshot_returns_exit_2_and_hides_next_step(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    save_current(repo, root)
    write(repo, "new.txt", "new\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "advance")
    project_repo = Path(__file__).resolve().parents[2]
    result = run_cli(project_repo, "inspect", "--repo", str(repo), "--session-root", str(root))
    assert result.returncode == 2
    assert "REPO_AHEAD" in result.stdout
    assert "continue E0" not in result.stdout


def test_save_rejects_payload_with_unknown_fields(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = tmp_path / "payload.json"
    payload.write_text('{"exact_next_step":"safe","token":"secret-value"}', encoding="utf-8")
    project_repo = Path(__file__).resolve().parents[2]
    result = run_cli(
        project_repo, "save", "--repo", str(repo), "--session-root", str(tmp_path / "sessions"),
        "--topic", "recovery", "--payload", str(payload)
    )
    assert result.returncode == 3
    assert "secret-value" not in result.stderr


def test_old_match_requires_explicit_allow_old(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    root = tmp_path / "sessions"
    save_current(repo, root, NOW - timedelta(days=8))
    project_repo = Path(__file__).resolve().parents[2]
    blocked = run_cli(
        project_repo, "inspect", "--repo", str(repo), "--session-root", str(root)
    )
    assert blocked.returncode == 2
    assert "continue E0" not in blocked.stdout
    approved = run_cli(
        project_repo, "inspect", "--repo", str(repo), "--session-root", str(root), "--allow-old"
    )
    assert approved.returncode == 0
    assert "continue E0" in approved.stdout
```

- [ ] **Step 2: Run CLI tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_state.py -q -k 'round_trip or inspect_stale or save_rejects or allow_old'`

Expected: tests fail because `main()` and CLI parsers are not implemented.

- [ ] **Step 3: Implement parser, reports, and exit mapping**

```python
# merge these imports above the existing `if __package__` bootstrap in scripts/session_state.py
import argparse
import json
from datetime import datetime

from pydantic import ValidationError

from scripts.session_state_store import SnapshotStoreError, write_snapshot

STALE_STATUSES = {
    SnapshotStatus.REPO_AHEAD,
    SnapshotStatus.HEAD_DIVERGED,
    SnapshotStatus.BRANCH_MISMATCH,
    SnapshotStatus.DIRTY_MISMATCH,
    SnapshotStatus.EVIDENCE_CHANGED,
    SnapshotStatus.PROJECT_MISMATCH,
    SnapshotStatus.LEGACY_UNVERIFIABLE,
}


def render_report(result: ValidationResult, current: RepositoryState) -> str:
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
    if result.status is SnapshotStatus.MATCH and not result.requires_user_confirmation:
        return 0
    if result.status in STALE_STATUSES or result.requires_user_confirmation:
        return 2
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Git-verified session snapshot tool")
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
    args = build_parser().parse_args(argv)
    try:
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
        print(result.model_dump_json(indent=2) if args.json else render_report(result, current))
        return exit_code(result)
    except (OSError, ValidationError, GitInspectionError, SnapshotStoreError) as error:
        print(f"ERROR: {type(error).__name__}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI and complete suite GREEN**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state.py -q
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run real read-only incident check**

Run:

```powershell
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
```

Expected before the first v2 save: exit `2`, status `LEGACY_UNVERIFIABLE`, the report identifies the 2026-07-30 historical candidate, and it does not print TD-072 as a next step.

- [ ] **Step 6: Commit**

```powershell
git add scripts/session_state.py tests/test_scripts/test_session_state.py
git commit -m "feat: add session recovery CLI"
```

---

### Task 6: Wire Global Skills and Project Workflow Rules

**Files:**
- Create: `docs/01-guides/workflow/SESSION_RECOVERY.md`
- Modify: `AGENTS.md:11`
- Modify: `docs/01-guides/workflow/STARTUP.md:164-198`
- Modify: `docs/01-guides/workflow/CLOSING.md:1-120`
- Modify: `docs/01-guides/WORKFLOW.md`
- Modify: `docs/01-guides/HANDOVER.md:46,61,92,145`
- Modify: `README.md`
- Modify: `C:/Users/rog/.agents/skills/source-command-resume-session/SKILL.md`
- Modify: `C:/Users/rog/.agents/skills/source-command-save-session/SKILL.md`
- Create: `tests/test_scripts/test_session_recovery_policy.py`

**Interfaces:**
- Consumes: Task 5 CLI and v2 contract.
- Produces: one project-owned operator policy, two global Skill orchestration contracts, and repository documentation contract tests.

- [ ] **Step 1: Write failing project policy tests**

```python
# tests/test_scripts/test_session_recovery_policy.py
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def test_startup_requires_combined_git_verified_recovery() -> None:
    agents = read("AGENTS.md")
    startup = read("docs/01-guides/workflow/STARTUP.md")
    assert "Git/worktree 是事实源" in agents
    assert "python scripts/session_state.py inspect" in startup
    assert "LEGACY_UNVERIFIABLE" in startup
    assert "不得执行快照中的下一步" in startup


def test_closing_lists_only_guaranteed_save_triggers() -> None:
    closing = read("docs/01-guides/workflow/CLOSING.md")
    assert "python scripts/session_state.py save" in closing
    assert "原子功能提交后" in closing
    assert "上下文耗尽" in closing
    assert "直接关闭桌面窗口" in closing
    assert "无法保证" in closing


def test_handover_and_readme_expose_current_recovery_status() -> None:
    handover = read("docs/01-guides/HANDOVER.md")
    readme = read("README.md")
    assert "2026-08-11" in handover
    assert "会话快照不是事实源" in handover
    assert "Git 校验的会话恢复" in readme
```

- [ ] **Step 2: Run policy tests and witness RED**

Run: `python -m pytest tests/test_scripts/test_session_recovery_policy.py -q`

Expected: all three tests fail because policy text is absent or stale.

- [ ] **Step 3: Add canonical project recovery guide**

Create `docs/01-guides/workflow/SESSION_RECOVERY.md` with these exact sections and rules:

```markdown
# 会话恢复与保存

## 权威顺序

Git/worktree 是事实源；当前分支 SDD、HANDOVER 和最新工作日志是状态说明；通过一致性
校验的 v2 快照是缓存；旧 `.tmp` 和原始任务 JSONL 仅供追溯。

## 启动

运行 `python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"`。
只有 `MATCH` 可生成恢复简报；超过 7 天还需用户确认。`REPO_AHEAD`、`HEAD_DIVERGED`、
`BRANCH_MISMATCH`、`DIRTY_MISMATCH`、`EVIDENCE_CHANGED`、`LEGACY_UNVERIFIABLE` 或
`MALFORMED` 都不得执行快照中的下一步，必须按 Git → SDD → HANDOVER → 最新日志重建状态。

## 保存

先创建只包含 `HandoffPayload` 字段的 UTF-8 JSON，再运行 `python scripts/session_state.py save`。
原子功能提交后、用户明确收尾、上下文耗尽、切换 worktree/任务前必须保存。直接关闭桌面
窗口无法保证触发仓库流程；系统依靠下一次恢复时失败关闭兜底。

## 安全边界

恢复只读，不自动 checkout/reset/clean/merge/push；旧快照不删除；疑似凭据拒绝写入且不回显。
```

- [ ] **Step 4: Replace project rule ambiguity and stale handover date**

Change AGENTS rule 1 to:

```markdown
1. **会话启动**：Git/worktree 是事实源。先执行 `/resume-session`，并强制用
   `python scripts/session_state.py inspect`、当前 Git、SDD、HANDOVER 与最新工作日志组合校验；
   快照不是事实源，非 `MATCH` 时不得执行其中的下一步。
```

Add the same command/status behavior to STARTUP; add the guaranteed save triggers and direct-window-close limitation to CLOSING; link `SESSION_RECOVERY.md` from WORKFLOW; change HANDOVER’s “下次会话启动点” date to `2026-08-11` and add the fail-closed policy. Because HANDOVER is a public-status file, add a README project-quality bullet named `Git 校验的会话恢复` in the same commit so the ordered README gate closes.

- [ ] **Step 5: Rewrite the global resume Skill orchestration**

Apply these mandatory semantics to `C:/Users/rog/.agents/skills/source-command-resume-session/SKILL.md`:

```markdown
1. Resolve the current workspace and Git worktree before reading any snapshot body.
2. If `scripts/session_state.py` exists, run its `inspect` command against `~/.Codex/session-data`.
3. Only `MATCH` may expose `exact_next_step`; a snapshot older than 7 days also requires user confirmation.
4. Every other status triggers read-only repository recovery: Git status/log, current SDD progress,
   HANDOVER, ROADMAP when needed, and the latest work log.
5. A legacy `.tmp` is historical evidence only. Never print “Ready to continue” from it and never
   execute its next step.
6. If the repository has no validator script, perform the same project/worktree/branch/HEAD checks
   manually and fail closed when any fact is unavailable. Never fall back to global-mtime authority.
```

Remove the old instruction to select the globally most recently modified `*-session.tmp`, and update the briefing to include `WORKTREE`, `BRANCH`, `HEAD`, `SNAPSHOT`, `STATUS`, conflicts, and authority source.

- [ ] **Step 6: Rewrite the global save Skill orchestration**

Apply these mandatory semantics to `C:/Users/rog/.agents/skills/source-command-save-session/SKILL.md`:

```markdown
1. Require a Git repository and collect the current worktree, branch, full HEAD, dirty paths,
   HANDOVER, latest work log, and SDD evidence.
2. Create a temporary UTF-8 `HandoffPayload` JSON containing only current_state,
   failed_approaches, open_questions, and exact_next_step.
3. Run `python scripts/session_state.py save --repo <worktree> --session-root
   ~/.Codex/session-data --topic <topic> --payload <payload>` when the project tool exists.
4. Delete only the temporary payload after a successful or failed call; never delete snapshots.
5. Refuse to save secrets and never echo rejected values.
6. Do not claim direct desktop-window close is automatically intercepted.
```

Keep legacy-format reading compatibility in resume only; all new saves use v2.

- [ ] **Step 7: Run policy tests and verify both global Skill files**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_recovery_policy.py -q
$resume = Get-Content -LiteralPath 'C:\Users\rog\.agents\skills\source-command-resume-session\SKILL.md' -Raw -Encoding UTF8
$save = Get-Content -LiteralPath 'C:\Users\rog\.agents\skills\source-command-save-session\SKILL.md' -Raw -Encoding UTF8
if ($resume -notmatch 'scripts/session_state.py' -or $resume -match 'Pick the most recently modified') { throw 'resume skill contract mismatch' }
if ($save -notmatch 'HandoffPayload' -or $save -notmatch 'schema_version.*2') { throw 'save skill contract mismatch' }
```

Expected: policy tests pass and PowerShell exits 0.

- [ ] **Step 8: Run README sync and commit repository-owned changes**

Run: `python scripts/check.py --readme-sync`

Expected: README public status sync passes.

Commit only repository files; global Skill files remain user-level configuration outside this Git repository:

```powershell
git add AGENTS.md README.md docs/01-guides/WORKFLOW.md docs/01-guides/HANDOVER.md docs/01-guides/workflow/STARTUP.md docs/01-guides/workflow/CLOSING.md docs/01-guides/workflow/SESSION_RECOVERY.md tests/test_scripts/test_session_recovery_policy.py
git commit -m "docs: enforce Git-verified session recovery"
```

---

### Task 7: Prove v2 Round-Trip, Close TD-076, and Run Final Gates

**Files:**
- Modify: `docs/superpowers/specs/2026-08-11-session-recovery-reliability-design.md`
- Modify: `docs/learning/52-session-snapshot-is-not-source-of-truth.md`
- Modify: `docs/06-departments/00-cross-cutting/DEBT.md`
- Modify: `docs/01-guides/debt/ROUTER.md`
- Modify: `docs/04-changelog/logs/2026-08-11/2026-08-11.md`
- Modify as required by independent review: only files already in this plan.

**Interfaces:**
- Consumes: all prior tasks and the approved design acceptance criteria.
- Produces: a real v2 snapshot, independent code/spec review evidence, closed TD-076, synchronized learning/log records, and a clean full gate.

- [ ] **Step 1: Run the complete session-state test suite**

Run:

```powershell
python -m pytest tests/test_scripts/test_session_state_models.py tests/test_scripts/test_session_state_git.py tests/test_scripts/test_session_state_store.py tests/test_scripts/test_session_state.py tests/test_scripts/test_session_recovery_policy.py -q
```

Expected: every test passes with no warnings.

- [ ] **Step 2: Generate a preliminary real v2 snapshot**

Create a temporary payload outside the repository with these fields:

```json
{
  "current_state": ["TD-076 implementation complete and under final verification"],
  "failed_approaches": ["Global newest legacy snapshot without Git validation"],
  "open_questions": [],
  "exact_next_step": "Review the final verification evidence before resuming E0 implementation"
}
```

Run:

```powershell
python scripts/session_state.py save --repo . --session-root "$env:USERPROFILE\.Codex\session-data" --topic "session recovery reliability" --payload <absolute-temporary-payload-path>
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
```

Expected: save exits 0; inspect exits 0 with `MATCH`, current worktree, current branch, full HEAD, and the approved next step. This preliminary snapshot is expected to become stale after closeout documents are committed. Delete only the temporary payload after verification.

- [ ] **Step 3: Prove repository advancement invalidates the snapshot without changing the real branch**

Use a temporary clone of the current repository. Generate a v2 snapshot for that clone with its own temporary session root, create one new commit in the clone, and run inspect there.

Expected: exit 2, `REPO_AHEAD`, and no `NEXT STEP` line. Do not create the proof commit in the real worktree.

- [ ] **Step 4: Request independent code and spec reviews**

Use `superpowers:requesting-code-review` plus the mandatory Python reviewer. Review scope:

```text
scripts/session_state.py
scripts/session_state_models.py
scripts/session_state_git.py
scripts/session_state_store.py
tests/test_scripts/test_session_state*.py
tests/test_scripts/session_state_helpers.py
global resume/save Skill diffs
docs/superpowers/specs/2026-08-11-session-recovery-reliability-design.md
```

Require explicit checks for command injection, path traversal, secret leakage, malformed Git output, Windows worktree identity, legacy next-step quarantine, atomic-write behavior, and spec coverage. Fix every confirmed Critical/High finding with a new RED → GREEN regression before proceeding.

- [ ] **Step 5: Synchronize closeout documentation**

Update the design status to implemented with commit/test evidence. Replace learning card 52’s planned pseudo-code/file wording with actual public functions and a verified incident example. Mark TD-076 closed, move it to the closed-debt table, and decrement ROUTER totals/severity counts back from 35/20 moderate to the correct post-close values. Append exact focused/full test counts and global Skill verification evidence to the 2026-08-11 work log.

- [ ] **Step 6: Run the smart gate**

Run: `python scripts/check.py`

Expected: Ruff, Pyright, README sync, selected Python tests, and any triggered frontend check pass.

- [ ] **Step 7: Run the full gate and whitespace audit**

Run:

```powershell
python scripts/check.py --full
git diff --check
```

Expected: full non-slow project suite, Ruff, Pyright, README sync, frontend type-check, and whitespace audit all pass. Record exact collected/passed/skipped/deselected counts rather than copying counts from 2026-08-10.

- [ ] **Step 8: Commit the verified closeout**

```powershell
git add docs/superpowers/specs/2026-08-11-session-recovery-reliability-design.md docs/learning/52-session-snapshot-is-not-source-of-truth.md docs/06-departments/00-cross-cutting/DEBT.md docs/01-guides/debt/ROUTER.md docs/04-changelog/logs/2026-08-11/2026-08-11.md
git commit -m "docs: close reliable session recovery"
```

- [ ] **Step 9: Generate and verify the final current v2 snapshot**

After the closeout commit, create a new temporary payload whose exact next step is `Resume from Git-verified session state, then continue the user-approved E0 implementation plan`. Run `save`, then run `inspect` without `--allow-old`.

Expected: both commands exit 0 and inspect reports `MATCH` against the final clean HEAD. Delete only the temporary payload; retain both preliminary and final snapshots as immutable history.

- [ ] **Step 10: Verify final repository state**

Run:

```powershell
git status --short --branch
git log --oneline -8
```

Expected: clean worktree, branch only ahead of its existing upstream, no push performed, and the session-recovery commits visible in order.

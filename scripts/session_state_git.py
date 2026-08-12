"""Fail-closed Git and local-evidence inspection for session snapshots."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Callable, TypeVar

from scripts.session_state_models import EvidenceRef, RepositoryState, normalize_identity_path

_ORDINARY_STATUS_PAIRS = frozenset(
    f"{index_status}{worktree_status}"
    for index_status in " MADRCT"
    for worktree_status in " MTD"
    if (index_status, worktree_status) != (" ", " ")
)
_UNMERGED_STATUS_PAIRS = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})
_VALID_STATUS_PAIRS = _ORDINARY_STATUS_PAIRS | _UNMERGED_STATUS_PAIRS | {"??", "!!"}
_GIT_HEAD_PATTERN = re.compile(r"[0-9a-f]{40}")
_GIT_REF_FORBIDDEN = frozenset(" ~^:?*[\\")
_T = TypeVar("_T")


class GitInspectionError(RuntimeError):
    """Raised when repository identity or Git evidence cannot be verified."""


class GitOperationalError(GitInspectionError):
    """Raised when Git or repository evidence cannot be read operationally."""


class SnapshotGitHeadMissingError(GitInspectionError):
    """Raised when a snapshot references a commit object absent from the repository."""


class _GitOutput(str):
    """Git output carrying its checked exit code for commands with multiple OK codes."""

    returncode: int

    def __new__(cls, value: str, returncode: int) -> _GitOutput:
        instance = super().__new__(cls, value)
        instance.returncode = returncode
        return instance


def _git_io(action: Callable[[], _T], diagnostic: str) -> _T:
    """Translate process/filesystem I/O after its private exception context ends."""
    try:
        result = action()
    except (OSError, UnicodeError):
        failure = GitOperationalError(diagnostic)
    else:
        return result
    raise failure


def _require_single_line_identity(output: str, operation: str) -> str:
    """Reject empty or multiline identity output without retaining its value."""
    if not output or any(character in output for character in "\0\r\n"):
        raise GitOperationalError(f"Git {operation} failed")
    return output


def _require_branch_identity(output: str) -> str:
    """Accept only an attached, syntactically valid short branch identity."""
    branch = _require_single_line_identity(output, "attached branch identity")
    components = branch.split("/")
    if (
        branch == "HEAD"
        or branch.startswith("-")
        or branch.startswith("/")
        or branch.endswith(("/", "."))
        or ".." in branch
        or "@{" in branch
        or any(character in _GIT_REF_FORBIDDEN or ord(character) < 32 for character in branch)
        or any(
            not component or component.startswith(".") or component.endswith(".lock")
            for component in components
        )
    ):
        raise GitOperationalError("Git attached branch identity failed")
    return branch


def _require_head_identity(output: str) -> str:
    """Accept only the SHA-1 commit identity supported by the snapshot contract."""
    head = _require_single_line_identity(output, "HEAD identity")
    if _GIT_HEAD_PATTERN.fullmatch(head) is None:
        raise GitOperationalError("Git HEAD identity failed")
    return head


def _git(
    repo: Path,
    operation: str,
    *args: str,
    ok: tuple[int, ...] = (0,),
    strip: bool = True,
) -> _GitOutput:
    """Run Git with bounded diagnostic output and explicit acceptable exit codes."""
    completed = _git_io(
        lambda: subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        ),
        f"Git {operation} failed",
    )
    if completed.returncode not in ok:
        raise GitOperationalError(f"Git {operation} failed")
    output = completed.stdout.strip() if strip else completed.stdout
    return _GitOutput(output, completed.returncode)


def parse_porcelain_z(output: str) -> tuple[str, ...]:
    """Parse NUL-delimited porcelain v1 output into sorted affected paths."""
    if not output:
        return ()
    if not output.endswith("\0"):
        raise GitInspectionError("malformed porcelain status: missing NUL terminator")

    records = output.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(records) - 1:
        record = records[index]
        if len(record) < 4 or record[2] != " ":
            raise GitInspectionError("malformed porcelain status record")
        status, first_path = record[:2], record[3:]
        if not first_path or status not in _VALID_STATUS_PAIRS:
            raise GitInspectionError("malformed porcelain status record")
        paths.add(first_path.replace("\\", "/"))
        index += 1
        if "R" in status or "C" in status:
            if index >= len(records) - 1 or not records[index]:
                raise GitInspectionError("truncated porcelain rename/copy record")
            paths.add(records[index].replace("\\", "/"))
            index += 1
    return tuple(sorted(paths))


def hash_evidence(repo: Path, path: Path) -> EvidenceRef:
    """Hash a repository-contained evidence file using a stable relative identity."""
    try:
        resolved_repo, resolved_path = _git_io(
            lambda: (repo.resolve(strict=True), path.resolve(strict=True)),
            "Git evidence access failed",
        )
        relative = resolved_path.relative_to(resolved_repo)
        if not _git_io(resolved_path.is_file, "Git evidence access failed"):
            raise GitInspectionError("evidence path is not a file")
        digest = hashlib.sha256(
            _git_io(resolved_path.read_bytes, "Git evidence access failed")
        ).hexdigest()
    except GitInspectionError:
        raise
    except ValueError:
        failure = GitInspectionError("evidence path escapes repository")
    else:
        return EvidenceRef(path=relative.as_posix(), sha256=digest)
    raise failure


def find_latest_work_log(repo: Path) -> Path | None:
    """Return the lexically latest dated project work log, if present."""
    return _git_io(
        lambda: max(
            repo.glob("docs/04-changelog/logs/????-??-??/????-??-??*.md"),
            key=lambda path: path.relative_to(repo).as_posix(),
            default=None,
        ),
        "Git work-log discovery failed",
    )


def find_latest_sdd_progress(repo: Path) -> Path | None:
    """Return the newest local SDD progress file, with a deterministic tie-breaker."""
    return _git_io(
        lambda: max(
            repo.glob(".superpowers/sdd/*/progress.md"),
            key=lambda path: (path.stat().st_mtime_ns, path.relative_to(repo).as_posix()),
            default=None,
        ),
        "Git SDD discovery failed",
    )


def verify_commit_exists(repo: Path, commit: str) -> None:
    """Verify one commit object exists without parsing localized Git output."""
    snapshot_object = _git(
        repo,
        "snapshot HEAD object verification",
        "rev-parse",
        "--verify",
        "--quiet",
        f"{commit}^{{commit}}",
        ok=(0, 1),
    )
    if snapshot_object.returncode == 1:
        raise SnapshotGitHeadMissingError("snapshot HEAD object is missing")
    if snapshot_object.returncode != 0:
        raise GitOperationalError("Git snapshot HEAD object verification failed")


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    """Return whether ``older`` is an ancestor of ``newer``, failing closed on Git errors."""
    verify_commit_exists(repo, older)
    result = _git(repo, "ancestry", "merge-base", "--is-ancestor", older, newer, ok=(0, 1))
    exit_code = result.returncode
    if exit_code == 0:
        return True
    if exit_code == 1:
        return False
    raise GitOperationalError(f"Git ancestry failed: exit code {exit_code}")


def collect_repository_state(repo: Path) -> RepositoryState:
    """Collect Git identity, dirty paths, and local evidence for a worktree."""
    worktree_output = _require_single_line_identity(
        str(_git(repo, "repository identity", "rev-parse", "--show-toplevel")),
        "repository identity",
    )
    if not Path(worktree_output).is_absolute():
        raise GitOperationalError("Git repository identity failed")
    worktree = _git_io(
        lambda: Path(worktree_output).resolve(strict=True),
        "Git repository path access failed",
    )
    common_dir_output = _git(
        worktree, "repository common directory", "rev-parse", "--git-common-dir"
    )
    common_dir_value = _require_single_line_identity(
        str(common_dir_output), "repository common directory"
    )
    common_dir = Path(common_dir_value)
    if not common_dir.is_absolute():
        common_dir = worktree / common_dir
    common_dir = _git_io(
        lambda: common_dir.resolve(strict=True),
        "Git common directory access failed",
    )
    project_root = common_dir.parent if common_dir.name == ".git" else worktree

    branch = _require_branch_identity(
        str(
            _git(
                worktree,
                "attached branch identity",
                "symbolic-ref",
                "--quiet",
                "--short",
                "HEAD",
            )
        )
    )
    git_head = _require_head_identity(
        str(_git(worktree, "HEAD identity", "rev-parse", "--verify", "HEAD"))
    )
    status = _git(
        worktree,
        "working tree status",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        strip=False,
    )
    dirty_paths = parse_porcelain_z(str(status))

    handover_path = worktree / "docs/01-guides/HANDOVER.md"
    work_log = find_latest_work_log(worktree)
    sdd_progress = find_latest_sdd_progress(worktree)
    handover = _git_io(
        lambda: hash_evidence(worktree, handover_path) if handover_path.is_file() else None,
        "Git handover evidence access failed",
    )
    normalized_project_root, normalized_worktree = _git_io(
        lambda: (
            normalize_identity_path(project_root),
            normalize_identity_path(worktree),
        ),
        "Git repository identity access failed",
    )
    return RepositoryState(
        project_root=normalized_project_root,
        worktree_path=normalized_worktree,
        branch=branch,
        git_head=git_head,
        git_dirty=bool(dirty_paths),
        dirty_paths=dirty_paths,
        handover=handover,
        latest_work_log=hash_evidence(worktree, work_log) if work_log is not None else None,
        sdd_progress=hash_evidence(worktree, sdd_progress) if sdd_progress is not None else None,
    )

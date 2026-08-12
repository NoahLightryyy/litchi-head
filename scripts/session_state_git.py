"""Fail-closed Git and local-evidence inspection for session snapshots."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from scripts.session_state_models import EvidenceRef, RepositoryState, normalize_identity_path


class GitInspectionError(RuntimeError):
    """Raised when repository identity or Git evidence cannot be verified."""


class _GitOutput(str):
    """Git output carrying its checked exit code for commands with multiple OK codes."""

    returncode: int

    def __new__(cls, value: str, returncode: int) -> _GitOutput:
        instance = super().__new__(cls, value)
        instance.returncode = returncode
        return instance


def _summary(value: str) -> str:
    """Return a stable, single-line subprocess diagnostic summary."""
    normalized = " ".join(value.split())
    return normalized[:200] or "<empty>"


def _git(
    repo: Path,
    operation: str,
    *args: str,
    ok: tuple[int, ...] = (0,),
    strip: bool = True,
) -> _GitOutput:
    """Run Git with bounded diagnostic output and explicit acceptable exit codes."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in ok:
        raise GitInspectionError(
            f"Git {operation} failed: exit code {completed.returncode}; "
            f"stderr={_summary(completed.stderr)}; stdout={_summary(completed.stdout)}"
        )
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
        if not first_path or any(character not in " MADRCU?!" for character in status):
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
    resolved_repo = repo.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    try:
        relative = resolved_path.relative_to(resolved_repo)
    except ValueError as error:
        raise GitInspectionError("evidence path escapes repository") from error
    if not resolved_path.is_file():
        raise GitInspectionError("evidence path is not a file")
    digest = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    return EvidenceRef(path=relative.as_posix(), sha256=digest)


def find_latest_work_log(repo: Path) -> Path | None:
    """Return the lexically latest dated project work log, if present."""
    logs = repo.glob("docs/04-changelog/logs/????-??-??/????-??-??*.md")
    return max(logs, key=lambda path: path.relative_to(repo).as_posix(), default=None)


def find_latest_sdd_progress(repo: Path) -> Path | None:
    """Return the newest local SDD progress file, with a deterministic tie-breaker."""
    progress_files = repo.glob(".superpowers/sdd/*/progress.md")
    return max(
        progress_files,
        key=lambda path: (path.stat().st_mtime_ns, path.relative_to(repo).as_posix()),
        default=None,
    )


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    """Return whether ``older`` is an ancestor of ``newer``, failing closed on Git errors."""
    result = _git(repo, "ancestry", "merge-base", "--is-ancestor", older, newer, ok=(0, 1))
    exit_code = result.returncode
    if exit_code == 0:
        return True
    if exit_code == 1:
        return False
    raise GitInspectionError(f"Git ancestry failed: exit code {exit_code}")


def collect_repository_state(repo: Path) -> RepositoryState:
    """Collect Git identity, dirty paths, and local evidence for a worktree."""
    worktree = Path(
        _git(repo, "repository identity", "rev-parse", "--show-toplevel")
    ).resolve(strict=True)
    common_dir_output = _git(
        worktree, "repository common directory", "rev-parse", "--git-common-dir"
    )
    common_dir = Path(str(common_dir_output))
    if not common_dir.is_absolute():
        common_dir = worktree / common_dir
    common_dir = common_dir.resolve(strict=True)
    project_root = common_dir.parent if common_dir.name == ".git" else worktree

    branch = str(
        _git(worktree, "attached branch identity", "symbolic-ref", "--quiet", "--short", "HEAD")
    )
    if not branch:
        raise GitInspectionError("Git attached branch identity failed: detached HEAD")
    git_head = str(_git(worktree, "HEAD identity", "rev-parse", "--verify", "HEAD"))
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
    return RepositoryState(
        project_root=normalize_identity_path(project_root),
        worktree_path=normalize_identity_path(worktree),
        branch=branch,
        git_head=git_head,
        git_dirty=bool(dirty_paths),
        dirty_paths=dirty_paths,
        handover=hash_evidence(worktree, handover_path) if handover_path.is_file() else None,
        latest_work_log=hash_evidence(worktree, work_log) if work_log is not None else None,
        sdd_progress=hash_evidence(worktree, sdd_progress) if sdd_progress is not None else None,
    )

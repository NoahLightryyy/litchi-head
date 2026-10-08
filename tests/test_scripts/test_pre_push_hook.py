"""Integration tests for the repository pre-push hook boundary."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "scripts" / "pre-push"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        check=True,
        cwd=repo,
        text=True,
    )
    return result.stdout.strip()


def _bash_executable() -> str:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is unavailable")
    if os.name == "nt":
        git_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is unavailable")
    return bash


def _write_tool(bin_dir: Path, name: str) -> None:
    tool = bin_dir / name
    tool.write_text(
        "#!/bin/sh\n"
        "printf '%s|%s|%s|%s\\n' \"$PWD\" \"${GIT_DIR-unset}\" "
        '"${GIT_WORK_TREE-unset}" "${GIT_INDEX_FILE-unset}" '
        '>> "$HOOK_CAPTURE"\n',
        encoding="utf-8",
    )
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)


def test_pre_push_clears_git_environment_before_quality_tools(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "hook-test@example.com")
    _git(repo, "config", "user.name", "Hook Test")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "fixture")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("ruff", "pyright", "pytest"):
        _write_tool(bin_dir, command)
    capture = tmp_path / "hook-environment.txt"
    env = os.environ.copy()
    env.update(
        {
            "GIT_DIR": str(repo / ".git"),
            "GIT_WORK_TREE": str(repo),
            "GIT_INDEX_FILE": str(repo / ".git" / "index"),
            "HOOK_CAPTURE": str(capture),
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        }
    )

    result = subprocess.run(
        [_bash_executable(), str(HOOK_PATH)],
        capture_output=True,
        cwd=repo,
        encoding="utf-8",
        errors="replace",
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    invocations = capture.read_text(encoding="utf-8").splitlines()
    assert len(invocations) >= 3
    for invocation in invocations:
        tool_cwd, git_dir, git_work_tree, git_index = invocation.split("|")
        assert tool_cwd.endswith(f"/{tmp_path.name}/repo")
        assert (git_dir, git_work_tree, git_index) == ("unset", "unset", "unset")


@pytest.mark.parametrize("dirty_kind", ["tracked", "staged", "untracked"])
def test_pre_push_rejects_dirty_worktree_without_running_quality_tools(
    tmp_path: Path,
    dirty_kind: str,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "hook-test@example.com")
    _git(repo, "config", "user.name", "Hook Test")
    readme = repo / "README.md"
    readme.write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "fixture")
    if dirty_kind == "untracked":
        (repo / "untracked.txt").write_text("keep me\n", encoding="utf-8")
    else:
        readme.write_text(f"{dirty_kind} change\n", encoding="utf-8")
        if dirty_kind == "staged":
            _git(repo, "add", "README.md")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("ruff", "pyright", "pytest"):
        _write_tool(bin_dir, command)
    capture = tmp_path / "hook-environment.txt"
    env = os.environ.copy()
    env.update(
        {
            "GIT_DIR": str(repo / ".git"),
            "GIT_WORK_TREE": str(repo),
            "GIT_INDEX_FILE": str(repo / ".git" / "index"),
            "HOOK_CAPTURE": str(capture),
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        }
    )
    status_before = _git(repo, "status", "--short")

    result = subprocess.run(
        [_bash_executable(), str(HOOK_PATH)],
        capture_output=True,
        cwd=repo,
        encoding="utf-8",
        errors="replace",
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert not capture.exists()
    assert _git(repo, "status", "--short") == status_before

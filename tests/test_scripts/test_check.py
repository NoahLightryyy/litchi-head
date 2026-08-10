"""本地 CI 检查脚本的回归测试。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import check


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        check=True,
        cwd=repo,
        text=True,
    )
    return result.stdout.strip()


def _write(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _write(repo, "README.md", "base README\n")
    _write(repo, "docs/00-overview/ROADMAP.md", "base roadmap\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def test_git_diff_includes_untracked_files(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs: Iterator[subprocess.CompletedProcess[str]] = iter(
        [
            _completed("backend/main.py\n"),
            _completed("README.md\n"),
            _completed("frontend/components/new.tsx\nstart.bat\n"),
        ]
    )
    run = Mock(side_effect=lambda *args, **kwargs: next(outputs))
    monkeypatch.setattr(check.subprocess, "run", run)

    changed = check.git_diff()

    assert changed == {
        "README.md",
        "backend/main.py",
        "frontend/components/new.tsx",
        "start.bat",
    }
    assert run.call_args_list[2].args[0] == [
        "git",
        "ls-files",
        "--others",
        "--exclude-standard",
    ]


def test_public_status_change_requires_root_readme_sync() -> None:
    assert check.missing_readme_sync_batches(
        [{"docs/00-overview/ROADMAP.md", "src/data/models.py"}]
    ) == ("docs/00-overview/ROADMAP.md",)


def test_root_readme_satisfies_public_status_sync() -> None:
    assert check.missing_readme_sync_batches(
        [{"README.md", "docs/01-guides/HANDOVER.md"}]
    ) == ()


def test_unrelated_docs_do_not_require_root_readme_sync() -> None:
    assert check.missing_readme_sync_batches(
        [{"docs/learning/21-engineering-discipline.md"}]
    ) == ()


def test_ordered_batches_require_readme_after_later_canonical_change() -> None:
    assert check.missing_readme_sync_batches(
        [
            {"README.md"},
            {"docs/00-overview/ROADMAP.md"},
        ]
    ) == ("docs/00-overview/ROADMAP.md",)


def test_ordered_batches_allow_same_or_later_readme_sync() -> None:
    assert check.missing_readme_sync_batches(
        [
            {"docs/00-overview/ROADMAP.md", "README.md"},
            {"docs/01-guides/HANDOVER.md"},
            {"README.md"},
        ]
    ) == ()


def test_git_commit_batches_parses_commits_in_old_to_new_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs: Iterator[subprocess.CompletedProcess[str]] = iter(
        [
            _completed("older\nnewer\n"),
            _completed("parent-older\n"),
            _completed("README.md\n"),
            _completed("parent-newer\n"),
            _completed("docs/00-overview/ROADMAP.md\n"),
        ]
    )
    run = Mock(side_effect=lambda *args, **kwargs: next(outputs))
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check.git_commit_batches("base") == [
        {"README.md"},
        {"docs/00-overview/ROADMAP.md"},
    ]
    assert run.call_args_list[0].args[0] == [
        "git",
        "rev-list",
        "--reverse",
        "base..HEAD",
    ]
    assert run.call_args_list[1].args[0] == [
        "git",
        "show",
        "--format=%P",
        "--no-patch",
        "older",
    ]
    assert run.call_args_list[2].args[0] == [
        "git",
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "older",
    ]


def test_git_commit_batches_returns_empty_when_comparison_ref_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(return_value=_completed(returncode=128))
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check.git_commit_batches("@{upstream}") == []
    assert run.call_args.args[0] == [
        "git",
        "rev-list",
        "--reverse",
        "@{upstream}..HEAD",
    ]


def test_git_commit_batches_fails_closed_when_a_commit_cannot_be_inspected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs: Iterator[subprocess.CompletedProcess[str]] = iter(
        [_completed("commit\n"), _completed(returncode=1)]
    )
    monkeypatch.setattr(
        check.subprocess,
        "run",
        Mock(side_effect=lambda *args, **kwargs: next(outputs)),
    )

    assert check.git_commit_batches("base") is None


def test_git_commit_batches_detects_conflict_resolution_in_real_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_git_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-b", "incoming")
    _write(repo, "docs/00-overview/ROADMAP.md", "incoming roadmap\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "incoming roadmap")

    _git(repo, "checkout", "main")
    _write(repo, "README.md", "early README sync\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "early README sync")
    _write(repo, "docs/00-overview/ROADMAP.md", "main roadmap\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main roadmap")

    merge = subprocess.run(
        ["git", "merge", "incoming"], capture_output=True, cwd=repo, text=True
    )
    assert merge.returncode != 0
    _write(repo, "docs/00-overview/ROADMAP.md", "resolved roadmap\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "resolve roadmap conflict")

    monkeypatch.setattr(check, "REPO_ROOT", repo)
    batches = check.git_commit_batches(base)

    assert batches is not None
    assert batches[-1] == {"docs/00-overview/ROADMAP.md"}
    assert check.missing_readme_sync_batches(
        [{"README.md"}, batches[-1]]
    ) == ("docs/00-overview/ROADMAP.md",)


def test_git_commit_batches_ignores_incoming_only_path_in_real_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _init_git_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-b", "incoming")
    _write(repo, "docs/00-overview/ROADMAP.md", "incoming roadmap\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "incoming roadmap")

    _git(repo, "checkout", "main")
    _write(repo, "README.md", "early README sync\n")
    _write(repo, "main-only.txt", "main only\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "early README sync and main change")
    _git(repo, "merge", "--no-ff", "incoming", "-m", "merge incoming")

    monkeypatch.setattr(check, "REPO_ROOT", repo)
    batches = check.git_commit_batches(base)

    assert batches is not None
    assert batches[-1] == set()


@pytest.mark.parametrize(
    "changed_file",
    [
        "pyproject.toml",
        ".github/workflows/ci.yml",
        "pyrightconfig.json",
    ],
)
def test_quality_config_change_triggers_full_python_tests(changed_file: str) -> None:
    assert check.pick_test_targets({changed_file}) is None


def test_check_script_change_runs_script_tests() -> None:
    assert check.pick_test_targets({"scripts/check.py"}) == ["tests/test_scripts"]


def test_root_level_test_change_triggers_full_python_tests() -> None:
    assert check.pick_test_targets({"tests/test_risk_r1_three_layer.py"}) is None


def test_no_changes_skip_python_tests() -> None:
    assert check.pick_test_targets(set()) == []


@pytest.mark.parametrize(
    ("changed_files", "expected"),
    [
        ({"frontend/app/page.tsx"}, True),
        ({"frontend/package.json"}, True),
        ({"docs/README.md"}, False),
    ],
)
def test_frontend_change_detection(changed_files: set[str], expected: bool) -> None:
    assert check.needs_frontend_check(changed_files) is expected


@pytest.mark.parametrize(
    ("os_name", "executable"),
    [
        ("nt", "pnpm.cmd"),
        ("posix", "pnpm"),
    ],
)
def test_frontend_typecheck_command_is_platform_compatible(
    os_name: str,
    executable: str,
) -> None:
    assert check.frontend_typecheck_command(os_name)[0] == executable


def test_main_checks_backend_types_and_changed_frontend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(name: str, cmd: list[str]) -> bool:
        calls.append((name, cmd))
        return True

    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": {"frontend/app/page.tsx"})
    monkeypatch.setattr(check, "git_commit_batches", lambda target: [])
    monkeypatch.setattr(check, "run_step", fake_run_step)
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 0
    assert ("pyright", ["pyright", "src/", "backend/"]) in calls
    assert (
        "frontend type-check",
        check.frontend_typecheck_command(),
    ) in calls


def test_full_mode_runs_python_and_frontend_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(name: str, cmd: list[str]) -> bool:
        calls.append((name, cmd))
        return True

    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": set())
    monkeypatch.setattr(check, "git_commit_batches", lambda target: [])
    monkeypatch.setattr(check, "run_step", fake_run_step)
    monkeypatch.setattr(sys, "argv", ["check.py", "--full"])

    assert check.main() == 0
    assert (
        "tests (not slow)",
        [sys.executable, "-m", "pytest", "-x", "--tb=short", "-m", "not slow"],
    ) in calls
    assert (
        "frontend type-check",
        check.frontend_typecheck_command(),
    ) in calls


def test_full_mode_fails_when_public_status_lacks_root_readme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(
        check,
        "git_diff",
        lambda target="HEAD": {"docs/00-overview/ROADMAP.md"},
    )
    monkeypatch.setattr(check, "git_commit_batches", lambda target: [])
    monkeypatch.setattr(check, "run_step", lambda name, cmd: True)
    monkeypatch.setattr(sys, "argv", ["check.py", "--full"])

    assert check.main() == 1


def test_explicit_diff_uses_its_ref_for_committed_sync_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diff = Mock(return_value={"src/data/models.py"})
    batches = Mock(return_value=[])

    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", diff)
    monkeypatch.setattr(check, "git_commit_batches", batches)
    monkeypatch.setattr(check, "run_step", lambda name, cmd: True)
    monkeypatch.setattr(sys, "argv", ["check.py", "--diff", "some-ref"])

    assert check.main() == 0
    assert diff.call_args_list[0].args == ("some-ref",)
    assert diff.call_args_list[1].args == ()
    batches.assert_called_once_with("some-ref")


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (1, False)])
def test_run_step_returns_command_status(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    expected: bool,
) -> None:
    monkeypatch.setattr(
        check.subprocess,
        "run",
        Mock(return_value=_completed(returncode=returncode)),
    )

    assert check.run_step("example", ["tool", "arg"]) is expected


def test_main_returns_failure_when_a_gate_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": set())
    monkeypatch.setattr(check, "git_commit_batches", lambda target: [])
    monkeypatch.setattr(check, "run_step", lambda name, cmd: name != "ruff")
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 1


def test_main_fails_when_committed_public_status_lacks_root_readme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": {"src/data/models.py"})
    monkeypatch.setattr(
        check,
        "git_commit_batches",
        lambda target: [{"docs/00-overview/ROADMAP.md"}],
    )
    monkeypatch.setattr(check, "run_step", lambda name, cmd: True)
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 1


def test_readme_sync_mode_uses_explicit_diff_batches_and_skips_full_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches = Mock(
        return_value=[
            {"README.md"},
            {"docs/00-overview/ROADMAP.md"},
        ]
    )
    current = Mock(return_value=set())

    monkeypatch.setattr(check, "git_commit_batches", batches)
    monkeypatch.setattr(check, "git_diff", current)
    monkeypatch.setattr(
        check,
        "ensure_deps",
        lambda: pytest.fail("--readme-sync must not install dependencies"),
    )
    monkeypatch.setattr(
        check,
        "run_step",
        lambda name, cmd: pytest.fail("--readme-sync must not run full gates"),
    )
    monkeypatch.setattr(sys, "argv", ["check.py", "--readme-sync", "--diff", "base"])

    assert check.main() == 1
    batches.assert_called_once_with("base")
    current.assert_called_once_with()


def test_readme_sync_default_without_upstream_checks_only_current_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches = Mock(return_value=[])
    monkeypatch.setattr(check, "git_commit_batches", batches)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": {"README.md"})
    monkeypatch.setattr(
        check,
        "run_step",
        lambda name, cmd: pytest.fail("--readme-sync must not run full gates"),
    )
    monkeypatch.setattr(sys, "argv", ["check.py", "--readme-sync"])

    assert check.main() == 0
    batches.assert_called_once_with("@{upstream}")


def test_ci_runs_dedicated_readme_sync_gate_for_pull_requests() -> None:
    workflow = (check.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    command = (
        "python scripts/check.py --readme-sync --diff "
        "${{ github.event.pull_request.base.sha }}"
    )

    assert "fetch-depth: 0" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert command in workflow

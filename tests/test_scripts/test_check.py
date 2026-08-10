"""本地 CI 检查脚本的回归测试。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from unittest.mock import Mock

import pytest

from scripts import check


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


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
    assert check.missing_readme_sync(
        {"docs/00-overview/ROADMAP.md", "src/data/models.py"}
    ) == ("docs/00-overview/ROADMAP.md",)


def test_root_readme_satisfies_public_status_sync() -> None:
    assert check.missing_readme_sync(
        {"README.md", "docs/01-guides/HANDOVER.md"}
    ) == ()


def test_unrelated_docs_do_not_require_root_readme_sync() -> None:
    assert check.missing_readme_sync(
        {"docs/learning/21-engineering-discipline.md"}
    ) == ()


def test_git_upstream_diff_parses_successful_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(return_value=_completed("README.md\ndocs/00-overview/ROADMAP.md\n"))
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check.git_upstream_diff() == {
        "README.md",
        "docs/00-overview/ROADMAP.md",
    }
    assert run.call_args.args[0] == [
        "git",
        "diff",
        "--name-only",
        "@{upstream}...HEAD",
    ]


def test_git_upstream_diff_returns_empty_set_without_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(return_value=_completed(returncode=128))
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check.git_upstream_diff() == set()
    assert run.call_args.args[0] == [
        "git",
        "diff",
        "--name-only",
        "@{upstream}...HEAD",
    ]


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
    monkeypatch.setattr(check, "git_upstream_diff", lambda: set())
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
    monkeypatch.setattr(check, "git_upstream_diff", lambda: set())
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
    monkeypatch.setattr(check, "git_upstream_diff", lambda: set())
    monkeypatch.setattr(check, "run_step", lambda name, cmd: name != "ruff")
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 1


def test_main_fails_when_upstream_public_status_lacks_root_readme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": {"src/data/models.py"})
    monkeypatch.setattr(
        check,
        "git_upstream_diff",
        lambda: {"docs/00-overview/ROADMAP.md"},
    )
    monkeypatch.setattr(check, "run_step", lambda name, cmd: True)
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 1

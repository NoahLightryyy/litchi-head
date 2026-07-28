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


def test_main_checks_backend_types_and_changed_frontend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_run_step(name: str, cmd: list[str]) -> bool:
        calls.append((name, cmd))
        return True

    monkeypatch.setattr(check, "ensure_deps", lambda: None)
    monkeypatch.setattr(check, "git_diff", lambda target="HEAD": {"frontend/app/page.tsx"})
    monkeypatch.setattr(check, "run_step", fake_run_step)
    monkeypatch.setattr(sys, "argv", ["check.py"])

    assert check.main() == 0
    assert ("pyright", ["pyright", "src/", "backend/"]) in calls
    assert (
        "frontend type-check",
        ["pnpm", "--dir", str(Path("frontend")), "type-check"],
    ) in calls

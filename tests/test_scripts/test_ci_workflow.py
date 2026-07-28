"""前端可复现构建与 GitHub Actions 门禁契约。"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _workflow() -> dict:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def _run_commands(job: dict) -> str:
    return "\n".join(
        str(step["run"])
        for step in job["steps"]
        if isinstance(step, dict) and "run" in step
    )


def _used_actions(job: dict) -> set[str]:
    return {
        str(step["uses"])
        for step in job["steps"]
        if isinstance(step, dict) and "uses" in step
    }


def test_root_layout_does_not_import_remote_google_fonts() -> None:
    layout = (REPO_ROOT / "frontend" / "app" / "layout.tsx").read_text(encoding="utf-8")

    assert "next/font/google" not in layout


def test_python_ci_checks_src_and_backend_with_node24_actions() -> None:
    python_job = _workflow()["jobs"]["check"]
    commands = _run_commands(python_job)
    actions = _used_actions(python_job)

    assert "pyright src/ backend/" in commands
    assert 'python -m pytest -m "not slow" --cov=src' in commands
    assert "actions/checkout@v6" in actions
    assert "actions/setup-python@v6" in actions


def test_ci_has_reproducible_frontend_type_and_build_job() -> None:
    frontend_job = _workflow()["jobs"]["frontend"]
    commands = _run_commands(frontend_job)
    actions = _used_actions(frontend_job)

    assert "pnpm --dir frontend install --frozen-lockfile" in commands
    assert "pnpm --dir frontend type-check" in commands
    assert "pnpm --dir frontend build" in commands
    assert "actions/checkout@v6" in actions
    assert "actions/setup-node@v6" in actions
    assert "pnpm/action-setup@v6" in actions

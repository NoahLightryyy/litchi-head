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


def test_canonical_guide_documents_fail_closed_local_user_boundary() -> None:
    guide = read("docs/01-guides/workflow/SESSION_RECOVERY.md")

    assert "可信本机用户" in guide
    assert "预先存在" in guide
    assert "symlink" in guide
    assert "junction" in guide
    assert "同一 Windows 账号" in guide
    assert "不防御" in guide
    assert "原生目录句柄" in guide
    assert "不实现" in guide
    assert "快照是可丢弃的缓存" in guide


def test_workflow_links_the_canonical_recovery_guide() -> None:
    workflow = read("docs/01-guides/WORKFLOW.md")

    assert "SESSION_RECOVERY.md" in workflow

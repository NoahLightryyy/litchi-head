from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8")


def assert_order(text: str, *needles: str) -> None:
    positions = [text.index(needle) for needle in needles]
    assert positions == sorted(positions), dict(zip(needles, positions, strict=True))


def assert_project_resume_contract(text: str) -> None:
    inspect = "scripts/session_state.py inspect"
    assert inspect in text
    assert_order(text, inspect, "快照正文")
    assert_order(text, inspect, "HANDOVER.md")
    assert "只有非过期的 `MATCH`" in text
    for status in (
        "REPO_AHEAD",
        "HEAD_DIVERGED",
        "BRANCH_MISMATCH",
        "DIRTY_MISMATCH",
        "EVIDENCE_CHANGED",
        "PROJECT_MISMATCH",
        "LEGACY_UNVERIFIABLE",
        "MALFORMED",
    ):
        assert f"`{status}`" in text
    assert "都不得输出或执行快照中的下一步" in text
    assert_order(text, "Git status", ".superpowers/sdd/", "HANDOVER.md", "最新工作日志")
    assert "明确确认" in text
    assert "--allow-old" in text
    assert "只有第二次仍为 `MATCH`" in text
    assert "不得按全局 mtime" in text
    assert "legacy `.tmp` 只作为 `LEGACY_UNVERIFIABLE` 历史线索" in text
    forbidden = (
        "先读取 HANDOVER.md，再运行校验器",
        "非 MATCH 也可以执行下一步",
        "允许按全局 mtime 选择快照",
        "执行 legacy 快照中的下一步",
        "直接读取 HANDOVER.md 即可恢复",
    )
    for phrase in forbidden:
        assert phrase not in text


def assert_claude_resume_contract(text: str) -> None:
    rule = text.split("\n", 12)[10]
    assert "scripts/session_state.py inspect" in rule
    assert "只有 `MATCH`" in rule
    assert "--allow-old" in rule
    assert "不得绕过校验器" in rule
    assert "或手动读取" not in rule
    assert "直接读取 HANDOVER 即可恢复" not in rule


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


def test_operator_policy_uses_array_invocation_and_revalidates_old_match() -> None:
    resume = read("docs/01-guides/workflow/SESSION_RECOVERY.md")

    assert "$inspectArgs = @(" in resume
    assert "& python @inspectArgs" in resume
    assert "$allowOldArgs = $inspectArgs + @('--allow-old')" in resume
    assert "& python @allowOldArgs" in resume
    assert "第二次仍为 `MATCH`" in resume
    assert "不得直接读取快照正文" in resume


def test_operator_policy_scans_topic_and_payload_before_array_invocation() -> None:
    save = read("docs/01-guides/workflow/SESSION_RECOVERY.md")

    assert "四个 payload 字段和 `$topic`" in save
    assert "构造或打印参数数组前" in save
    assert "$cliArgs = @(" in save
    assert "& python @cliArgs" in save
    assert "不得插值或拼接命令字符串" in save


def test_operator_policy_constrains_literal_payload_cleanup_to_temp_root() -> None:
    save = read("docs/01-guides/workflow/SESSION_RECOVERY.md")

    assert "位于 `$repoPath` 和 `$sessionRoot` 之外" in save
    assert "$payloadPath" in save
    assert "Remove-Item -LiteralPath $payloadPath" in save
    assert "解析后的允许临时根目录" in save
    assert "不得使用 glob" in save


def test_project_resume_entrypoint_and_claude_require_validator() -> None:
    project_skill = read(".agents/skills/resume-session/skill.md")
    claude = read("CLAUDE.md")

    assert_project_resume_contract(project_skill)
    assert_claude_resume_contract(claude)


@pytest.mark.parametrize(
    "old,new",
    [
        ("不得先读快照正文", "先读取 HANDOVER.md，再运行校验器；不得先读快照正文"),
        ("都不得输出或执行快照中的下一步", "非 MATCH 也可以执行下一步"),
        ("不得按全局 mtime 选择快照", "允许按全局 mtime 选择快照"),
        (
            "legacy `.tmp` 只作为 `LEGACY_UNVERIFIABLE` 历史线索",
            "执行 legacy 快照中的下一步",
        ),
    ],
)
def test_project_resume_contract_rejects_unsafe_rule_mutations(old: str, new: str) -> None:
    original = read(".agents/skills/resume-session/skill.md")
    assert old in original

    with pytest.raises(AssertionError):
        assert_project_resume_contract(original.replace(old, new, 1))


def test_claude_contract_rejects_direct_handover_bypass_mutation() -> None:
    original = read("CLAUDE.md")
    mutation = original.replace(
        "不得绕过校验器直接把 HANDOVER 或最新日志当作当前状态",
        "直接读取 HANDOVER 即可恢复",
        1,
    )

    with pytest.raises(AssertionError):
        assert_claude_resume_contract(mutation)


def test_project_guides_require_full_allow_old_rerun() -> None:
    startup = read("docs/01-guides/workflow/STARTUP.md")
    guide = read("docs/01-guides/workflow/SESSION_RECOVERY.md")

    command = (
        "python scripts/session_state.py inspect --repo . --session-root "
        '"$env:USERPROFILE\\.Codex\\session-data" --allow-old'
    )
    assert command in startup
    assert command in guide


def test_current_resume_references_do_not_bypass_or_point_to_retired_entry() -> None:
    handover = read("docs/01-guides/HANDOVER.md")
    routing = read("docs/01-guides/ROUTING.md")
    learning = read("docs/learning/19-windows-git-bash-compat.md")
    learning_index = read("docs/learning/README.md")

    assert "先执行 `scripts/session_state.py inspect`" in handover
    assert "校验器前置" in routing
    assert ".claude/skills/resume-session" not in learning
    assert ".claude/skills/resume-session" not in learning_index


def test_learning_card_does_not_claim_removed_resume_ci_code_is_current() -> None:
    learning = read("docs/learning/19-windows-git-bash-compat.md")

    assert "## 项目里的真实代码" not in learning
    assert "之前的 resume-session CI 检查" not in learning
    assert "之后的 resume-session CI 检查" not in learning
    assert "对比之前（注释掉的旧版本）" not in learning


def test_current_log_records_task6_commits_and_task7_is_unfinished() -> None:
    log = read("docs/04-changelog/logs/2026-08-12/2026-08-12.md")

    assert "Task 6" in log
    assert "75eb660" in log
    assert "e18872c" in log
    assert "Task 7" in log
    assert "未完成" in log

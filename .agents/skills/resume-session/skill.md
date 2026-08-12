# resume-session — Git 校验的会话恢复

> 本项目入口明确委托 `scripts/session_state.py inspect` 做 v2 快照身份校验。Git/worktree 是事实源，快照只是缓存；恢复默认只读。

## 执行步骤

### 1. 先解析当前 worktree，再运行校验器

从当前目录或用户明确指定的 worktree 解析项目根目录、分支、完整 HEAD、dirty paths 和 worktree 列表。确认 `scripts/session_state.py` 属于该 worktree 后，用独立参数调用：

```powershell
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
```

不得先读快照正文，也不得按全局 mtime 选择快照。

### 2. 按 status 失败关闭

- 只有非过期的 `MATCH` 可以采用校验器输出的 handoff 和 `exact_next_step`。
- 首次得到旧 `MATCH` 时，不显示 handoff 或下一步；先向用户说明过期警告并等待明确确认。
- 用户确认后，必须用同一个 repo、session root 和 worktree 完整重跑：

```powershell
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data" --allow-old
```

只有第二次仍为 `MATCH` 才能采用校验器这一次输出的 handoff；不得绕过 CLI 直接读取 snapshot body。

`REPO_AHEAD`、`HEAD_DIVERGED`、`BRANCH_MISMATCH`、`DIRTY_MISMATCH`、`EVIDENCE_CHANGED`、`PROJECT_MISMATCH`、`LEGACY_UNVERIFIABLE`、`MALFORMED` 或任何校验异常，都不得输出或执行快照中的下一步。

### 3. 非 MATCH 时从仓库重建

按以下权威顺序只读恢复：

1. 当前 worktree 的 Git status、branch、完整 HEAD、worktree list 和 recent log；
2. 当前分支 `.superpowers/sdd/` 的活跃任务、计划和规格；
3. `AGENTS.md` / `CLAUDE.md` 启动规则；
4. 项目及部门 `HANDOVER.md`；
5. 按日期与 Git 历史确定的最新工作日志；
6. 必要时查 ROADMAP 与债务；
7. legacy `.tmp` 只作为 `LEGACY_UNVERIFIABLE` 历史线索。

不得 checkout、reset、clean、merge、push、修复快照目录或删除快照。校验器缺失时手工核对项目、worktree、分支和完整 HEAD；事实不全即失败关闭。

### 4. 输出并停止

输出 WORKTREE、BRANCH、完整 HEAD、SNAPSHOT、STATUS、CONFLICTS、AUTHORITY，以及已完成/进行中/未开始、失败方案、阻塞和证据支持的下一步。非 `MATCH` 标记为 `REPOSITORY STATE RECONSTRUCTED`，不得写 `SESSION LOADED`。

输出恢复摘要后停止，等待用户给方向；不得自动修改仓库。

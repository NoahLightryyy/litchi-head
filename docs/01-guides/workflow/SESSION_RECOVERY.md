# 会话恢复与保存

> 会话快照用于减少恢复时间，不替代仓库证据。恢复过程默认只读并失败关闭。

## 权威顺序

Git/worktree 是事实源；当前分支的 SDD、HANDOVER 和最新工作日志是状态说明；通过一致性校验的 v2 快照是可丢弃的缓存；旧 `.tmp` 和原始任务 JSONL 仅供追溯。

## 启动

从当前项目或明确指定的 worktree 运行：

```powershell
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
```

只有 `MATCH` 可生成恢复简报并显示 `exact_next_step`；快照超过 7 天时，即使是 `MATCH` 也必须先得到用户明确确认。`REPO_AHEAD`、`HEAD_DIVERGED`、`BRANCH_MISMATCH`、`DIRTY_MISMATCH`、`EVIDENCE_CHANGED`、`LEGACY_UNVERIFIABLE` 或 `MALFORMED` 都不得执行快照中的下一步，也不得输出其中的下一步；必须按当前 worktree Git 状态与日志 → 当前 SDD → HANDOVER → 最新工作日志的顺序只读重建状态，必要时再查 ROADMAP 和债务记录。

如果项目没有校验器，必须手工确认项目根目录、worktree、分支和完整 HEAD；任一事实不可得或不一致都失败关闭。不得按全局修改时间选择“最新”快照。

## 保存

保存要求当前目录属于 Git 仓库。先收集当前 worktree、分支、完整 HEAD、dirty paths、HANDOVER、最新工作日志和 SDD 证据，再在仓库外创建临时 UTF-8 JSON。JSON 只能包含 `HandoffPayload` 的四个字段：

```json
{
  "current_state": ["当前已验证状态"],
  "failed_approaches": [],
  "open_questions": [],
  "exact_next_step": "下一项可执行动作"
}
```

然后运行项目 CLI（`<payload>` 必须替换成临时 JSON 的绝对路径）：

```powershell
python scripts/session_state.py save --repo . --session-root "$env:USERPROFILE\.Codex\session-data" --topic "short-topic" --payload <payload>
```

无论调用成功还是失败，只删除临时 payload，绝不删除快照。原子功能提交后、用户明确收尾、上下文耗尽、切换 worktree 或任务前必须保存。直接关闭桌面窗口无法保证触发仓库流程；系统依靠下一次恢复时失败关闭兜底，不宣称能拦截该关闭动作。

疑似凭据、token、私钥或秘密不得写入；拒绝时不得回显被拒绝的值。

## 安全边界

本功能采用可信本机用户威胁模型：保存或发现前检查已存在的 session root、`v2`、project key 和 worktree key 目录组件；预先存在的 symlink 或 junction 重定向必须失败关闭。它不防御拥有同一 Windows 账号权限的恶意进程在校验后替换目录，也不实现原生目录句柄（native handle-relative）后端；快照不承载敏感数据，也不跨信任边界共享。

恢复只读，不自动 checkout、reset、clean、merge、push 或修复目录；任何目录、Git、校验或快照异常都回退到只读 Git/SDD/HANDOVER/最新日志恢复。旧快照只隔离和追溯，不因本流程删除。

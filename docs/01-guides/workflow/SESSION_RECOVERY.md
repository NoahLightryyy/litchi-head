# 会话恢复与保存

> 会话快照用于减少恢复时间，不替代仓库证据。恢复过程默认只读并失败关闭。

## 权威顺序

Git/worktree 是事实源；当前分支的 SDD、HANDOVER 和最新工作日志是状态说明；通过一致性校验的 v2 快照是可丢弃的缓存；旧 `.tmp` 和原始任务 JSONL 仅供追溯。

## 启动

从当前项目或明确指定的 worktree 解析路径，并用原生参数数组运行；每个路径是独立数组元素，不拼接命令字符串：

```powershell
$repoPath = (Resolve-Path -LiteralPath '.').Path
$sessionRoot = [System.IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.Codex\session-data'))
$scriptPath = Join-Path $repoPath 'scripts\session_state.py'
$inspectArgs = @($scriptPath, 'inspect', '--repo', $repoPath, '--session-root', $sessionRoot)
& python @inspectArgs
```

只有 `MATCH` 可生成恢复简报并显示 `exact_next_step`。快照超过 7 天时，首次结果即使是 `MATCH` 也不得显示 handoff；必须先得到用户明确确认，再用完全相同的 repo/session root 参数加 `--allow-old` 重新运行：

第二次调用沿用原数组：`$allowOldArgs = $inspectArgs + @('--allow-old')`，再执行 `& python @allowOldArgs`。等价的完整命令是：

```powershell
python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data" --allow-old
```

只有第二次仍为 `MATCH` 才能采用这次校验器输出的 handoff；不得直接读取快照正文。`REPO_AHEAD`、`HEAD_DIVERGED`、`BRANCH_MISMATCH`、`DIRTY_MISMATCH`、`EVIDENCE_CHANGED`、`LEGACY_UNVERIFIABLE` 或 `MALFORMED` 都不得执行快照中的下一步，也不得输出其中的下一步；必须按当前 worktree Git 状态与日志 → 当前 SDD → HANDOVER → 最新工作日志的顺序只读重建状态，必要时再查 ROADMAP 和债务记录。

如果项目没有校验器，必须手工确认项目根目录、worktree、分支和完整 HEAD；任一事实不可得或不一致都失败关闭。不得按全局修改时间选择“最新”快照。

## 保存

保存要求当前目录属于 Git 仓库。先收集当前 worktree、分支、完整 HEAD、dirty paths、HANDOVER、最新工作日志和 SDD 证据。构造或打印参数数组前，必须扫描四个 payload 字段和 `$topic`；发现疑似 secret 就停止，不创建文件、不启动进程、不回显值，秘密 topic 不得进入进程参数或 transcript。

在系统临时目录创建唯一 UTF-8 JSON，确保位于 `$repoPath` 和 `$sessionRoot` 之外，并记录精确的 `$payloadPath`。JSON 只能包含 `HandoffPayload` 的四个字段：

```json
{
  "current_state": ["当前已验证状态"],
  "failed_approaches": [],
  "open_questions": [],
  "exact_next_step": "下一项可执行动作"
}
```

然后用解析后的变量和原生数组运行项目 CLI。不得插值或拼接命令字符串；路径和 topic 都是独立数组元素：

```powershell
$cliArgs = @(
    $scriptPath, 'save',
    '--repo', $repoPath,
    '--session-root', $sessionRoot,
    '--topic', $topic,
    '--payload', $payloadPath
)
& python @cliArgs
```

`finally` 中先验证 `$payloadPath` 仍等于本次创建的精确临时文件、仍位于解析后的允许临时根目录，且仍在 repo/session root 之外，然后只执行 `Remove-Item -LiteralPath $payloadPath`。不得使用 glob、通配符、递归目录、推断的 latest 文件或任何 snapshot 路径。无论调用成功还是失败，只删除临时 payload，绝不删除快照。原子功能提交后、用户明确收尾、上下文耗尽、切换 worktree 或任务前必须保存。直接关闭桌面窗口无法保证触发仓库流程；系统依靠下一次恢复时失败关闭兜底，不宣称能拦截该关闭动作。

疑似凭据、token、私钥或秘密不得写入；拒绝时不得回显被拒绝的值。

## 安全边界

本功能采用可信本机用户威胁模型：保存或发现前检查已存在的 session root、`v2`、project key 和 worktree key 目录组件；预先存在的 symlink 或 junction 重定向必须失败关闭。它不防御拥有同一 Windows 账号权限的恶意进程在校验后替换目录，也不实现原生目录句柄（native handle-relative）后端；快照不承载敏感数据，也不跨信任边界共享。

恢复只读，不自动 checkout、reset、clean、merge、push 或修复目录；任何目录、Git、校验或快照异常都回退到只读 Git/SDD/HANDOVER/最新日志恢复。旧快照只隔离和追溯，不因本流程删除。

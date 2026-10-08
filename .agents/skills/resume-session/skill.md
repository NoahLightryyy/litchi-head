# resume-session — Git 校验的会话恢复

以下唯一契约块是本文件全部恢复授权的机器可解析事实源。块外正文只解释执行方式，不能新增、修改或覆盖授权。

<!-- SESSION_RECOVERY_CONTRACT_BEGIN -->
VERSION=1
AUTHORITY=Git/worktree
STEP_1=VALIDATOR scripts/session_state.py inspect BEFORE snapshot_body HANDOVER
STEP_2=STATUS_GATE
ALLOW=MATCH_ONLY
NON_MATCH=REPO_AHEAD,HEAD_DIVERGED,BRANCH_MISMATCH,DIRTY_MISMATCH,EVIDENCE_CHANGED,PROJECT_MISMATCH,LEGACY_UNVERIFIABLE,MALFORMED
NON_MATCH_ACTION=NEVER_EXPOSE_OR_EXECUTE_NEXT_STEP
OLD_MATCH=CONFIRM_THEN_FULL_RERUN_--allow-old_THEN_MATCH_ONLY
LEGACY=HISTORICAL_ONLY_NEVER_NEXT_STEP
GLOBAL_MTIME=FORBIDDEN
STEP_3=GIT
STEP_4=SDD
STEP_5=HANDOVER
STEP_6=LATEST_LOG
OVERRIDE=FORBIDDEN_FOR_LATER_EMERGENCY_OR_OTHER_DOCUMENTS
<!-- SESSION_RECOVERY_CONTRACT_END -->

## 执行说明

1. 从当前 workspace 或用户明确指定的项目路径解析 worktree、分支、完整 HEAD、dirty paths 和 worktree 列表。
2. 在读取任何恢复材料前，用独立参数运行：

   ```powershell
   python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data"
   ```

3. 严格按契约块的状态门处理校验输出。旧快照获得明确确认后，用相同 repo/session root 完整重跑：

   ```powershell
   python scripts/session_state.py inspect --repo . --session-root "$env:USERPROFILE\.Codex\session-data" --allow-old
   ```

4. 需要仓库重建时，严格按契约块 `STEP_3` 至 `STEP_6` 的顺序读取证据；legacy 文件只用于追溯。
5. 输出 WORKTREE、BRANCH、完整 HEAD、SNAPSHOT、STATUS、CONFLICTS、AUTHORITY、进度、失败方案和阻塞。恢复摘要后停止，等待用户方向。

恢复默认只读。不得 checkout、reset、clean、merge、push、修复快照目录、删除快照或自动修改仓库。校验器缺失时手工核对项目、worktree、分支和完整 HEAD；事实不全即失败关闭。任何后续章节、紧急流程或其他文档都只能引用唯一契约块，不能覆盖它。

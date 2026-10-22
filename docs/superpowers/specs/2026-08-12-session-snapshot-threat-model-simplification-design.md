# 会话快照威胁模型收缩设计

> 日期：2026-08-12  
> 状态：用户已批准设计方向，待实施计划  
> 目的：纠正 Task 5 将会话缓存扩展为 Windows 安全存储系统的范围失控

## 1. 决策

会话快照是可丢弃的恢复缓存，不是事实源，也不是面向同一 Windows 账号下恶意并发进程的安全存储。Git/worktree、SDD、HANDOVER 与最新工作日志仍是恢复事实源。

系统防御以下实际风险：

- 读到其他项目、worktree、分支或旧 HEAD 的快照；
- 损坏、超限、字段非法或包含可疑凭据的快照；
- 已存在的 symlink/junction 将保存或读取明显重定向到预期目录之外；
- 中断写入、重复文件名、半写文件和普通并发保存；
- 异常输出泄露 payload、Git 输出或文件内容。

系统不防御拥有当前用户权限的并发恶意进程在校验后原地把普通目录改造成 junction。该能力本身足以修改用户文件；为其实现完整 NT handle-relative 文件系统后端不符合本功能的风险与收益。

## 2. 简化实现

保留已经提交并验证的实现：

- v2 项目/worktree 隔离与 Pydantic 严格契约；
- Git 身份、HEAD、dirty paths 和 evidence 校验；
- 过期时间精确边界、legacy quarantine 与 fail-closed 状态机；
- CLI 的稳定退出码、结构化失败原因和净化错误边界；
- 同目录临时文件、fsync、no-clobber 发布、大小限制及读取同一文件句柄；
- Windows 对最终候选文件 reparse point 的同句柄拒绝。

撤销尚未提交的 Round 5 原生目录后端与相关测试。采用最小目录边界：

1. 保存或发现前检查 session root、`v2`、project key 和 worktree key 中已存在的目录组件；发现 symlink/reparse point 立即失败关闭。
2. 继续使用普通路径执行目录创建、枚举和发布，不实现 NT 相对目录句柄 API。
3. 任一目录、Git 或快照操作异常都返回稳定诊断，不执行快照中的 `exact_next_step`。
4. 恢复失败时转入只读 Git 恢复流程，而不是尝试修复目录或降级读取不可信候选。

## 3. 删除与保留的测试

删除或改写要求抵御“校验后由同账号进程原地设置 reparse point”的竞态测试，以及仅为 NT/POSIX 原生目录后端存在的 binding 测试。

保留并补齐产品边界测试：

- 预先存在的 `v2`、project 或 worktree symlink/junction 被拒绝；
- 正常 Windows/POSIX 目录可保存、发现和读取；
- 原子发布、禁止覆盖、清理失败回滚不回归；
- 非法 UTF-8、序列化 Unicode 错误及所有公开异常不泄露内容；
- 任一失败状态不输出 handoff，CLI 返回约定退出码；
- 真实 2026-07-30 legacy 事件仍为 `LEGACY_UNVERIFIABLE`。

## 4. 文档与债务

项目恢复文档明确声明可信本机用户威胁模型，并说明快照失败时回退 Git。若未来快照承载敏感数据、跨信任边界共享或作为守护进程运行，再登记独立安全项目评估 handle-relative 存储；当前不预埋该复杂度。

Round 5 的失败尝试、真实 junction 逃逸证据和本次范围裁决写入工作日志与债务记录，避免后续代理重新扩大威胁模型。

## 5. 验收

- 未提交 Round 5 约千行原生后端改动被完整撤销；
- 精简后的新增代码和测试规模与产品目标相称；
- Task 1–5 专项测试、Ruff、Pyright 和 `python scripts/check.py --full` 全部通过；
- 独立 Python 复审确认无 Critical/Important 产品边界问题；
- 不提交、不发布任何已知会把快照写出作用域的实现。

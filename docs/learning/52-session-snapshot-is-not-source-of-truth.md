# 52｜会话快照不是事实源

## 一句话

> 会话快照是帮助恢复上下文的缓存；只有当前 worktree、Git 提交和同分支交接证据能证明项目现在在哪里。

---

## 为什么需要它？

2026-08-10 的项目已经完成 KR-3B-2 并写好 E0 实施计划，但 `~/.Codex/session-data`
最后一份快照仍停在 2026-07-30。旧恢复流程只取全局最新文件，于是把 TD-072 当成
当前下一步。

这里没有丢 Git 数据。真正的问题是把一个没有项目、分支、HEAD 和证据哈希的缓存，
当成了事实数据库。

## 它的解法

恢复前先建立固定权威顺序：

```text
worktree + Git
  > 当前分支 SDD/HANDOVER/工作日志
  > 通过一致性校验的新快照
  > 旧快照
  > 原始任务事件
```

新快照记录完整 HEAD、分支、脏路径和交接文档哈希。只要仓库前进、分支改变、脏路径
不同或证据变化，就失败关闭并重新从仓库恢复，不能执行快照中的旧“下一步”。

---

## 项目里的真实设计与代码

设计规格：

```text
docs/superpowers/specs/2026-08-11-session-recovery-reliability-design.md
```

计划实施入口：

```text
scripts/session_state.py
tests/test_scripts/test_session_state.py
```

核心判定不是“文件够不够新”，而是“快照描述的世界是否仍与当前世界一致”：

```python
if is_ancestor(snapshot.git_head, current.git_head):
    return "REPO_AHEAD"
if snapshot.git_head != current.git_head:
    return "HEAD_DIVERGED"
if snapshot.dirty_paths != current.dirty_paths:
    return "DIRTY_MISMATCH"
if snapshot.handover_hash != current.handover_hash:
    return "EVIDENCE_CHANGED"
return "MATCH"
```

实现尚未落地；以上是已批准设计中的目标接口，不是当前生产代码。

---

## 和普通“最近文件”有什么不同？

| 对比 | 最近文件策略 | 一致性恢复 |
|:-----|:-------------|:-----------|
| 选择依据 | 全局修改时间 | 项目 + worktree + Git 身份 |
| 仓库前进 | 可能继续旧任务 | 明确判定 `REPO_AHEAD` |
| 跨分支 | 容易串线 | `BRANCH_MISMATCH` 失败关闭 |
| 旧格式 | 照常执行 | 只作历史线索 |
| Git 报错 | 容易当成空变化 | 稳定错误并停止 |

---

## 面试会怎么问

> **Q：为什么时间戳不能证明缓存是最新的？**
>
> A：时间只说明文件什么时候写过，不能证明它属于当前项目、分支或提交。可靠恢复需要
> 比较内容身份：项目路径、worktree、提交图、脏文件集合和交接证据哈希。无法验证时应
> 失败关闭，而不是选择“看起来最新”的文件继续执行。

---

## 自己试试（5 分钟）

1. 查看当前 `git log -3` 和 7 月 30 日快照的时间；
2. 思考：即使快照只旧 1 分钟，只要期间产生新提交，它还能自动恢复吗？
3. 切换到另一个 worktree，比较为什么同一个仓库名仍不足以证明身份；
4. 列出恢复报告必须显示的五项证据。

---

**上一篇：[51｜闭卷评测与两阶段验证](51-closed-book-e0-validation.md)**

**下一篇：待后续卡片**

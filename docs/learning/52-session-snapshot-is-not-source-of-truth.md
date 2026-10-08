# 52｜会话快照不是事实源

## 一句话

> 会话快照是可信本机用户环境里的可丢弃缓存；当前 worktree、Git 提交和同分支交接证据才是事实源。

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
不同或证据变化，就失败关闭并重新从仓库恢复，不能执行快照中的旧“下一步”。保存或发现
时，如果已有 `v2`、project key 或 worktree key 目录是符号链接/junction/reparse point，也
同样失败关闭。

2026-08-21 的 TD-078 回归还证明：只在官方保存入口查凭据不够，因为外部程序可以直接写入
结构合法的 v2 JSON。`write_snapshot` 与 `load_v2` 现在都调用同一个窄扫描契约；载入发现
凭据时只返回稳定的 `SnapshotStoreError`，不让正文进入文本或 JSON 恢复报告。

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

核心判定不是“文件够不够新”，而是“快照描述的世界是否仍与当前世界一致”。HEAD 相等只表示
HEAD 这一项匹配，代码仍会继续检查脏路径和证据；只有 HEAD 不等时才判断祖先关系：

```python
if snapshot.git_head != current.git_head:
    if is_ancestor(repo, snapshot.git_head, current.git_head):
        return "REPO_AHEAD"
    return "HEAD_DIVERGED"
if snapshot.dirty_paths != current.dirty_paths:
    return "DIRTY_MISMATCH"
if snapshot.handover_hash != current.handover_hash:
    return "EVIDENCE_CHANGED"
return "MATCH"
```

这些规则已经落地在 `scripts/session_state.py`、`scripts/session_state_git.py` 与
`scripts/session_state_store.py`，并由相应的 `tests/test_scripts/test_session_state*.py`
覆盖。快照、目录或 Git 检查有任何不确定性时，恢复只读取 Git、SDD、HANDOVER 和工作日志。

凭据边界也必须在读写两端一致：

```python
payload = snapshot.model_dump(mode="json")
_reject_suspected_secret(payload)  # write_snapshot

loaded = SessionSnapshotV2.model_validate_json(encoded)
_reject_suspected_secret(loaded.model_dump(mode="json"))  # load_v2
```

这里故意不用熵评分或第三方扫描器。冻结的范围只覆盖可审计的常见形式：`sk-`、具名
key/token/password/secret 赋值、PEM 私钥头、带认证的 URI/连接串、AWS key 和 GitHub token
前缀。`token budget`、`password policy`、`secret-free snapshot` 这类普通恢复文字仍能通过。
对应的参数化契约在 `tests/test_scripts/test_session_state_store.py`，文本/JSON 隔离回归在
`tests/test_scripts/test_session_state.py`。

Fix Round 1 补上了一个容易漏掉的层次：扫描结构化 JSON 能发现字段名和值的组合，却会把
字符串内部的引号转义，也会在连接串前加上 JSON 引号，从而破坏正则的引号或行首语义。
因此 `contains_secret` 既扫描序列化后的整体，也递归扫描每个原始字符串值；这让双引号
AWS secret assignment、以 `Pwd=` 开头的连接串和空用户名的认证 URI 都走同一失败关闭边界。

---

## 威胁模型要花在真正的风险上

测试曾用一个**预先存在**的真实 Windows junction 证明基线会把快照写到作用域外；因此产品
实现会拒绝这种在验证时已存在的重定向。它不承诺抵御同一 Windows 账号的进程在验证以后，
再把一个普通目录原地换成 junction：该进程已拥有修改用户文件的权限，完整 NT
handle-relative 目录后端的复杂度不符合这项可丢弃缓存的收益。

这不是忽略 TOCTOU，而是明确预算：先保护能稳定检测、用户会真实遇到的预存重定向；其余
情况回到只读仓库证据。若快照日后跨信任边界、含敏感材料，或跑在特权/共享服务中，必须重开
`TD-077`，重新做安全设计，不能沿用今天的边界。

---

## 和普通“最近文件”有什么不同？

| 对比 | 最近文件策略 | 一致性恢复 |
|:-----|:-------------|:-----------|
| 选择依据 | 全局修改时间 | 项目 + worktree + Git 身份 |
| 仓库前进 | 可能继续旧任务 | 明确判定 `REPO_AHEAD` |
| 跨分支 | 容易串线 | `BRANCH_MISMATCH` 失败关闭 |
| 旧格式 | 照常执行 | 只作历史线索 |
| Git 报错 | 容易当成空变化 | 稳定错误并停止，改读仓库证据 |
| 外部直接写入合法 JSON | 绕过保存入口检查 | `load_v2` 用同一扫描器重新隔离 |
| 已有重定向目录 | 可能被带出作用域 | 保存/发现立即失败关闭 |
| 校验后的同账号目录替换 | 常被误承诺为已防御 | 当前明确不在威胁模型内 |

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
4. 看 `tests/test_scripts/test_session_state_store.py` 的预存 junction 测试，区分“验证前已存在”与“验证后替换”；
5. 把 `token budget` 和一个假的 `ghp_` 测试值分别传给 `contains_secret`，解释为什么前者允许、后者拒绝；
6. 列出恢复报告必须显示的五项证据，并说明不确定时为何要回到 Git。

---

**上一篇：[51｜闭卷评测与两阶段验证](51-closed-book-e0-validation.md)**

**下一篇：待后续卡片**

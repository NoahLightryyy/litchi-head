# 53｜多窗口开发为什么必须隔离工作树

> 一句话：Git 分支只是提交指针；两个窗口共用同一个工作目录时，未提交文件仍然完全共享，
> 所以真正的并行隔离单位必须是 worktree + 分支。

## 为什么只建分支还不够？

工作树中的文件不属于某个窗口。窗口 A 修改后端、窗口 B 修改前端，只要它们指向同一目录，
两边执行 `git status` 都会看到全部修改。此时 `git add -A` 会把两个任务一起暂存；切分支、
整体 stash 或变基也可能连带处理另一边尚未完成的文件。

`git worktree` 让同一仓库拥有多个独立检出目录。每个目录绑定自己的分支和未提交状态，
后端窗口、前端窗口和集成窗口才真正互不踩文件。

## 项目里的标准结构

```text
main（稳定线）
├─ backend worktree  → codex/backend-<scope>
├─ frontend worktree → codex/frontend-<scope>
└─ integration       → codex/integration-<scope>
```

后端先冻结 Pydantic/OpenAPI、错误码和重试语义并提交；前端再同步 TypeScript、client、
hooks、五态和测试。集成分支按上游到下游顺序合并，完成消费者契约和浏览器故障验证后，
才进入 `main`。

## 为什么要按路径暂存？

即使已经使用独立 worktree，也应让提交保持原子：

```bash
git status --short
git add -- path/to/owned-file path/to/owned-test
git diff --cached --name-only
git diff --cached
git commit -m "fix: atomic task"
```

`git diff --cached` 是最后一道边界检查：它回答“本次提交究竟会带走什么”，而不是“工作树
里现在有什么”。

## 已经共用脏工作树怎么办？

先停止新的写操作、切分支、合并和整体 stash。建立“文件 → 窗口/任务”归属表，按任务
逐个路径级暂存；同文件重叠转给集成窗口处理。当前批次清理后，后续开发迁移到独立
worktree。

项目完整规则见 `docs/01-guides/workflow/CONCURRENT-DEVELOPMENT.md`。

## 自己试试（5 分钟）

1. 在仓库运行 `git worktree list`；
2. 比较两个 worktree 的绝对目录和分支；
3. 在一个 worktree 新建临时未跟踪文件，确认另一个 worktree 看不到它；
4. 思考：如果两个窗口共用目录，`git add -A` 为什么无法判断文件归属？

---

**上一篇：[52｜证据不完整时怎样继续推理而不伪装完整](52-evidence-limited-reasoning.md)**

## 本次集成补充（2026-10-01）

跨分支不仅合代码：债务和卡片编号也要去重。接口改为缓存情绪读取时，所有调用链测试的 mock 必须同步；证据适配测试需 mock 独立审查和大师复核，避免本地密钥让测试误发真实 LLM 请求。集成目录单独跑完整闸门，源目录保留。

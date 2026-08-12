# 会话恢复可靠性设计

> **状态**：部分实施。原计划 Tasks 1–6 已完成：核心快照契约、Git/证据校验、存储、状态机、
> CLI、全局 Skills 与项目工作流均已接线；当前目录边界采用 `55c2efc` 的可信本机用户简化
> 方案。Task 7 初步 round-trip 与仓库推进证明通过，但最终复审因 TD-078～TD-080 阻塞；
> TD-076 保持未关闭，修复并复审后再恢复最终闸门。以当前 Git 提交和 SDD ledger 为准。
> **日期**：2026-08-11
> **状态更新**：2026-08-12
> **范围**：Codex 会话快照的保存、发现、校验、恢复，以及 litchi-head 的启动权威规则。
> **事故样本**：2026-08-10 错把 2026-07-30 快照中的 TD-072 当成当前下一步。

## 1. 问题与证据

当前存在两套没有自动同步的状态：

- `~/.codex/sessions/YYYY/MM/DD/*.jsonl` 保存桌面任务的原始事件；
- `~/.Codex/session-data/*-session.tmp` 只在显式执行 `save-session` 时生成恢复快照。

事故当天原始事件目录有 31 个任务记录，当前 worktree 有 12 个晚于快照的提交，
但恢复快照仍停留在 2026-07-30。旧 `resume-session` 只按全局修改时间选择文件，
不校验项目、worktree、分支、Git HEAD 或仓库是否已经前进。代理随后又漏掉了“超过
7 天必须报警”的既有要求，最终把历史线索误判成当前事实。

这不是 Git 数据丢失，而是恢复缓存失去新鲜度后仍被当成事实源。

## 2. 目标与非目标

### 2.1 目标

1. 恢复前必须证明候选快照属于当前项目和 worktree；
2. 必须用当前 Git 与项目交接资料验证快照新鲜度；
3. 无法证明一致时失败关闭，转入仓库恢复流程，禁止直接执行快照中的下一步；
4. 新快照必须携带可机器校验的项目、分支、HEAD 和文档证据；
5. litchi-head 必须把 Git/worktree 明确为事实源，把快照降级为可丢弃缓存；
6. 用确定性测试覆盖跨项目、跨分支、仓库前进、旧格式和损坏快照。

### 2.2 非目标

- 不修改 Codex 桌面端内部事件存储格式；
- 不假设存在仓库可以控制的“窗口关闭”或“任务结束”钩子；
- 不从原始 JSONL 自动推断业务结论或重放模型思考过程；
- 不删除旧 `.tmp` 快照；旧文件只降级为历史资料；
- 不让恢复流程自动切分支、重置工作区、合并或推送。

## 3. 权威模型

恢复时采用固定权威顺序：

1. 当前 worktree 的真实路径、Git HEAD、分支、状态和提交图；
2. 当前分支中的 SDD progress、HANDOVER、ROADMAP 和最新工作日志；
3. 经过一致性校验的新式会话快照；
4. 旧式 `.tmp` 快照；
5. Codex 原始任务 JSONL，仅在人工追溯时读取。

低层数据可以补充高层数据没有记录的失败尝试，但不得覆盖高层事实。发生冲突时，
恢复报告必须列出冲突并停止在“已定位、未继续”的状态。

## 4. 新式快照契约

新快照使用 UTF-8 JSON，`schema_version` 固定为 `2`。JSON 比自由格式 Markdown 更适合
严格解析、字段校验和回归测试。业务交接正文仍保留为结构化字符串字段。

```json
{
  "schema_version": 2,
  "snapshot_id": "20260811T093000+0800-48e9eb3",
  "saved_at": "2026-08-11T09:30:00+08:00",
  "project_root": "E:\\litchi-head",
  "worktree_path": "E:\\litchi-head\\.worktrees\\kr-3b-2-failure-diagnostics",
  "branch": "codex/kr-3b-2-failure-diagnostics",
  "git_head": "48e9eb34e72763143ac7803ef45860a933176998",
  "git_dirty": false,
  "dirty_paths": [],
  "handover": {"path": "docs/01-guides/HANDOVER.md", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "latest_work_log": {"path": "docs/04-changelog/logs/2026-08-10/2026-08-10.md", "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
  "sdd_progress": {"path": ".superpowers/sdd/2026-08-10-readme-public-status-sync/progress.md", "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},
  "topic": "E0 validation checkpoint",
  "current_state": [],
  "failed_approaches": [],
  "open_questions": [],
  "exact_next_step": "按已批准计划实施 E0 validation checkpoint"
}
```

示例中的重复十六进制 SHA-256 仅用于展示字段长度，不代表真实文件内容。

约束如下：

- 所有时间使用带时区的 RFC 3339；
- `project_root` 和 `worktree_path` 保存解析后的绝对路径；Windows 比较大小写不敏感；
- `git_head` 必须是完整 commit ID；无 Git 仓库时不得生成可自动恢复快照；
- 脏工作区必须记录排序后的相对路径，不得只写 `git_dirty=true`；
- 文档证据必须同时保存路径和 SHA-256；不存在时显式写 `null`；
- 不保存 API key、环境变量值、访问令牌或未脱敏日志；
- 写入使用同目录临时文件和原子替换，禁止留下半写快照。

存储按项目和 worktree 隔离：

```text
~/.Codex/session-data/v2/<project-key>/<worktree-key>/<timestamp>-<head>-session.json
```

`project-key` 与 `worktree-key` 由规范化路径哈希生成，避免名称碰撞和非法路径字符。

## 5. 恢复状态机

### 5.1 候选发现

1. 读取当前 cwd、Git 顶层路径、公共仓库目录、worktree 路径、分支和 HEAD；
2. 只枚举当前 `project-key/worktree-key` 下的新式快照；
3. 找不到时才扫描旧 `.tmp`，且必须解析并匹配其中的 Project 路径；
4. 绝不因为文件“全局最新”而加载另一个项目或 worktree。

### 5.2 一致性判定

每个候选只能得到以下一种状态：

| 状态 | 条件 | 行为 |
|:-----|:-----|:-----|
| `MATCH` | 项目、worktree、分支、HEAD、脏路径和证据哈希全部一致 | 可生成恢复简报 |
| `REPO_AHEAD` | 快照 HEAD 是当前 HEAD 的祖先 | 标记过期，转仓库恢复 |
| `HEAD_DIVERGED` | 两个 HEAD 无祖先关系或无法验证 | 失败关闭 |
| `BRANCH_MISMATCH` | worktree 相同但分支不同 | 失败关闭 |
| `DIRTY_MISMATCH` | 脏状态或路径集合不同 | 失败关闭 |
| `EVIDENCE_CHANGED` | HANDOVER、工作日志或 SDD 哈希变化 | 标记过期，转仓库恢复 |
| `PROJECT_MISMATCH` | 项目或 worktree 不匹配 | 排除候选，不读取正文 |
| `LEGACY_UNVERIFIABLE` | 旧快照没有 HEAD/哈希 | 仅作历史线索 |
| `MALFORMED` | JSON、字段、时间或路径无效 | 报错并跳过，禁止猜测 |

“超过 7 天”保留为额外告警，但不能代替 Git 一致性判断。即使只有 5 分钟，只要仓库已前进，
快照也必须判为过期；即使超过 7 天，只要所有证据仍严格一致，也只允许用户确认后继续。

### 5.3 仓库恢复

候选不是 `MATCH` 时，自动执行只读恢复：

1. `git status --short --branch`；
2. 当前分支最近提交和快照 HEAD 之后的提交；
3. 当前 HANDOVER 的状态/优先级；
4. 最新工作日志；
5. 当前 worktree 最新 SDD progress。

输出必须区分“快照声称”“仓库证明”和“仍未知”。在用户确认前不得执行旧快照的
`exact_next_step`，也不得修改文件。

## 6. 保存流程与可实现的自动化边界

`save-session` 先收集 Git 和证据字段，再生成交接正文，最后原子写入 JSON。以下节点必须
调用保存流程：

- 用户明确要求收尾、保存或写进文档；
- 上下文进入耗尽交接；
- 完成原子功能、闸门通过并提交后；
- 切换 worktree 或把工作交给新任务前。

桌面窗口被直接关闭时，当前仓库和 Skill 无法保证获得生命周期回调。因此本阶段不承诺
“任意退出都自动保存”。这个剩余限制登记为债务；恢复安全性依靠失败关闭，而不是依靠
快照一定存在。原始 JSONL 只承担人工追溯，不承担自动恢复。

## 7. 分层实现边界

### 7.1 全局 Skill 层

- `source-command-resume-session`：禁止全局最新即权威；要求项目过滤、一致性报告和失败关闭；
- `source-command-save-session`：采用 v2 JSON 契约、项目隔离目录和原子写入；
- 两个 Skill 均明确旧 `.tmp` 只作历史线索，不自动执行其下一步。

### 7.2 litchi-head 仓库层

- 新增可测试的 `scripts/session_state.py`，负责采集、保存、发现和校验；
- 新增对应单元测试，使用临时 Git 仓库，不依赖用户真实 `~/.Codex`；
- `AGENTS.md` 和 `STARTUP.md` 把“resume 或手动读取”改为组合校验；
- HANDOVER 修正过期启动日期，并记录当前恢复规则；
- CLOSING 流程加入可观测保存触发点。

全局 Skill 是编排入口，仓库脚本是 litchi-head 的确定性执行与测试载体。其他项目没有该脚本时，
全局 Skill 只能执行同等严格的只读人工校验，不得降级为旧行为。

## 8. 错误与安全策略

- **2026-08-12 威胁模型校正**：会话快照是可信本机用户环境中的可丢弃恢复缓存，
  不是事实源，也不是抵御同一账号恶意并发进程的安全存储。当前 worktree、Git 与
  同分支仓库证据始终权威；快照、目录或 Git 操作出现任何不确定性时，只能回到只读的
  Git/SDD/HANDOVER/工作日志恢复，绝不执行快照中的 `exact_next_step`。未提交的 Round 5
  原生目录后端（983 行新增、58 行删除）已撤销，且从未提交或发布。
- 所有 Git 命令错误都返回稳定诊断，不把空输出当作“没有变化”；
- 保存或发现时，session root 以下已存在的 `v2`、project key、worktree key 目录组件
  如为符号链接或 Windows reparse point，立即失败关闭；普通目录在校验后的同账号原地
  变更不属于当前威胁模型；
- 快照正文不得触发命令执行；所有字段作为数据处理；
- 恢复命令只读，禁止自动 checkout、reset、clean、merge、push；
- 快照包含疑似 secret 时拒绝写入，并只报告字段位置，不回显值；
- 多个 `MATCH` 候选按 `saved_at` 选择最新，同时在报告中列出被忽略候选。

## 9. 测试矩阵

实施必须按 TDD 覆盖：

1. 同项目、同 worktree、同 HEAD、干净状态得到 `MATCH`；
2. 当前 HEAD 晚于快照得到 `REPO_AHEAD`；
3. 分支不同得到 `BRANCH_MISMATCH`；
4. 两条提交线分叉得到 `HEAD_DIVERGED`；
5. 脏路径增加、删除或改名得到 `DIRTY_MISMATCH`；
6. HANDOVER、日志或 SDD 内容变化得到 `EVIDENCE_CHANGED`；
7. 另一个项目中更新的快照不会成为候选；
8. 旧 `.tmp` 得到 `LEGACY_UNVERIFIABLE`，不会返回可执行下一步；
9. 损坏 JSON、缺字段、无效时间和不存在 HEAD 得到 `MALFORMED`；
10. Git 命令失败不会被误判为一致；
11. 写入中断不覆盖上一份完整快照；
12. secret 扫描拒绝包含凭据的快照；
13. Windows 路径大小写差异可匹配，不同 worktree 不可匹配；
14. 项目文档包含权威顺序、失败关闭和保存触发点。

## 10. 迁移与回滚

1. 先用测试锁定现有错误；
2. 实现仓库脚本并只运行 `inspect`，不写快照；
3. 更新全局 Skill 和项目规则；
4. 生成第一份 v2 快照并验证能够判为 `MATCH`；
5. 创建一个仓库前进场景，证明旧 v2 快照转为 `REPO_AHEAD`；
6. 保留旧 `.tmp`，但从自动候选中降级；
7. 全量闸门通过后提交项目内改动，不自动 push。

若全局 Skill 修改出现问题，回滚 Skill 文本不会破坏仓库或 v2 快照；项目脚本仍可独立输出
一致性报告。任何回滚都不得恢复“全局最新文件直接执行”的旧行为。

## 11. 验收标准

- 本次 7 月 30 日事故样本稳定得到 `LEGACY_UNVERIFIABLE` 或仓库前进诊断；
- 恢复输出明确列出实际 worktree、分支、HEAD、快照时间和判定状态；
- 不同项目/分支快照不能被选中；
- 未通过一致性校验时，不输出“Ready to continue”或自动执行下一步；
- 项目规则、学习卡片、债务、工作日志和引用同步完成；
- 专项测试、Ruff、Pyright、README 同步检查和项目完整闸门通过。

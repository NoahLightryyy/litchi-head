# 2026-11-16 v1.0 收尾：依赖锁定、一键启动、异常审计、编排器拆分

## 用户授权与范围

用户要求“先收尾，改成稳定的工具”，并选择：冻结功能 + 一键启动 + 代码加固；Mac 与 Windows 都要启动脚本；
允许本地提交、删除已合并的本地分支、清理失效 worktree 记录。未授权 push，未授权新增功能。

分支 `chore/v1-stabilize`，基于 `084b9bc`（当时 `main` = `origin/main` = 原集成分支，工作区干净）。

## 会话恢复

`scripts/session_state.py inspect` 在助手沙箱（Python 3.10、无项目依赖）无法运行，按契约改为手工核对
项目、worktree、分支与完整 HEAD（`084b9bcf1d5513e507843ae2156f5dd3506bfbec`），再按 Git → HANDOVER → 最新日志只读重建。未使用任何会话快照。

## 发现：全新安装已经不可用（TD-093，已关闭）

`pyproject.toml` 只有下限、没有版本锁。2026-11-16 全新安装拿到 akshare 1.20.65，
该版本已移除 `stock_zh_a_hist` 和 `stock_individual_fund_flow`：Pyright 1 个错误、6 项测试失败，
运行时 K 线与资金流向会走异常分支返回空。本地 `.venv`（akshare 1.19.1）不受影响，所以之前没暴露；
但 CI 下一次运行、以及任何新机器安装都会中招。

处理：从 10-22 验收环境导出 143 个包的版本到 `constraints.txt`；`pyproject.toml` 把 akshare 限制在 `<1.20`；
CI（GitHub/Gitee）、Dockerfile、Makefile、README 与环境文档统一改为 `pip install -e ".[dev]" -c constraints.txt`。

## 一键启动

- `start.command`（macOS，双击）：检查 Python 3.12+ / Node 20+ → 首次建 `.venv` 并按锁安装 → 前端源码有变化才 `next build`
  → 启动 uvicorn(8000) 与 `next start`(3000) → 轮询健康检查 → 打开浏览器。端口占用、依赖安装失败、
  服务启动即退出、超时未就绪各有明确提示和日志路径（`logs/launcher-*.log`）。已在运行时直接打开浏览器。
- `start.bat` + `scripts/start.ps1`（Windows）与 `stop.bat`：同样流程；`.ps1` 以 UTF-8 BOM + CRLF 保存，`.gitattributes` 固定行尾。
- 删除基于 conda 且不启动任何服务的 `start_dev.ps1`，同步清理 `ENVIRONMENT.md` 引用。

验证边界：macOS 脚本在 Linux 沙箱跑通了环境检查、失败提示路径；后端用同一条命令 3 秒内健康检查通过。
前端构建与 `next start` 无法在沙箱验证（`node_modules` 是 macOS 原生二进制）。**Windows 脚本未在真机运行过**（TD-094）。

## 异常处理审计

用 AST 扫描 `src/` 与 `backend/` 全部 194 处 `except Exception`：144 处已记日志，37 处重新抛出，
7 处把异常写入返回结果，6 处静默。静默的 6 处补上与同文件相邻分支同级别的日志，控制流与返回值不变：
`FallbackDataSource.get_stock_industry`（4 处）、复盘批量刷新循环（1 处）、凭据来源探测（1 处）。
没有改变任何错误处理策略（静默/报错的取舍属于需用户决定的事项）。

## 编排器拆分

`src/debate/orchestrator.py` 2285 → 824 行，只保留 `DebateOrchestrator` 与再导出。拆出：

| 新模块 | 内容 |
|---|---|
| `graph_state.py` | `DebateState`、证据限制辅助函数、常量 |
| `collection.py` | `collect_data_node` 与采集后路由 |
| `participants.py` | 分析师 / 策略师 / 同侪复核 / 独立评审的单体执行函数 |
| `graph_nodes.py` | 各轮节点工厂、偏差报告、加权聚合 |

26 个被移动的定义与原文件逐一做 AST 比对，全部一致。`from src.debate.orchestrator import ...` 继续可用；
日志器名保持 `src.debate.orchestrator`。测试里 77 行 `patch("src.debate.orchestrator.X")` 改为指向实际查找该名字的新模块。

## 仓库清理

- 取消跟踪 `.coverage` 并加入 `.gitignore`；移除未使用的 streamlit 依赖组与过期的 `backend/requirements.txt`。
- 删除 4 个已合并且未被任何 worktree 检出的本地分支：`codex/integration-project-20261001`、
  `codex/integration-remaining-20261022`、`codex/readme-graduate-application`、`codex/readme-portfolio-20261022`。
- **未清理 worktree**：`~/.codex/worktrees/` 下 9 个 worktree 在本机真实存在，只是在助手沙箱里路径不可见才显示为 prunable。
  其中是否有未提交改动无法从这里判断，留给用户确认后处理。对应的 8 个 `codex/*` 分支也因此保留。
  `codex/market-availability` 尚未合并进 `main`。

## 验证

锁定依赖、Linux aarch64、Python 3.12.15：

| 检查 | 改动前 | 改动后 |
|---|---|---|
| Ruff | 通过 | 通过 |
| Pyright `src/ backend/` | 0 错误 | 0 错误 |
| Pytest `-m "not slow"` | 2450 通过 / 8 跳过 | 2450 通过 / 8 跳过 |
| 前端 `node --test` | 161 通过 | 未改动前端代码 |
| 前端 `tsc --noEmit` | 通过 | 未改动前端代码 |

与 10-22 记录（2451 通过 / 7 跳过）相差 1 项，是沙箱没有系统凭据管理器后端导致多跳过 1 项。
未运行：慢测试、前端 lint、前端生产构建、GitHub CI（分支未 push）。

## 五同步

代码、测试补丁点、README（中英）、环境与模块文档、债务（TD-093 关闭，TD-094/TD-095 新开）已同步。
学习卡片未新增（是否新增属于需用户决定的事项）。

## 待用户决定

1. 是否 push 并合并到 `main`、是否打 `v1.0.0` 标签。
2. 9 个 Codex worktree 与对应分支的去留。
3. 在 Mac 上双击 `start.command`、在 Windows 上双击 `start.bat` 各实测一次。
4. 是否为“依赖锁定”和“编排器拆分”各写一张学习卡片。

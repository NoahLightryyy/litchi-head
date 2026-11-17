# 2026-11-17 合并 market-availability 与 ETF 目录修复

## 起因

用户在新 Mac 上双击 `start.command` 提示没有权限，随后反馈“搜索的股票、证券、ETF 不完整”。

## 发现

1. **`start.command` 没有可执行位。** 提交里的文件模式是 644。已改为 755 并提交。
2. **用户日常运行的不是 `main`。** 正在提供服务的是 `~/.codex/worktrees/market-availability`
   （分支 `codex/market-availability`，自 `88fc22a` 起 43 个提交、293 个文件，从未合并）。
   2026-11-16 的收尾（依赖锁定、一键启动、编排器拆分）做在了 `main` 的后继上，两条线已经分叉。
   依据：运行中的后端返回 `STOCK_CATALOG_PARTIAL`，该错误码只存在于这条分支。
3. **ETF 搜不到的根因是校验过严。** 新浪 `getHQNodeStockCount` 自报 938，分页 `getHQNodeData`
   实际一致地返回 927（前 9 页各 100、第 10 页 27、第 11 页为空，无重复，按 symbol 有序）。
   `fetch_catalog` 要求每页条数与自报总数严格对应，于是抛出 “ETF directory truncated”，整份目录不可用。
   在用户网络下用浏览器直接请求新浪接口复现；该问题两条分支都有。
4. **股票目录首次不完整**：四个交易所目录共用 8 秒时限，首次请求超时，第二次成功。属于已有设计的短退避，本次未改。
5. **搜索结果上限 100 条**（如 “920” 命中 361、返回 100）是既有设计，本次未改。

## 更正：ETF 搜不到的首要原因是本机 DNS（合并后实测）

合并并用 `start.command` 启动新版本后，ETF 目录仍然失败。`logs/launcher-backend.log` 显示：

- 新浪域名（ETF 目录、新浪板块、新浪快讯）与 `www.bse.cn`（北交所股票目录）在 Python 里解析失败：
  `[Errno 8] nodename nor servname provided, or not known`；
- 东方财富、腾讯域名解析和请求正常；
- 同一台机器的浏览器可以正常打开新浪接口。

所以上面第 3 条（938 与 927 不符）是真实存在的第二个问题，但不是用户当前搜不到 ETF 的首要原因；
首要原因与既有债务 ENV-DNS-20261027 相同：系统解析器解析不了部分行情域名。
校验放宽的修复已有单元测试，但在 DNS 恢复前无法在用户机器上端到端确认。
本次没有修改任何系统网络设置，也没有新增数据源或解析方式。

实测结果（新版本，2026-11-17 09:28）：搜索“600519”“中芯国际”可得；“ETF”“510050”“沪深300”无结果；
`failed_sources` 为“股票目录”（北交所缺失，其余三市场可用）和“ETF目录”。

另：`start.command` 首次实跑暴露一个脚本缺陷——macOS 自带 bash 3.2 在变量名后紧跟全角标点时把变量名解析错
（`BACKEND_PORT?: unbound variable`）。已给相关变量加花括号，第二次启动成功；新增 `stop.command`。

## 用户决定

- 合并：把 `codex/market-availability` 合进收尾分支，之后只保留一条线。
- ETF 校验：放宽并提示（各页内部一致即接受，同时披露自报总数与实际条数的差异）。

## 合并

在隔离克隆中把 `origin/codex/market-availability` 合入 `chore/v1-stabilize`，12 个冲突：

| 文件 | 处理 |
|---|---|
| `src/debate/orchestrator.py` | `main` 侧自分叉点未改动，取对方版本后用同一脚本重新拆分；26 个定义与对方文件 AST 逐一相同 |
| `frontend/components/macro/market-data-notice.tsx`、`shared/backend-status.tsx`、`stock/debate-panel.tsx` | 取对方版本。对方是用户每天在用的较新界面；`main` 上 10-22 的“折叠诊断”方案被其取代 |
| `frontend/tests/market-notice.test.mts` | 两边的测试都保留 |
| README、ROADMAP、HANDOVER、债务路由、日志索引、前端 WORKLIST、学习卡 54 | 两边内容都保留 |

对方新增测试里指向 `src.debate.orchestrator.<name>` 的补丁点改为拆分后的模块；
`tests/test_data/test_market_research_policy.py` 改为从 `src.debate.participants` 取用。

遗留：`frontend/lib/market-notice.ts` 的 `marketNoticeLabel` 现在只有测试在用（界面已不调用）。

## ETF 目录修复（ETF-CATALOG-COUNT-001，当轮关闭）

`backend/etf_display.py::fetch_catalog` 的接受条件改为：

- 分页连续：出现不满页之后不得再有数据；
- 身份无重复、按 symbol 有序、末页之后为空、前后两次自报总数一致（以上沿用原有检查）；
- 实际条数不少于自报总数的 95%（`MIN_REPORTED_COVERAGE`），低于则仍按截断拒绝。

满足时接受目录，`EtfCatalog.reported_count` 记录自报总数并写一条 warning 日志。
搜索接口 `SearchResult` 新增 `notices`，不一致时返回
“ETF目录：新浪报告 938 只，实际取到 927 只，已显示取到的全部。”，前端搜索结果上方以中性色显示。
旧后端不返回 `notices` 时前端按空处理。

95% 这个下限是实现时加的保护（防止只取回首页也被当作完整），用户批准的是“内部一致即接受并提示”，下限数值可调。

新增测试：小幅不一致被接受并披露；自报与实际一致时无提示；覆盖不足、只有首页、分页不连续三种情形仍被拒绝；
搜索披露文案；前端对 `notices` 的解析。原有 truncated / repeat / extra / count_changed 四种拒绝用例保持通过。

## 验证

锁定依赖、Linux aarch64、Python 3.12.15：

| 检查 | 结果 |
|---|---|
| Ruff | 通过 |
| Pyright `src/ backend/` | 0 错误 |
| Pytest `-m "not slow"` | 2798 通过 / 8 跳过 |
| 前端 `node --test` | 329 通过 |
| 前端 `tsc --noEmit`、ESLint `--max-warnings 0` | 通过 |

未运行：慢测试、前端生产构建、GitHub CI（未 push）。修复后的 ETF 搜索尚未在用户机器上实测，需重启服务后确认。

## 待用户处理

1. 重启服务后搜索 “ETF” 确认结果与提示。
2. `~/.codex/worktrees/market-availability` 仍检出旧分支并在提供服务；确认新版本可用后再决定是否移除该 worktree。
3. 是否 push、合并到 `main`。

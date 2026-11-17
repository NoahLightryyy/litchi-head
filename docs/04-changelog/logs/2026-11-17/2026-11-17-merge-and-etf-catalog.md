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

## 备用域名解析（用户批准后实现，ENV-DNS-20261027 缓解）

用户说明人在巴黎且经常换 Wi-Fi，改系统 DNS 不合适；同意在程序内处理。

证据：失败的只有经多层 CDN 转接的域名（新浪、北交所，偶发腾讯 `web.ifzq.gtimg.cn`、同花顺资讯），
东方财富直接返回地址所以正常；阿里公共 DNS 对这些域名全部能给出地址；本机未发现运行中的 VPN/代理软件。

实现：`src/utils/dns_fallback.py` 在后端启动时包一层 `socket.getaddrinfo`。系统解析先行；仅在抛出
`socket.gaierror` 时，通过 HTTPS 向 `223.5.5.5`、`1.1.1.1`（按 IP 直连并校验证书）查询 A 记录。
结果按 TTL 缓存（60–600 秒，失败 30 秒），丢弃私有与回环地址；IP、本机名、单标签主机名不介入。
每次使用写 warning 日志，并以 `dns_fallback` 计入数据源健康统计（数据状态页显示为“备用域名解析”）。
`LITCHI_DNS_FALLBACK=0` 可关闭；测试进程默认关闭。未新增数据源，未改系统设置。

用户机器实测（2026-11-17 09:43，巴黎）：

| 项目 | 结果 |
|---|---|
| 备用解析 | 16/16 成功，涉及新浪、北交所、同花顺资讯、腾讯分钟接口域名 |
| 搜索 “ETF” | 927 项，`failed_sources` 为空 |
| 搜索 “510050” / “沪深300” | 上证50ETF华夏 / 27 只 ETF |
| 搜索 “600519” / “中芯国际” | 正常 |
| 指数三源 | 东方财富、新浪、腾讯均健康 |
| 披露 | “ETF目录：新浪报告 938 只，实际取到 927 只，已显示取到的全部。” |

已知不足：披露文案目前出现在每一次搜索结果上方（包括纯股票搜索），偏多；从巴黎到国内服务器的连接慢与偶发超时不在本次范围。

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
| Pytest `-m "not slow"` | 2821 通过 / 8 跳过（含备用域名解析的 23 项） |
| 前端 `node --test` | 329 通过 |
| 前端 `tsc --noEmit`、ESLint `--max-warnings 0` | 通过 |

未运行：慢测试、前端生产构建、GitHub CI（未 push）。修复后的 ETF 搜索尚未在用户机器上实测，需重启服务后确认。

## 待用户处理

1. 重启服务后搜索 “ETF” 确认结果与提示。
2. `~/.codex/worktrees/market-availability` 仍检出旧分支并在提供服务；确认新版本可用后再决定是否移除该 worktree。
3. 是否 push、合并到 `main`。

## 追加：证据包空态说明（用户选择方案 1）

用户反馈“已核验证据与 AI 深入研究”像是坏了。实际是人工核验的证据包只有 3 个（板块 BK0917、股票 688012、ETF 512480），
其他标的的 404 被显示成“尚未配置”，并配了一个不可能生效的“重新读取证据”按钮。

改动（`frontend/components/research/policy-capital-panel.tsx`）：空态写明这不是加载失败、重试无效，
说明功能只覆盖 3 个示例标的并给出入口；重试按钮只在真正的读取错误时显示。
示例清单放在 `frontend/lib/policy-capital.ts`，测试核对它与 `backend/policy_evidence_data/packages.json` 一致。
没有扩大证据包范围，也没有新增模型调用。前端 330 项通过，tsc 与 ESLint 通过。

## 追加：产业链草图缓存随旧运行目录遗留

用户反馈合并后找不到上下游产业链分析。代码未丢失（`frontend/components/sector/*`、`/api/market/sector/{id}/chain-draft`
等与 `codex/market-availability` 完全一致），丢的是数据：`chain_drafts` 与 `chain_companies` 的缓存路径相对代码位置，
之前服务从 `~/.codex/worktrees/market-availability` 运行，AI 生成结果留在了那个目录的 `data/` 下。

已从旧目录复制到当前仓库的 `data/`（均为 git 忽略的本地数据，未重新调用模型）：

- 产业链草图：BK1184 人形机器人、sina:gn_jjzc 基金重仓、sina:gn_cdp 超大盘（后者同名缓存以旧目录较新版本为准，原文件备份在 `data/_backup_20261117/`）；
- 代表企业：BK1184 人形机器人（6 家）、基金重仓（8 家）；
- 分时历史：600126、002885 共 15 个文件。

四个草图的缓存键已按现行 `DEFAULT_MODEL` 核对命中。其余板块没有缓存，打开时显示“AI自动绘图 · 待核验”入口，生成需调用付费模型。

## 追加：辩论中途断网（用户批准的错误处理调整）

现象：ETF 560780 的辩论（session `deb_fc286fbdbf25`）3/5 流派失败、无独立评审。
日志：10:03:49–10:05:24 无任何外部请求；10:05:24 起系统 DNS 与备用解析同时失败；格雷厄姆 120 秒超时，
其后林奇、达利欧、两份同侪复核、独立评审在 7 秒内全部以 `LLM_REQUEST_FAILED` 结束（每个仅由 SDK 重试两次、不足 2 秒）；
10:11 模型调用恢复。判断为约一分半钟的整机断网（休眠或 Wi-Fi 重连，日志无法直接证实），与合并改动无关。

用户同意两点：断网时多等一会儿；失败原因是断网时写明。

- `src/utils/llm.py`：连接失败（`APIConnectionError`，不含超时）在同一次调用内等待重试，间隔 3/6/12/15/15 秒，
  预算 60 秒；仍连不上时报 `LLM_NETWORK_UNAVAILABLE: 网络连接中断，未能连上模型服务`。连接失败的请求不计费。
  请求超时单独报 `LLM_REQUEST_TIMEOUT`，不进入等待循环。HTTP 状态错误与余额不足的处理不变。
- `backend/routers/debate.py`：全部流派失败且原因是断网时返回 `ANALYSIS_NETWORK_UNAVAILABLE` 及对应说明。
- 前端：单个流派的失败原因显示“网络连接中断，未能连上模型服务”或“分析超时”；部分失败的摘要前加原因
  （如“分析期间网络连接中断，部分分析超时；3 位分析未成功…”）。只认后端明确代码，旧记录里的笼统失败不会被改写成断网。

未做：独立评审与同侪复核失败目前不保存原因，界面仍只显示“未取得有效独立评审”；只补跑失败流派的功能未做。
代理单次运行的 120 秒总超时未改，断网等待包含在其中。

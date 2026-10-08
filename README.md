# 🍒 Litchi Head · 荔枝头

[![CI](https://github.com/NoahLightryyy/litchi-head/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/NoahLightryyy/litchi-head/actions)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

面向 A 股的个人投资研究工具。把行情、财报、新闻、公司定位和不同流派的分析放在同一个工作台，帮助用户看清依据、分歧和风险。

**当前阶段：Phase R · 数据可靠性与研究体验加固。** 功能分支已整合到 `main` 并推送 GitHub。最近完整验收为 **2026-10-08**，见[整合记录](docs/04-changelog/logs/2026-10-08/2026-10-08-branch-consolidation.md)。

> [!IMPORTANT]
> 工程测试通过不代表投资效果已经得到验证。项目尚未证明多智能体优于单 Agent、简单规则或买入持有；AI 分数与置信度不等于上涨概率。研究输出保留数据时间、适用周期、成立条件和失效条件，最终投资决策由用户作出。

## 可以做什么

| 页面 | 当前功能 |
|---|---|
| **市场总览** | 三大指数及来源核验、板块资金榜、多渠道新闻、热点词云与历史新闻检索 |
| **搜索与发现** | 搜索股票和板块、浏览器本地搜索历史、多周期涨幅榜与资金排行；不可用周期显示具体限制 |
| **行业研究** | 行业与概念排行、成分股筛选、可追溯资料图、按需 AI 解读及生成地图版本 |
| **个股研究** | 报价、当日/五日分时、日/周/月 K 线、技术指标、财务与资金数据、相关新闻和公告 |
| **公司解读** | 业务与产业链位置、亮点、竞争优势与压力、风险点，以及对盈利预期和估值的条件性影响；附来源并保存结果 |
| **流派分析** | 同时研究短期 1–5 个交易日、中期 1–3 个月、长期 1–3 年；分别呈现条件、风险与结论，支持查询分析历史 |
| **选股与对比** | 按股票、行业或概念搜索，最多四家公司并列比较财务指标 |
| **跟踪与复盘** | 自选、持仓与风险、研究及用户操作记录入口；连续收益验证与完整反馈闭环仍待完善 |

菜单提供 **中文 / English** 选择，目前覆盖导航、页头及部分界面，业务正文和历史 AI 输出尚未全面翻译。

### 图表与指标

- K 线支持 MA / BOLL 主图，以及成交量、MACD、RSI、KDJ 副图；共享时间范围和十字线。
- 默认展示全部**已取得**历史，支持缩放与日期滑块；不代表已经覆盖上市以来全部行情。
- 悬停行情栏显示日期、开高低收、涨跌额、涨跌幅和指标值。
- 当日分时包含价格/百分比轴、行情栏、每分钟成交量和成交额副图；分钟量额由有效的相邻累计值计算，缺口留空。
- 五日分时提供行情栏；当前五日数据契约缺少量额序列，不绘制相应成交副图。
- 财务指标支持点击查看含义与用途；缺失值保留为空，不补成零。

### 数据与研究依据

行情适配器包含东方财富、新浪、腾讯等来源，使用 AKShare、ADaTa 及直连接口。具体页面会显示本次实际使用的来源、数据时间、单源/多源状态和失败诊断；接入多个渠道不意味着每次请求都取得了多个独立证据。

新闻渠道包括财新、新浪、东方财富、财联社、同花顺和富途；个股页还检索相关新闻与公司公告。列表保留各渠道出处，热点统计另行去重。历史库保存采集结果并支持按时间、来源和关键词查询，同时公开实际覆盖范围。

休市研究使用交易日历核验最近收盘报价，保留单源和证据缺口标记。各研究周期分别判断，条件或证据不完整时不强行生成方向共识。公司解读及地图的引用校验不等于逐句事实核验，AI 推断与披露事实分开标注。

## 快速开始

需要 **Python 3.12+、Node.js 24、pnpm 10**。最近 macOS 本地验收使用 Python 3.13；Docker 和 `make` 不是必需依赖。

### 1. 安装依赖

```bash
git clone https://github.com/NoahLightryyy/litchi-head.git
cd litchi-head

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# 已安装 pnpm 时可跳过这一步
npm install --global pnpm@10.33.0
pnpm --dir frontend install --frozen-lockfile
```

Windows PowerShell 使用 `python -m venv .venv` 和 `.\.venv\Scripts\Activate.ps1`。其他环境配置见[环境指南](docs/01-guides/ENVIRONMENT.md)。

### 2. 配置 AI 凭据

```bash
# 首次配置时复制；已有 .env 请保留原配置
cp .env.example .env
python scripts/store-api-keys.py --set DEEPSEEK_API_KEY
```

Windows 复制配置使用 `Copy-Item .env.example .env`。密钥通过交互提示写入系统凭据管理器，不提交到仓库。行情与资料浏览不需要调用 LLM；生成 AI 解读和辩论需要有效凭据，并按供应商用量计费。

当前产品默认使用 **`deepseek-v4-pro` 非思考模式**，以 [`src/utils/llm.py::DEFAULT_MODEL`](src/utils/llm.py) 为准。Flash 快速模型策略仍是后续目标，尚未作为当前产品默认恢复。

### 3. 启动后端与前端

在项目根目录打开两个终端。

**终端一：后端**

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**终端二：前端**

```bash
pnpm --dir frontend dev
```

打开 [http://localhost:3000](http://localhost:3000)。API 文档位于 [http://localhost:8000/docs](http://localhost:8000/docs)。

默认前端连接本机 8000。使用自定义端口或隔离预览时，同时设置 `NEXT_PUBLIC_API_URL=/api` 和 `LITCHI_BACKEND_URL=http://127.0.0.1:<后端端口>`；生产构建需在 `pnpm --dir frontend build` 前设置这些变量。PowerShell 使用 `$env:变量名="值"`。

## 验证与开发

```bash
python scripts/check.py          # Ruff、Pyright、README 同步与按变更选择的检查
python scripts/check.py --full   # 全量非 slow Python 测试及前端 Lint / 类型检查
pnpm --dir frontend test         # 前端消费者与逻辑测试
pnpm --dir frontend build        # 生产构建
```

**最近完整本地验证（2026-10-08，整合代码 `e42c202`）：**

| 检查 | 结果 |
|---|---|
| 项目检查脚本 | 6/6 通过 |
| Python 测试 | 2371 passed、7 skipped、19 deselected |
| 前端测试 | 141 passed |
| Ruff / Pyright / ESLint / TypeScript | 通过 |
| Next.js 生产构建 | 通过 |
| 浏览器验收 | 个股报价、分时主副图对齐、板块资料图及生成入口；错误与重试状态 |

以上是带日期的本地验收快照，最新远程执行结果以 [GitHub Actions](https://github.com/NoahLightryyy/litchi-head/actions) 为准；未展示未经此次测量的覆盖率数字。

并行开发使用独立 worktree 与 `codex/` 分支，经契约、测试和浏览器验收后再合入 `main`。不要在多个窗口中共同修改一个脏工作区，详见[并行开发规则](docs/01-guides/workflow/CONCURRENT-DEVELOPMENT.md)。

**Git 校验的会话恢复**：Git/worktree 与同分支交接记录是事实源，会话快照只是缓存。规范和未完成的安全审核边界见[会话恢复指南](docs/01-guides/workflow/SESSION_RECOVERY.md)。

## 当前限制与后续工作

- **上游可用性**：东方财富部分行情端点仍有 HTTP 502；可用的历史快照会标明时间，不能视为实时行情。详见后端债务 `TD-081`。
- **排行榜覆盖**：部分历史周期、长期资金及总流入口径仍缺可核验数据；不会用当日前若干名回算冒充全市场历史排名。见 `RANKING-HISTORY-001`。
- **资料覆盖**：新闻样本不保证连续覆盖完整时间段；匹配零条不证明没有新闻。长期研究的完整财报、公告、事件链与逐句语义审核仍需补强。
- **图谱与公司研究**：生成内容需人工核对，重大事件自动更新尚未启用；有引用不代表供应关系、竞争优势或股价影响已得到独立证明。
- **收益验证**：E0-100 闭卷评测代码已合入 [`src/backtest/e0/`](src/backtest/e0/)，尚无正式表现裁决。首次真实运行前仍需确认费用和实验参数；KR-4～KR-6 后续阶段在 E0 裁决前暂停，已合入的适配层不代表生产接入完成。
- **交易与反馈**：当前研究输出不自动进入交易决策流程；Broker 接入、连续真实结果、基准对照与收益闭环尚未完成。

完整范围见[债务路由](docs/01-guides/debt/ROUTER.md)、[后端债务](docs/06-departments/08-backend-api/DEBT.md)和[前端债务](docs/06-departments/09-frontend/DEBT.md)。

## 架构与技术栈

```text
数据适配与缓存 → 来源/时间/身份校验 → 研究证据
                                      ↓
                       分析师 → 流派研究 → 审阅与聚合
                                      ↓
                       分周期结论、条件、风险与历史记录
```

研究展示、证据准入和交易相关模块分别保留边界。仓库中存在风控、交易规划、回测与记忆模块，不意味着它们已经完成实盘收益验证。

| 层 | 选型 |
|---|---|
| 后端与契约 | Python、FastAPI、Pydantic v2 |
| AI 编排 | LangGraph / LangChain，统一 LLM 调用层 |
| 当前模型 | DeepSeek V4 Pro，非思考模式 |
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS、TanStack Query |
| 图表 | Lightweight Charts |
| 数据与持久化 | AKShare / ADaTa / 直连适配器，SQLite、JSON、Parquet |
| 工程检查 | pytest、Ruff、Pyright、ESLint、TypeScript、GitHub Actions |

```text
src/
├── agents/       分析与流派 Agent
├── debate/       辩论编排、证据注入与聚合
├── data/         数据源、校验、缓存与采集
├── memory/       记忆与检索
├── callback/     结果回调
├── risk/         风控逻辑
├── trader/       交易规划
├── backtest/     回测与 E0 评测
├── retro/        用户操作与复盘数据
├── core/         通信协议
└── utils/        模型、配置与凭据工具
backend/          FastAPI 路由与展示契约
frontend/         页面、图表与交互
scripts/          检查、凭据与会话工具
tests/            单元、契约与集成测试
docs/             需求、设计、债务、学习卡片与日志
```

## 文档导航

- [项目总览](docs/00-overview/OVERVIEW.md) · [进度看板](docs/00-overview/ROADMAP.md) · [会话交接](docs/01-guides/HANDOVER.md)
- [环境配置](docs/01-guides/ENVIRONMENT.md) · [前端说明](frontend/README.md) · [后端说明](backend/README.md)
- [API 契约](docs/03-modules/10-frontend/API.md) · [辩论引擎规格](docs/03-modules/02-debate-engine/SPEC.md)
- [架构决策](docs/05-decisions/README.md) · [设计哲学](docs/00-overview/DESIGN_PHILOSOPHY.md)
- [E0 评测设计](docs/superpowers/specs/2026-08-10-e0-validation-checkpoint-design.md) · [组织与验证策略](docs/02-requirements/STRATEGY_VALIDATION_AND_ORG_EVOLUTION.md)
- [开发工作流](docs/01-guides/WORKFLOW.md) · [学习卡片](docs/learning/README.md) · [整合与验收日志](docs/04-changelog/logs/2026-10-08/2026-10-08-branch-consolidation.md)

## 许可证

[MIT](LICENSE)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/荔枝头-Litchi%20Head-FF6B35?style=for-the-badge">
    <img alt="Litchi Head" src="https://img.shields.io/badge/荔枝头-Litchi%20Head-FF6B35?style=for-the-badge">
  </picture>
</p>

<p align="center">
  <em>个人多智能体投资决策助手 — 你的 AI 投研团队</em>
</p>

<p align="center">
  <a href="https://github.com/NoahLightryyy/litchi-head/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/NoahLightryyy/litchi-head/ci.yml?branch=main&label=CI&logo=github" alt="CI Status">
  </a>
  <img src="https://img.shields.io/badge/tests-1459%20passed-2ea44f?logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-brightgreen" alt="Coverage">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/type_check-pyright-brightgreen" alt="Pyright">
  <img src="https://img.shields.io/badge/architecture%20decisions-13%20ADRs-informational" alt="ADRs">
</p>

---

## 项目动机

> 散户想认真做投资？打开 APP 满屏推荐、消息轰炸、FOMO 追涨。
> 机构有 10 个 CFA + Bloomberg Terminal — 我就不信一个人配不齐 AI 投研。

**Litchi Head** 的目标是：你问一句话 → 15 秒内拿到结构化的多维投资决策信息，10 秒内能看懂、能决策、能行动。

> 💡 **2026-06-23 新的方向**：投行 vs 散户的真正壁垒不是分析模型，而是**数据纵深**——财报拆解、供应链分析、产业链定位。litchi-head 补上这块，就是极少数同时具备技术分析 + 基本面深度 + AI 多角度辩论的散户投资工具。

## 核心架构

> 哲学：**体系 > 天才** — 这不是一个更好的交易机器人，而是一个组织的模拟。
> 🏛️ 完整设计哲学见 [DESIGN_PHILOSOPHY.md](docs/00-overview/DESIGN_PHILOSOPHY.md)
>
> 三权分立：公式负责调整，镜子负责展示，人负责拍板

```
                         ┌───────────────────────────┐
                         │     💬 用户一句话输入       │
                         │   "蔚来被低估了吗？"        │
                         └─────────────┬─────────────┘
                                       ▼
                         ┌───────────────────────────┐
                         │  📊 第1层 · 数据采集 ✅    │
                         │  行情+K线+新闻 (已有)      │
                         │  财务指标+估值比率 ✅     │
                         │  FinancialMetric ✅       │
                         └─────────────┬─────────────┘
                                       ▼
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ 🧑‍💼 第2层·分析师层  │   │                  │   │                  │
    │ 基本面(真实数据)✅│   │ 技术面  情绪面    │   │ 宏观面           │
    │ FinancialMetric   │   │                  │   │                  │
    │ 注入分析师prompt  │   │ key_findings    │   │ red_flags        │
    └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
             └───────────────────────┼──────────────────────┘
                                     ▼
              ┌─────────────────────────────────────────┐
              │ 🧠 第3层·策略师层 (7位大师人格)           │
              │ 巴菲特/格雷厄姆 ← ROE/自由现金流 ✅       │
              │ 林奇 ← PEG/营收增长 ✅                   │
              │ 芒格/达利欧/索罗斯/德鲁肯米勒             │
              │ 基于分析师报告综合判断 + D2 强制方向       │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ ⚔️ 第4层·辩论层 (D1 同侪审阅)             │
              │ 大师互相审阅分析：赞同 + 补充 + 异议        │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ 🧑‍⚖️ 第5层·评审层 (D3 独立评审+ D4 聚合)  │
              │ 独立裁判评分 + 权重建议 + 加权投票汇总      │
              └───────────────────┬─────────────────────┘
                                  ▼
            ┌─────────────────────┴───────────────────────┐
            ▼                                              ▼
  ┌─────────────────────┐                    ┌─────────────────────┐
  │ 🛡️ 第6层·风控层      │ ← M1 历史注入       │                     │
  │ 激进·保守·中性       │                    │ R1 三层风控辩论      │
  │ 交易纪律·PM裁决      │                    │ 止损/止盈/仓位/熔断  │
  └──────────┬──────────┘                    └──────────┬──────────┘
             └──────────────────┬──────────────────────┘
                                ▼
              ┌─────────────────────────────────────────┐
              │ 💰 第7层·交易员层 (T1)                    │
              │ 仓位计算 + 多步执行 + 预案规划             │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ 🎯 第8层·PM裁决                          │
              │ 综合全部上游产出 → TradeRecommendation    │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ 🔁 第9层·用户经验反馈闭环 🆕             │
              │ AI推荐 ↔ 用户操作 ↔ 实际盈亏 ↔ 学习      │
              │ ResultCallbackEngine 分发结果事件 ✅     │
              │ RetroBoard记录 → M2反思注入 → 改进决策   │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ 🧠 记忆层 (贯穿全链路)                    │
              │ MemoryStore(ABC) → JSON/SQLite/Chroma   │
              │ 历史决策注入 · 知识库RAG · Skill插件盘    │
              │ 用户行为存储 · 经验教训索引 🆕            │
              └─────────────────────────────────────────┘
```

## 技术亮点

### 🧠 多智能体架构（LangGraph）

| 组件 | 说明 | 状态 |
|:----|:-----|:----:|
| **MasterAgent** | 通用化编排器 + Skill 插件盘 + RAG 知识库 + 结构化输出 | ✅ 完整实现 |
| **辩论引擎** | LangGraph StateGraph 10 层完整链路 + DP 系列增强 | ✅ D1-D4+M1-M4+R1+T1+FD+DP 系列完成 |
| **分析师层** | 4 位专业分析师（基本面/技术面/情绪面/宏观面）+ 财务指标注入 + 灵感官反共识分析 | ✅ Phase 1 完成 |
| **风控模块** | 三层风控辩论（Aggressive/Conservative/Neutral）+ PM 裁决 + 交易纪律体系 | ✅ R1 就绪（26 tests） |
| **交易员层** | T1 交易员执行规划 — ExecutionStep/TradePlan + 仓位计算 + 预案规划 | ✅ T1 就绪（20 tests） |
| **7 位投资大师 + 灵感官** | 巴菲特/芒格/费雪/卡拉曼/利弗莫尔/索罗斯/西蒙斯，每人独立人格 + 投资哲学 + 第 5 位反共识分析师 🆕 | ✅ 就绪（含 DP-005 灵感官） |
| **信任度评分** | TrustTracker — 方向准确率/校准/偏差/趋势统计 + DP-004 发言排序/低信任跳过 | ✅ M3 + RC-002 + DP-004 就绪 |
| **动态权重** | `compute_weight_factor(metrics, sector=...)` 根据信任度和板块胜率动态调整聚合权重，D3 weight_suggestions 叠加 | ✅ M4 就绪（支持 sector） |
| **教育小智** | RAG 驱动的问答 Agent（30 篇知识库 + TF 向量语义检索） | ✅ 就绪 |
| **M2 反思闭环** | AI推荐 ↔ 实际走势对比反思，自动生成经验教训存储入库，并触发实际结果回调 | ✅ 反思入口已接 RC-002 |
| **结果回调引擎 RC-001/002** 🆕 | ResultCallbackEngine 统一分发结果事件；M3-EXT 回调可把实际结果写入 TrustTracker | ✅ 核心分发器 + 信任度回调 + 反思 dispatch 完成 |
| **用户经验反馈闭环** 🆕 | 记录用户操作 vs AI推荐 → 实际盈亏 → 经验教训 → 改进未来决策 | 🟡 交易复盘看板完成，用户行为接入中 |
| **记忆存储系统** | MemoryStore(ABC) + JsonFileStore + MemoryManager 语义化接口 + 用户行为存储 🆕 | ✅ MVP |
| **数据采集层** | akshare 封装：实时行情 / K 线 / 新闻 / 板块 / 全部 A 股 + 财务指标(17列)+估值比率(PE/PB/PS)+API端点+前端Tab ✅ | ✅ 就绪 |
| **情绪数据层（C2）** | 市场涨跌比 + 情绪评分，提供市场整体情绪信号 | ✅ 已接入真实数据 |
| **数据新鲜度标注** | KLine/StockQuote 采集时间戳 + 前端 DataFreshnessTag（"刚刚/N秒前/N分钟前"） | ✅ TD-041 已修复 |
| **交易复盘看板** | RetroBoard 记录 AI推荐 → 用户操作 → 实际盈亏 → 准确率统计，全栈实现 | ✅ R4 极简版完成（27 tests） |
| **AI 输出置信度量化** | 校准曲线映射 + aggregate_node 校准 + 前端置信度可视化 | ✅ R4 完成 |
| **基本面深度（FD）** ✅ | 财报纵深 + 产业链定位 + 供应链调研 — 机构级基本面分析能力 | ✅ FD-001 全链路完成（数据层+辩论注入+API+前端Tab） |
| **多源证据完整性** | 六态来源结果 + 独立上游计数 + K 线逐源准确响应证明 + 不可变 `as_of` 回放 + LLM 前失败关闭 | 🟡 K 线 KR-1B 已完成数据部审计旁路；KR-2 复权、统一信封及 AI/API 切换待完成 |

> FD 基本面深度轨道基于 2026-06-23 调研结论：散户 vs 机构的核心壁垒在于财报纵深和供应链数据，而非分析模型。
> 完整调研报告见 [FUNDAMENTAL_RESEARCH.md](docs/02-requirements/FUNDAMENTAL_RESEARCH.md)。

### 🏗️ 工程架构（12 部门体系）

```
├── agents/          Agent 定义（Base → Master → 7位大师 → 教育小智）    ← 🤖 AI Agent 架构部
├── debate/          辩论编排器（D1-D4+M1-M4+R1+T1+FD+DP🆕 全模块） ← 🎯 辩论引擎部
├── data/            数据采集（行情/K线/新闻/公告 + 多源证据契约）      ← 🗄️ 数据管道部
├── memory/          记忆系统（RAG 知识库 + MemoryStore）                 ← 🧠 记忆系统部
├── callback/        结果回调引擎（事件分发 + 冷却 + 自动禁用 + 审计）   ← 🧠 记忆系统部
├── core/            通信协议（AgentMessage + EvidenceItem）              ← 🤖 AI Agent 架构部
├── utils/           LLM 封装 · 配置 · 费用追踪                          ← ⚙️ 基础设施部
├── risk/            风控模块（R1 三层风控辩论 + PM裁决）                 ← 🛡️ 风控管理部
├── trader/          交易员层（T1 执行规划 — TradePlan）                  ← 💹 交易执行部
├── backtest/        回测引擎（骨架 + TradePlan→TradeRecord）             ← 🔬 回测研究部
├── backend/         FastAPI 桥接层（行情/K线/新闻/财务/估值/产业链/复盘 ← 🌐 后端 API 部
├── frontend/        React + Next.js 前端（5 Tab含财务分析✅）          ← 🎨 前端部
├── .github/ + tests/  CI 流水线 + 测试架构 + 契约测试                    ← 🔄 质量保障部
└── docs/             部门体系 · 模块规格 · 设计决策 · 工作日志            ← 📋 全部门共享
```

> 每个代码目录对应一个"部门"（`docs/06-departments/{id}/`），
> 进入该目录 AI 自动加载对应角色身份和专业标准。

### 🧪 工程质量

- **1482 项测试已收集** — 本地非慢测 1459 通过、4 跳过、19 个慢测排除；含 K 线逐源覆盖/审计回放、新闻双源聚合与 backend 路由测试
- **CI/CD 全自动** — GitHub Actions 流水线（Ruff 风格检查 + Pyright 类型检查 + Pytest 测试）
- **类型安全** — 全项目完整类型注解，Pyright basic mode 零错误
- **结果回调审计** — `CallbackRecord` 记录每次结果事件响应，坏回调自动熔断不拖垮主流程
- **30+ 知识库文章** — 从《聪明的投资者》到《原则》，构建投资大师知识体系
- **9 份架构决策记录（ADR）** — 每条技术选型均有理由、权衡和替代方案

### 📋 关键设计决策一览

| 决策 | 选择 | 理由 |
|:----|:-----|:-----|
| 模型路由 | ADR-001 | Pydantic `BaseModel` 作为跨模块契约 |
| Agent 编排 | ADR-002 | LangGraph `StateGraph` 替代 SequentialChain |
| 数据源 | ADR-003 | akshare 覆盖 6+ 类 A 股数据 |
| 前端框架 | ADR-004 | Next.js 16 全栈框架（原 Streamlit MVP 已迁出） |
| 辩论策略 | ADR-005 | 多元大师并行 + 加权投票聚合 |

## 快速开始

```bash
# 克隆
git clone https://github.com/NoahLightryyy/litchi-head.git
cd litchi-head

# 创建虚拟环境
conda create -n litchi python=3.12
conda activate litchi

# 安装（含开发依赖）
pip install -e ".[dev]"

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
# 可选：将 LITCHI_KLINE_AUDIT_ROOT 设为绝对路径，迁移 K 线审计快照目录

# 运行全部测试
python scripts/check.py          # 智能检测变更范围，按需跑测试（推荐）
python scripts/check.py --full   # 强制全量子集
make check                       # Linux/macOS 同 --full
```

> 只需要 **DeepSeek API Key**（[平台申请](https://platform.deepseek.com/)），每月免费额度足够个人使用。

## 项目状态

```
Phase 0 ──── 基建期 ████████████████████░  95% ✅
  │  基础设施 · LLM 封装 · 通信协议 · Agent 基类 · CI/CD · ADR 体系

Phase 1 ──── MVP 链路 █████████████████████  100% ✅
  │  data/ ✅  debate/ ✅（D1-D4+M1-M4+R1+T1 十模块，含FD财务注入）
  │  memory/ ✅  callback/ ✅  risk/ ✅  trader/ ✅  backtest/ ✅ 待完成：业务回调接入 🆕

Phase 2 ──── 增强辩论与风控 ██████████░░░░░░░░░░░░  40% 🟡
  │  M2 交易后反思 ✅ · M3 信任度评分 ✅ · M4 动态权重 ✅ · C1 简报分区 ✅

Phase R ──── 实盘加固 █████████████████████████░░  88% 🟡 ← 当前阶段
  │  多源契约 ✅ · 多源真实接入/失败关闭 🟡 · 密钥安全 ✅ · API 限流 ✅ · 三层测试策略 ✅
  │  C2 情绪数据层 ✅ · R4 置信度量化 ✅ · 交易复盘看板 ✅ · TD-041 数据新鲜度 ✅

Phase R+1 ──── 设计哲学落地 ████████████████████████  100% ✅
  │  DP-001 模型瘦身 ✅ · DP-002 三段式互评 ✅ · DP-003 偏斜公示 ✅
  │  DP-004 旋钮扩展 ✅ · DP-005 灵感官 ✅ · DP-006 镜子反思 ✅ · DP-007 信息隔离 ✅

FD ──── 基本面深度 ✅ █████████░░░░░░░░░░░░░░░░░░░  30% 🟢 ← 数据层+API+前端已完成
  │  机构级基本面分析：财报纵深(FD-001全链路✅) · 产业链定位(FD-003 调研中) · 供应链图谱(FD-004 调研中)

Phase 3 ──── 实盘与个人化 ░░░░░░░░░░░░░░░░░░░░░   0% ⬜
  │  Broker 接入 · 回测验证 · 个人决策日志
```

## 为什么值得关注

### 学术价值

| 维度 | 内容 |
|:----|:------|
| 🎯 **多 Agent 协同** | LangGraph StateGraph 生产级实践，解决 Agent 间状态共享与并行调度 |
| 🧠 **RAG 知识检索** | TF 向量 + n-gram 语义检索混合方案，不依赖外部向量数据库 |
| 🛡️ **结构化输出** | Pydantic 驱动的 Agent 输出规范化，保证下游消费的类型安全 |
| 📊 **多源数据分析** | 统一来源身份与六态结果；按真实上游计数，证据不足时计划在 LLM 前失败关闭 |

### 工程素养

- 📐 **9 份架构决策记录** — 每步选型有理由有权衡，不是"跟着教程写"
- 🧪 **1482 项测试已收集** — 1459 通过、4 跳过、19 个慢测按本地闸门排除；含 K 线审计、真实 LLM、新闻双源证据契约和全链路测试
- 📝 **完整的文档体系** — 设计文档/流程规范/工作日志，代码即文档
- 🔄 **CI/CD 全自动流水线** — GitHub Actions 一键 lint + type + test
- 🔁 **结果驱动闭环地基** — RC-001/002 让“实际走势出来了”可以统一触发大师信任度校准

## 技术栈

| 领域 | 选型 |
|:----|:------|
| **核心语言** | Python 3.12+ |
| **AI 编排** | LangGraph (StateGraph) |
| **LLM** | DeepSeek-Chat（默认）+ DeepSeek-Reasoner（复杂任务，单 Provider 策略） |
| **数据访问** | Pydantic (v2) + akshare |
| **检索** | 自研 RAG（n-gram TF + 语义向量） |
| **测试** | pytest + VCR.py（真实 LLM 请求录制回放） |
| **CI** | GitHub Actions (Ruff + Pyright + pytest) |
| **文档** | ADR + 技术债务管理 + 自动化工作流 |

## 文档索引

- 🏛️ [设计哲学](docs/00-overview/DESIGN_PHILOSOPHY.md) — 虚拟小投行 · 三权分立 · 竞品差异化
- [项目总览](docs/00-overview/OVERVIEW.md) — 定位、架构、快照
- [全局看板](docs/00-overview/ROADMAP.md) — Phase 0-4 进度
- [技术栈](docs/00-overview/TECH_STACK.md) — 选型理由与权衡
- [🏢 部门体系](docs/06-departments/README.md) — 12 部门组织架构 + 数据流 + 协作规程
- [架构决策记录](docs/05-decisions/README.md) — 9 条 ADR
- [AI 工作流程](docs/01-guides/WORKFLOW.md) — 开发流程规范（含部门角色加载机制）
- [环境配置](docs/01-guides/ENVIRONMENT.md) — 快速开始
- [模块规格（辩论引擎）](docs/03-modules/02-debate-engine/SPEC.md) — 完整模块设计
- [🔬 基本面深度调研报告](docs/02-requirements/FUNDAMENTAL_RESEARCH.md) — 机构级财报/供应链分析可行性（2026-06-23 新增）
- [🎓 结果回调引擎学习卡片](docs/learning/23-result-callback-engine.md) — RC-001 如何让结果自动触发系统学习
- [🎓 按场景校准信任度](docs/learning/24-contextual-trust-calibration.md) — RC-002 为什么要按板块评估大师胜率
- [🎓 财务指标数据模型](docs/learning/25-financial-indicator-model.md) — FinancialMetrics 17 指标设计模式
- [🎓 估值比率模型](docs/learning/26-valuation-metrics-model.md) — PE/PB/PS 估值模型设计
- [🎓 PD 动态指标体系](docs/learning/27-pd-dynamic-indicators.md) — 产业链位置感知的指标注册表

---

<p align="center">
  <sub>Built with ❤️ and LangGraph · Licensed under MIT</sub>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/荔枝头-Litchi%20Head-FF6B35?style=for-the-badge">
    <img alt="Litchi Head" src="https://img.shields.io/badge/荔枝头-Litchi%20Head-FF6B35?style=for-the-badge">
  </picture>
</p>

<p align="center">
  <em>多智能体投资决策平台 — 让每个投资者拥有自己的 AI 投研团队</em>
</p>

<p align="center">
  <a href="https://github.com/NoahLightryyy/litchi-head/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/NoahLightryyy/litchi-head/ci.yml?branch=main&label=CI&logo=github" alt="CI Status">
  </a>
  <img src="https://img.shields.io/badge/tests-945%20passed-2ea44f?logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-brightgreen" alt="Coverage">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/type_check-pyright-brightgreen" alt="Pyright">
  <img src="https://img.shields.io/badge/architecture%20decisions-11%20ADRs-informational" alt="ADRs">
</p>

---

## 项目动机

> 机构投资者拥有 10 个 CFA + Bloomberg Terminal + 自研量化系统。
> 散户呢？只有手机上的炒股 APP 和满屏的"老师推荐"。
>
> 这个鸿沟不应该是技术造成的。

**Litchi Head** 的目标是：散户问一句话 → 15 秒内拿到结构化的多维投资决策信息，10 秒内能看懂、能决策、能行动。

## 核心架构

> 哲学：「体系 > 天才」— 信息垂直递进，每层产出是下层输入

```
                         ┌───────────────────────────┐
                         │     💬 用户一句话输入       │
                         │   "蔚来被低估了吗？"        │
                         └─────────────┬─────────────┘
                                       ▼
                         ┌───────────────────────────┐
                         │  📊 第1层 · 数据采集        │
                         │  akshare 6类行情 + 缓存    │
                         └─────────────┬─────────────┘
                                       ▼
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ 🧑‍💼 第2层·分析师层  │   │                  │   │                  │
    │ 基本面  技术面    │   │ 情绪面  宏观面    │   │ (4位专业分析师)    │
    │ AnalystReport    │   │ key_findings    │   │ red_flags        │
    └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
             └───────────────────────┼──────────────────────┘
                                     ▼
              ┌─────────────────────────────────────────┐
              │ 🧠 第3层·策略师层 (5位大师人格)            │
              │ 巴菲特/芒格/费雪/卡拉曼 → 价值              │
              │ 利弗莫尔/索罗斯          → 投机             │
              │ 西蒙斯/詹姆斯            → 量化             │
              │ 基于分析师报告综合判断 + D2 强制方向          │
              └───────────────────┬─────────────────────┘
                                  ▼
              ┌─────────────────────────────────────────┐
              │ ⚔️ 第4层·辩论层 (D1 交叉审阅+反驳)        │
              │ 大师互相审查分析结论、反驳逻辑漏洞          │
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
              │ 🧠 记忆层 (贯穿全链路)                    │
              │ MemoryStore(ABC) → JSON/SQLite/Chroma   │
              │ 历史决策注入 · 知识库RAG · Skill插件盘    │
              └─────────────────────────────────────────┘
```

## 技术亮点

### 🧠 多智能体架构（LangGraph）

| 组件 | 说明 | 状态 |
|:----|:-----|:----:|
| **MasterAgent** | 通用化编排器 + Skill 插件盘 + RAG 知识库 + 结构化输出 | ✅ 完整实现 |
| **辩论引擎** | LangGraph StateGraph 9 层完整链路：分析师 → 策略师 → 辩论 → 评审 → 风控 → 交易员 → PM 裁决 + M2 反思闭环 | ✅ D1-D4+M1+M2+M3+M4+R1+T1 完成 |
| **分析师层** | 4 位专业分析师（基本面/技术面/情绪面/宏观面）+ AnalystReport 结构化输出 | ✅ Phase 1 完成 |
| **风控模块** | 三层风控辩论（Aggressive/Conservative/Neutral）+ PM 裁决 + 交易纪律体系 | ✅ R1 就绪（26 tests） |
| **交易员层** | T1 交易员执行规划 — ExecutionStep/TradePlan + 仓位计算 + 预案规划 | ✅ T1 就绪（20 tests） |
| **7 位投资大师** | 巴菲特/芒格/费雪/卡拉曼/利弗莫尔/索罗斯/西蒙斯，每人独立人格 + 投资哲学 | ✅ 就绪 |
| **信任度评分** | TrustTracker — 方向准确率/校准/偏差/趋势统计，评分 Agent 输出可靠性 | ✅ M3 就绪（54 tests） |
| **动态权重** | `compute_weight_factor()` 根据信任度动态调整聚合权重，D3 weight_suggestions 叠加 | ✅ M4 就绪（10 tests） |
| **教育小智** | RAG 驱动的问答 Agent（30 篇知识库 + TF 向量语义检索） | ✅ 就绪 |
| **记忆存储系统** | MemoryStore(ABC) + JsonFileStore + MemoryManager 语义化接口 | ✅ MVP |
| **数据采集层** | akshare 封装：实时行情 / K 线 / 新闻 / 板块 / 基本面 / 全部 A 股 + C1 结构化4层简报输出 | ✅ 就绪 |

### 🏗️ 工程架构（10 部门体系）

```
├── agents/          Agent 定义（Base → Master → 7位大师 → 教育小智）    ← 🤖 AI Agent 架构部
├── debate/          辩论编排器（D1-D4+M1-M4+R1+T1 九模块）              ← 🎯 辩论引擎部
├── data/            数据采集（缓存层 + 6 类数据 + Pydantic 模型）        ← 🗄️ 数据管道部
├── memory/          记忆系统（RAG 知识库 + MemoryStore）                 ← 🧠 记忆系统部
├── core/            通信协议（AgentMessage + EvidenceItem）              ← 🤖 AI Agent 架构部
├── utils/           LLM 封装 · 配置 · 费用追踪                          ← ⚙️ 基础设施部
├── risk/            风控模块（R1 三层风控辩论 + PM裁决）                 ← 🛡️ 风控管理部
├── trader/          交易员层（T1 执行规划 — TradePlan）                  ← 💹 交易执行部
├── backtest/        回测引擎（骨架 + TradePlan→TradeRecord）             ← 🔬 回测研究部
├── backend/         FastAPI 桥接层（4 组路由）                          ← 🌐 后端 API 部
└── frontend/        React + Next.js 前端                                ← 🎨 前端部
```

> 每个代码目录对应一个"部门"（`docs/06-departments/{id}/`），
> 进入该目录 AI 自动加载对应角色身份和专业标准。

### 🧪 工程质量

- **945 测试全绿** — 单元测试 + 模块测试 + 辩论全流程（9层链路） + 回测桥接 + 真实 LLM 集成测试
- **CI/CD 全自动** — GitHub Actions 流水线（Ruff 风格检查 + Pyright 类型检查 + Pytest 测试）
- **类型安全** — 全项目完整类型注解，Pyright basic mode 零错误
- **30+ 知识库文章** — 从《聪明的投资者》到《原则》，构建投资大师知识体系
- **11 份架构决策记录（ADR）** — 每条技术选型均有理由、权衡和替代方案

### 📋 关键设计决策一览

| 决策 | 选择 | 理由 |
|:----|:-----|:-----|
| 模型路由 | ADR-001 | Pydantic `BaseModel` 作为跨模块契约 |
| Agent 编排 | ADR-002 | LangGraph `StateGraph` 替代 SequentialChain |
| 数据源 | ADR-003 | akshare 覆盖 6+ 类 A 股数据 |
| 前端框架 | ADR-004 | Streamlit 快速 MVP |
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

# 运行全部测试
make check        # lint + type + test 一键完成
```

> 需要 **DeepSeek API Key**（[平台申请](https://platform.deepseek.com/)），每月免费额度足够开发和测试。

## 项目状态

```
Phase 0 ──── 基建期 ████████████████████░  95% ✅
  │  基础设施 · LLM 封装 · 通信协议 · Agent 基类 · CI/CD · ADR 体系

Phase 1 ──── MVP 链路 ████████████████████░  90% 🟢
  │  data/ ✅  debate/ ✅（D1-D4+M1-M4+R1+T1 九模块，9层链路 + TrustTracker）
  │  memory/ ✅  risk/ ✅  trader/ ✅  backtest/ ✅ 待完成：前端

Phase 2 ──── 增强辩论与风控 ██████████░░░░░░░░░░░░  40% 🟡
  │  M2 交易后反思 ✅ · M3 信任度评分 ✅ · M4 动态权重 ✅ · C1 简报分区 ✅ · 端到端链路验证

Phase 3 ──── 实盘与生态 ░░░░░░░░░░░░░░░░░░░░░   0% ⬜
  │  Broker 接入 · 社区市场 · 策略广场

Phase 4 ──── 全球化 ░░░░░░░░░░░░░░░░░░░░   0% ⬜
```

## 为什么值得关注

### 学术价值

| 维度 | 内容 |
|:----|:------|
| 🎯 **多 Agent 协同** | LangGraph StateGraph 生产级实践，解决 Agent 间状态共享与并行调度 |
| 🧠 **RAG 知识检索** | TF 向量 + n-gram 语义检索混合方案，不依赖外部向量数据库 |
| 🛡️ **结构化输出** | Pydantic 驱动的 Agent 输出规范化，保证下游消费的类型安全 |
| 📊 **多源数据分析** | akshare 实时 + 缓存双轨，应对 A 股市场数据特点 |

### 工程素养

- 📐 **11 份架构决策记录** — 每步选型有理由有权衡，不是"跟着教程写"
- 🧪 **717 测试** — 含真实 LLM 集成测试 + 9 层完整链路，不是 mock 到死
- 📝 **完整的文档体系** — 设计文档/流程规范/工作日志，代码即文档
- 🔄 **CI/CD 全自动流水线** — GitHub Actions 一键 lint + type + test

## 技术栈

| 领域 | 选型 |
|:----|:------|
| **核心语言** | Python 3.12+ |
| **AI 编排** | LangGraph (StateGraph) |
| **LLM** | DeepSeek-Chat（主力）+ OpenAI / Claude（fallback） |
| **数据访问** | Pydantic (v2) + akshare |
| **检索** | 自研 RAG（n-gram TF + 语义向量） |
| **测试** | pytest + VCR.py（真实 LLM 请求录制回放） |
| **CI** | GitHub Actions (Ruff + Pyright + pytest) |
| **文档** | ADR + 技术债务管理 + 自动化工作流 |

## 文档索引

- [项目总览](docs/00-overview/OVERVIEW.md) — 定位、架构、快照
- [全局看板](docs/00-overview/ROADMAP.md) — Phase 0-4 进度
- [技术栈](docs/00-overview/TECH_STACK.md) — 选型理由与权衡
- [🏢 部门体系](docs/06-departments/README.md) — 10 部门组织架构 + 数据流 + 协作规程
- [架构决策记录](docs/05-decisions/README.md) — 11 条 ADR
- [AI 工作流程](docs/01-guides/WORKFLOW.md) — 开发流程规范（含部门角色加载机制）
- [环境配置](docs/01-guides/ENVIRONMENT.md) — 快速开始
- [模块规格（辩论引擎）](docs/03-modules/02-debate-engine/SPEC.md) — 完整模块设计

---

<p align="center">
  <sub>Built with ❤️ and LangGraph · Licensed under MIT</sub>
</p>

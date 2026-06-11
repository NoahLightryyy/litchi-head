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
  <img src="https://img.shields.io/badge/tests-331%20passed-2ea44f?logo=pytest" alt="Tests">
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

```
                     ┌──────────────────────────────────┐
                     │         Master Orchestrator        │
                     │        (LangGraph StateGraph)      │
                     └──────┬──────┬──────┬──────┬───────┘
                            │      │      │      │
              ┌─────────────┘      │      │      └─────────────┐
              ▼                    ▼      ▼                    ▼
      ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
      │  价值投资派    │    │  技术分析派   │    │  量化策略派  ···  │
      │巴菲特/芒格    │    │ 利弗莫尔/    │    │  西蒙斯/          │
      │费雪/卡拉曼   │    │ 索罗斯       │    │  詹姆斯          │
      └──────┬───────┘    └──────┬───────┘    └────────┬─────────┘
             │                  │                     │
             └──────────────────┼─────────────────────┘
                                ▼
                     ┌──────────────────┐
                     │   辩论聚合层      │
                     │  加权投票 + 证据  │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │   决策卡输出      │
                     │  Pydantic 结构化  │
                     └────────┬─────────┘
                              ▼
                     ┌──────────────────┐
                     │  记忆存储系统     │
                     │  MemoryStore ABC │
                     │  可插拔后端      │
                     │  (JSON/SQLite/   │
                     │   Chroma)        │
                     └──────────────────┘

     ┌─────────────────────────────────────────────┐
     │              数据层 (akshare)                │
     │  实时行情 · K线 · 新闻 · 板块 · 基本面       │
     └─────────────────────────────────────────────┘
```

## 技术亮点

### 🧠 多智能体架构（LangGraph）

| 组件 | 说明 | 状态 |
|:----|:-----|:----:|
| **MasterAgent** | 通用化编排器 + Skill 插件盘 + RAG 知识库 + 结构化输出 | ✅ 完整实现 |
| **辩论引擎** | LangGraph StateGraph 三节点：数据收集 → 多大师分析 → 投票聚合 | ✅ MVP |
| **7 位投资大师** | 巴菲特/芒格/费雪/卡拉曼/利弗莫尔/索罗斯/西蒙斯，每人独立人格 + 投资哲学 | ✅ 就绪 |
| **教育小智** | RAG 驱动的问答 Agent（30 篇知识库 + TF 向量语义检索） | ✅ 就绪 |
| **记忆存储系统** | MemoryStore(ABC) + JsonFileStore + MemoryManager 语义化接口 | ✅ MVP |
| **数据采集层** | akshare 封装：实时行情 / K 线 / 新闻 / 板块 / 基本面 / 全部 A 股 | ✅ 就绪 |

### 🏗️ 工程架构

```
├── agents/          Agent 定义（Base → Master → 7位大师 → 小智）
├── debate/          辩论编排器（模型层 + LangGraph 编排）
├── data/            数据采集（缓存层 + 6 类数据 + Pydantic 模型）
├── memory/          记忆系统（RAG 知识库 + Skill 插件盘 + MemoryStore + MemoryManager）
├── core/            通信协议（AgentMessage + EvidenceItem）
├── utils/           LLM 封装 · 配置 · 费用追踪 · 日志
├── backtest/        回测引擎（骨架）
└── risk/            风控模块（骨架）
```

### 🧪 工程质量

- **331 测试全绿** — 单元测试 + 模块测试 + 真实 LLM 集成测试
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

Phase 1 ──── MVP 链路 ████████████████░░░░  55% 🟡
  │  data/ ✅  debate/ ✅  memory/ ✅  待完成：端到端接驳 · Agent 接入记忆 · 前端

Phase 2 ──── 增强辩论 ░░░░░░░░░░░░░░░░░░░░   0% ⬜
  │  组间辩论 · 记忆反思 · 多引擎回测

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
- 🧪 **331 测试** — 含真实 LLM 集成测试，不是 mock 到死
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

- [架构决策记录](docs/技术债务与架构决策/架构决策记录.md) — 10 条关键决策与权衡
- [技术设计方案](docs/架构设计/技术实现方案-AI驱动版.md) — 完整架构设计
- [竞品调研报告](docs/调研分析/调研报告-多智能体投资决策平台竞品分析.md) — 市场定位分析
- [AI 自动化工作流程](docs/流程规范/AI自动化工作流程.md) — 开发流程规范
- [项目通俗介绍](docs/项目介绍/项目介绍-通俗版.md) — 给非技术读者的介绍

---

<p align="center">
  <sub>Built with ❤️ and LangGraph · Licensed under MIT</sub>
</p>

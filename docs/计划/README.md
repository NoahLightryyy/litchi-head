# 📋 项目进度看板

> 一站式总览：已完成 ✓ 进行中 ⟳ 待办 ⬜
> **目标**：进来看一眼，就知道项目到哪了、下一步做什么。

---

## 快速统计

```
总测试数   │ 302  passed（历史新高 ✅）
技术债务   │ 17 条总记 / 10 条已关闭 / 7 条开放
紧急指数   │ 0.6/10（持续下降，所有高风险债务已修复）
当前阶段   │ Phase 1 MVP 期（data/ + debate/ 已上线）
```

---

## 🟢 已完成（20 项）

### 核心基建
- ✅ **LLM 调用封装层** — `src/utils/llm.py`（TD-001 🔧 核心实现完成，测试待补）
- ✅ **LLMConfig 参数配置** — `LLMConfig` 数据类，temperature/max_tokens 可按 Agent 覆盖（TD-012 ✅ 已关闭）
- ✅ **通信协议** — `AgentMessage` + `EvidenceItem` + `MessageRouter`（20 tests）
- ✅ **配置加载** — Pydantic Settings（`src/utils/config.py`）
- ✅ **结构化日志** — `src/utils/logger.py`
- ✅ **费用追踪** — `src/utils/cost_tracker.py`（15 tests）
- ✅ **`ensure_dirs()` 目录创建函数已定义**（但未被调用 → TD-007）

### Agent 系统
- ✅ **BaseAgent 基类** + `AgentResult[Generic[T]]` 泛型化（TD-002 ✅ 已关闭）
- ✅ **AgentContext 辩论槽位** — 新增 `peer_outputs`/`current_round`/`target_audience`（TD-014 ✅ 已关闭）
- ✅ **教育小智 Agent** — RAG + LLM 问答（15 tests）
- ✅ **MasterAgent 通用化** — Skill 插件盘 + KB + LLM（24 tests ✅，含真实 DeepSeek API 集成测试）

### 知识 & 记忆
- ✅ **KnowledgeBase RAG** — n-gram TF 向量语义检索（15 tests）
- ✅ **知识库文件** — 30 篇（concepts 8 / indicators 7 / fundamentals 7 / masters 3 / strategies 5）
- ✅ **Master Skill 插件盘** — 7 位投资大师人格定义（30 tests）
- ✅ **知识检索双轨方案** — RAG + GREP 设计已定

### 基建 & 质量
- ✅ **CI 流水线** — GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13，TD-009 ✅ 已关闭）
- ✅ **Pyright 路径修复** — 移除硬编码 extraPaths（TD-011 ✅ 已关闭）
- ✅ **测试基座** — `conftest.py` + mock 工具 + VCR 录制（TD-004 🔧 核心完成）
- ✅ **全量测试 222 通过**
- ✅ **LangGraph 原型验证** — `tests/test_langgraph_prototype.py`（20 测试，TD-016 ✅ 已关闭）

### 设计文档
- ✅ **ADR 体系** — 10 条架构决策记录（001-010）
- ✅ **用户行为镜子 Agent 设计** — `docs/架构设计/用户行为镜子Agent设计构想.md`
- ✅ **前端 MVP 需求** — `docs/产品需求/前端MVP需求文档-基于市场对标.md`
- ✅ **产品初版要求** — `docs/产品需求/初版要求.md`

### Phase 1 核心模块
- ✅ **数据采集层** `src/data/` — DataCollector + Cache + 5 个 Pydantic 模型（43 测试）
- ✅ **辩论编排器 MVP** `src/debate/` — LangGraph StateGraph 驱动（三节点：collect_data→master_round→aggregate，28 测试）
- ✅ **data → debate 链路可行性验证** — 编排器 MVP 全链路跑通，300 passed
- ✅ **data → debate 接驳** — format_market_brief 市场简报 + 行情过滤 + 结构化下传

### 项目治理
- ✅ **远程仓库迁移** — Gitee → GitHub，保留 Gitee 为备份远程
- ✅ **AI 自动化工作流程** — `docs/流程规范/AI自动化工作流程.md`
- ✅ **AI 会话交接文档** — 当前文档
- ✅ **技术债务管理系统** — 含分类 / 生命周期 / 仪表盘
- ✅ **工作日志索引** — `docs/ai-work-logs/README.md`
- ✅ **子 Agent 灵算路由永久化** — Windows 用户 env + .bashrc 对齐，阻塞清零

---

## ⬜ 待办

### Phase 0 收尾（优先）

| 优先级 | 事项 | 预估 | 前置 |
|:------:|:-----|:----:|:----:|
| 🥇 | **LangGraph 最小原型验证**（TD-016） | ✅ 已完成 | 20 测试 + 222 全量通过 |
| 🥇 | **TD-013 Streaming 接口** — `astream() → AsyncIterator[str]` | ✅ 已完成 | 228 全量通过 |
| 🥇 | **TD-015 缓存策略解耦** — 不同 LLMConfig 独立缓存 | ✅ 已完成（与 TD-012 同步） | 5 测试验证 |
| 🥈 | **MasterAgent 输出结构化** — 纯文本 → 结构化评级+证据+置信度 | ✅ 已完成 | 228 全量通过 |
| 🥈 | **Phase 0 收尾修复** — config.py deprecation、.env.example | ✅ 已完成 | — |
| 🥈 | **A-4 GREP FormulaIndex** — 公式精确检索 | ~1d | — |
| 🥉 | **4 个空模块补模块文档** — debate/data/backtest/risk | ✅ 已完成 | — |
| 🥉 | **债务清理** — TD-003/005/006/007/008（低优先级，各 10min~1h） | ~3h | — |

### 空架子模块（白色目录，需从零实现）

```
src/
├── backtest/       回测引擎     —— 策略回测
└── risk/           风控模块     —— VaR / 波动率 / 一票否决
```

### 辩论引擎增强（编排器 MVP ✅）

| 步骤 | 事项 | 前置 |
|:----:|:-----|:----:|
| 1️⃣ | **辩论编排器 LangGraph StateGraph** | ✅ 已完成（28 测试） |
| 2️⃣ | **辩论分组** — 4 组大师分组辩论逻辑 | 编排器 ✅ |
| 3️⃣ | **交叉质疑** — Agent 之间互相质疑机制 | 辩论基础 ✅ |
| 4️⃣ | **投票聚合** — 大师投票加权汇总 | 质疑机制就绪 |
| 5️⃣ | **data → debate 接驳** — format_market_brief + 行情过滤 + 结构化下传 | ✅ 已完成 |

### Phase 1 MVP

| 优先级 | 事项 | 依赖 | 预估 |
|:------:|:-----|:----|:----:|
| 🥇 | **data → debate 接驳** — format_market_brief + 行情过滤 + 结构化下传 | ✅ 已完成 | — |
| 🥇 | **端到端链路验证** — 用户问题 → MasterAgent → 多 Agent 辩论 → 决策卡输出 | data→debate 接驳 | ~2d |
| 🥇 | **前端 MVP（3 页面）** — 首页/分析页/我的页面（Streamlit） | 端到端链路就绪 | ~3d |
| 🥈 | **用户行为镜子 Agent** — 记录期（1-9 次决策）MVP | 辩论引擎就绪 | ~2d |
| 🥈 | **记忆系统 MVP** — 三层记忆 JSON 持久化 | — | ~2d |
| 🥈 | **回测模块基础** — 简单策略回测 | data 就绪 | ~2d |

### Phase 2+ 迭代

| 事项 | 说明 |
|:-----|:------|
| 镜子 Agent 对比期 | 10+ 次决策出对比报告 |
| 镜子 Agent 出师期 | 辩论席位的可选占位 |
| 风控模块 | VaR / 波动率计算 |
| 前端决策卡优化 | 可视化升级 |
| 英文 README | GitHub 国际化 |

---

## 📊 模块完成度气温图

```
src/
├── utils/        ████████████████████ 100%  ✅ 全部完工
│   ├── llm.py                          ✅ TD-013/015 已修复
│   ├── config.py                       ✅
│   ├── cost_tracker.py                 ✅
│   └── logger.py                       ✅
│
├── core/
│   └── protocol.py   ██████████████ 80%  ← TD-003/006 待修复
│
├── agents/          ████████████████ 85%
│   ├── base.py                         ✅（TD-014 已修复）
│   ├── xiao_zhi.py                     ✅
│   └── master_agent.py                 ✅ InvestmentAnalysis 结构化输出
│
├── memory/          ██████████████ 75%
│   ├── knowledge_base.py               ✅
│   └── skill_disk.py                   ✅
│
├── debate/          ████████████████████ 100%  ✅ 编排器 MVP 上线（28 测试）
├── data/            ████████████████████ 100%  ✅ 采集器 + 缓存 + 模型（43 测试）
├── backtest/        ░░░░░░░░░░ 0%      ← 待实现
└── risk/            ░░░░░░░░░░ 0%      ← 待实现
```

---

## 🔗 关联信息源

| 信息来源 | 位置 | 用途 |
|---------|------|------|
| 技术债务详情 | `docs/技术债务与架构决策/技术债务日志.md` | 每条 TD 的完整描述+利息分析 |
| 架构决策 | `docs/技术债务与架构决策/架构决策记录.md` | 10 条 ADR 全文 |
| 工作日志 | `docs/ai-work-logs/README.md` | 按日期回溯每会话工作内容 |
| 会话交接 | `docs/流程规范/AI会话交接文档.md` | 当前上下文、待修复缺陷 |
| 镜子 Agent | `docs/架构设计/用户行为镜子Agent设计构想.md` | 完整设计（9 章） |
| 前端 MVP | `docs/产品需求/前端MVP需求文档-基于市场对标.md` | 3 页线框图+数据契约 |
| 初版要求 | `docs/产品需求/初版要求.md` | 原始需求文档 |

---

## 📝 更新记录

| 日期 | 操作 |
|------|------|
| 2026-06-07 | 创建 — 聚合 AI 会话交接文档 §5 + 技术债务日志 + 路线图 memory 为一站式看板 |
| 2026-06-07 | TD-012 关闭 — LLMConfig 数据类 + 接口修改 + 17 测试，202 全量通过，紧急指数 1.2→0.9 |
| 2026-06-08 | TD-016 关闭 — LangGraph 原型验证通过，20 测试 + 222 全量通过，紧急指数 1.2→0.9 |
| 2026-06-08 | Phase 0 核心收尾 — TD-013/015/010 关闭 + MasterAgent 结构化输出，228 全量通过，紧急指数 0.9→0.7 |
| 2026-06-08 | Phase 1 数据采集层上线 — DataCollector + Cache + Models，43 测试，272 total |
| 2026-06-08 | 辩论编排器 MVP 上线 — LangGraph StateGraph + 28 测试，300 total |
| 2026-06-08 | 子 Agent 灵算路由永久化 — Windows User env + .bashrc 对齐，阻塞清零 |
| 2026-06-09 | data → debate 接驳实现 — format_market_brief + 行情过滤 + 结构化下传 |
| 2026-06-11 | 提交惰性导入 + 断言鲁棒性修复 — 工作日志/交接文档/看板同步 |

> **如何更新**：每次会话结束时，把"已完成"和"变更状态"同步到此文件。
> 保持 `🟢 → 🔵 → ⬜` 三段式清晰可见。

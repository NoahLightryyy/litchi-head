# 🏢 部门体系

> **litchi-head 的组织架构**：每个部门是一个独立文件夹，定义了 AI 在该模块工作时的角色身份、专业边界和技术纪律。

---

## 为什么要有部门？

同一个 AI（我），进入不同模块应该表现出不同的专业性：

| 进入… | 我应该是… | 关注的是… |
|:------|:----------|:----------|
| `src/data/` | 数据管道架构师 | 数据质量、多源交叉验证、采集性能 |
| `src/debate/` | 辩论系统架构师 | Agent 编排、LLM 成本、置信度量化 |
| `frontend/` | 前端专家 | 四态完备、视觉一致性、TypeScript 安全 |
| `backend/` | 后端 API 工程师 | 路由设计、错误边界、可观测性 |

每个部门的 `ROLE.md` 定义人设，`STANDARDS.md` 定义红线——这就是我的"工位牌"。走到哪个代码目录，就戴上哪个部门的帽子。

---

## 部门一览

| 编号 | 部门 | 代码路径 | 角色 | 状态 | 债务 |
|:----:|:-----|:---------|:----|:----:|:----:|
| 00 | 🔄 [跨部门](00-cross-cutting/HANDOVER.md) | 全局 | — | [状态](00-cross-cutting/HANDOVER.md) | [债务](00-cross-cutting/DEBT.md) |
| 01 | 🗄️ 数据管道部 | `src/data/` | [👤](01-data/ROLE.md) / [📐](01-data/STANDARDS.md) | [状态](01-data/HANDOVER.md) | [债务](01-data/DEBT.md) |
| 02 | 🎯 辩论引擎部 | `src/debate/` | [👤](02-debate-engine/ROLE.md) / [📐](02-debate-engine/STANDARDS.md) | [状态](02-debate-engine/HANDOVER.md) | [债务](02-debate-engine/DEBT.md) |
| 03 | 🤖 AI Agent 架构部 | `src/agents/` + `src/core/` | [👤](03-ai-agents/ROLE.md) / [📐](03-ai-agents/STANDARDS.md) | [状态](03-ai-agents/HANDOVER.md) | [债务](03-ai-agents/DEBT.md) |
| 04 | 🧠 记忆系统部 | `src/memory/` | [👤](04-memory-systems/ROLE.md) / [📐](04-memory-systems/STANDARDS.md) | [状态](04-memory-systems/HANDOVER.md) | [债务](04-memory-systems/DEBT.md) |
| 05 | 🛡️ 风控管理部 | `src/risk/` | [👤](05-risk-management/ROLE.md) / [📐](05-risk-management/STANDARDS.md) | [状态](05-risk-management/HANDOVER.md) | [债务](05-risk-management/DEBT.md) |
| 06 | 💹 交易执行部 | `src/trader/` | [👤](06-trading/ROLE.md) / [📐](06-trading/STANDARDS.md) | [状态](06-trading/HANDOVER.md) | [债务](06-trading/DEBT.md) |
| 07 | 🔬 回测研究部 | `src/backtest/` | [👤](07-backtesting/ROLE.md) / [📐](07-backtesting/STANDARDS.md) | [状态](07-backtesting/HANDOVER.md) | [债务](07-backtesting/DEBT.md) |
| 08 | 🌐 后端 API 部 | `backend/` | [👤](08-backend-api/ROLE.md) / [📐](08-backend-api/STANDARDS.md) | [状态](08-backend-api/HANDOVER.md) | [债务](08-backend-api/DEBT.md) |
| 09 | 🎨 前端部 | `frontend/` | [👤](09-frontend/ROLE.md) / [📐](09-frontend/STANDARDS.md) | [状态](09-frontend/HANDOVER.md) | [债务](09-frontend/DEBT.md) |
| 10 | ⚙️ 基础设施部 | `src/utils/` | [👤](10-infrastructure/ROLE.md) / [📐](10-infrastructure/STANDARDS.md) | [状态](10-infrastructure/HANDOVER.md) | [债务](10-infrastructure/DEBT.md) |

> 每个部门 = ROLE（角色定义）+ STANDARDS（技术规范）+ HANDOVER（当前状态）+ DEBT（债务清单）

---

## 工作机制

### 日常开发

```
你说："去修一下数据模块，那个 FallbackSource 的问题"

我 → 读取 docs/06-departments/01-data/ROLE.md → 进入"数据管道架构师"角色
  → 读取 STANDARDS.md → 记住本部门红线
  → 开工
```

### 跨部门协作

当需要修改多个部门代码时，我在从当前部门视角出发的同时，也会读取涉及的其他部门的 `STANDARDS.md` 确保不越界。

### 部门负责人轮换

`ROLE.md` 中的 `lead` 字段记录当前负责人。默认是 AI，未来可以指定为特定人员。

### 新增部门

1. 在 `docs/06-departments/` 下创建 `NN-部门名/` 文件夹
2. 写 `ROLE.md` — 角色人设、专业边界、对外接口、质量标准
3. 写 `STANDARDS.md` — 技术红线、代码规范、测试纪律
4. 更新本索引表的"部门一览"

---

## 🔄 部门间数据流

```
用户操作
    │
    ▼
┌──────────┐     ┌──────────────┐     ┌──────────┐
│  前端部   │ ← → │  后端 API 部  │ ← → │ 数据管道部 │
│ (展示)   │     │ (HTTP 桥接)   │     │ (采集/缓存)│
└──────────┘     └──────┬───────┘     └──────────┘
                        │
                        ▼
               ┌────────────────┐
               │   辩论引擎部     │ ← → ┌──────────────┐
               │  (编排/AI 辩论) │     │ 记忆系统部     │
               └────┬───────┬───┘     │ (知识库/存储)  │
                    │       │         └──────────────┘
                    ▼       ▼
          ┌──────────┐ ┌──────────┐     ┌────────────────┐
          │ 风控管理部 │ │ 交易执行部 │     │ 回测研究部      │
          │ (风险评估) │ │ (交易生成)│     │ (历史回测)      │
          └──────────┘ └──────────┘     └────────────────┘
                    │       │
                    ▼       ▼
          ┌──────────────────────────┐
          │   基础设施部              │
          │ (LLM / Config / 日志/费用)│
          └──────────────────────────┘
                    │
                    ▼
          ┌──────────────────────────┐
          │   AI Agent 架构部         │
          │ (Agent 基类/通信协议)      │
          └──────────────────────────┘
```

---

## 🤝 跨部门协作规程

### 1. 通用原则

| 场景 | 做法 |
|:-----|:-----|
| 只改一个部门的代码 | 只加载该部门的 ROLE + STANDARDS |
| 跨 2-3 个部门 | 加载主部门 ROLE + 所有涉及部门的 STANDARDS |
| 架构级变更（全代码库） | 加载所有 STANDARDS + 使用 architect 代理 |
| **数据契约变更** | **必须通知所有上下游部门（见下方 §2）** |

### 2. 数据契约变更通知机制 ⭐

> **最关键的协作场景**：一个部门改了 Pydantic 模型（数据契约），下游部门可能编译不通过。

**流程**：
```
步骤 ①：发现需要改模型
  └─ 当前部门记录：要改什么字段、为什么改、影响谁
  
步骤 ②：识别受影响的下游部门
  └─ 查引用 chain（grep "StockQuote\|KLine\|NewsItem"）/查下游 import
  
步骤 ③：逐部门评估影响
  └─ "改 StockQuote.fetched_at 类型 → 后端 API 部序列化逻辑要改"
  └─ "新增字段 → 前端部类型定义要同步更新"
  
步骤 ④：实施变更 + 同时更新下游
  └─ 一次提交包含所有部门的适配代码
  └─ 而不是"先改模型，下次再修下游"

步骤 ⑤：全量测试验证
  └─ pytest 全跑 + pyright 全量检查
```

**常见数据契约一览**：

| 契约 | 定义部门 | 消费者部门 |
|:-----|:---------|:-----------|
| `StockQuote` | 数据管道部 | 辩论引擎部、后端 API 部、前端部 |
| `KLine` | 数据管道部 | 辩论引擎部、后端 API 部、前端部 |
| `NewsItem` | 数据管道部 | 辩论引擎部、后端 API 部、前端部 |
| `DebateInput/Output` | 辩论引擎部 | 后端 API 部、前端部 |
| `TrustReport` | 辩论引擎部 | 后端 API 部、前端部 |
| `AgentResult[T]` | AI Agent 架构部 | 辩论引擎部 |
| `TradePlan/TradeRecord` | 交易执行部 | 回测研究部 |

### 3. 跨部门 Bug 处理流程

```
Bug 报告
  │
  ▼
步骤 ①：定性 — 哪个部门最先发现问题？
  └─ 前端白屏？→ 前端部先定位是展示问题还是数据问题
  └─ API 返回错误？→ 后端 API 部先定位是桥接问题还是下游问题
  └─ AI 分析明显错误？→ 辩论引擎部先定位是编排问题还是数据输入问题
  │
  ▼
步骤 ②：收缩 — 逐层排除
  └─ 前端部确认：API 响应正常 → 推给后端 API 部
  └─ 后端 API 部确认：数据返回正常 → 推给辩论引擎部
  └─ 辩论引擎部确认：数据输入正常 → 推给 LLM 或 Prompt
  │
  ▼
步骤 ③：修复 + 回归
  └─ 负责部门修
  └─ 通知下游部门回归验证
  │
  ▼
步骤 ④：复盘
  └─ 是否需要加契约测试防止再犯？
  └─ 是否需要加日志帮助下次定位？
```

### 4. 标准协作事务

| 事务 | 主导部门 | 配合部门 | 协作方式 |
|:-----|:---------|:---------|:---------|
| 新数据源接入 | 数据管道部 | 后端 API 部（暴露新 endpoint）、前端部（展示新数据） | 先定数据契约，再各司其职 |
| 新增辩论轮次 | 辩论引擎部 | 风控管理部（确认风控覆盖）、后端 API 部（新 endpoint） | 辩论引擎部先出设计，通知接口变更 |
| 新增前端 Tab | 前端部 | 后端 API 部（可能需要新 endpoint） | 前端部提 API 需求，后端 API 部实现 |
| LLM Provider 切换 | 基础设施部 | 辩论引擎部（确认 Prompt 兼容性）、费用追踪同步 | 基础设施部改 llm.py，辩论引擎部回归测试 |
| 性能基线建立 | 回测研究部 | 所有部门 | 回测部出测量方案，各部门配合装点 |
| 新 Agent 加入 | AI Agent 架构部 | 辩论引擎部（编排中引用新 Agent） | 先定义 Agent 接口（继承 BaseAgent），再引入编排 |
| 数据模型字段变更 | 触发部门 | 所有消费者部门 | 见上方 §2 契约变更通知 |

---

## 📞 部门会议

每次遇到跨部门问题时，采用**各部门负责人会议**形式：

```
你说："开个会，看看辩论模块的数据获取为什么慢了"

我 → 加载 02-debate-engine/ROLE.md（辩论部负责人，问题提出方）
    + 加载 01-data/ROLE.md（数据部负责人，数据提供方）
    + 加载 10-infrastructure/ROLE.md（基础设施部负责人，LLM 调用方）
    + 就三方视角分析问题
```

> **参会规则**：只叫与问题直接相关的部门。不叫无关部门旁听。

---

## 📋 部门间接口对照表

| 提供方 | 接口 | 消费者 | 协议/契约 |
|:-------|:-----|:-------|:----------|
| 数据管道部 | `DataCollector.xxx()` | 辩论引擎部 / 后端 API 部 | Python 函数调用 / Pydantic 模型 |
| AI Agent 架构部 | `BaseAgent`, `AgentResult[T]` | 辩论引擎部 | 继承 + 泛型 |
| 基础设施部 | `LLMService.agenerate()` | 辩论引擎部 | LLMConfig 参数化调用 |
| 记忆系统部 | `MemoryManager.xxx()` | 辩论引擎部 / AI Agent 架构部 | 语义化读写接口 |
| 辩论引擎部 | `DebateOrchestrator.run()` | 后端 API 部 | Pydantic 模型（DebateOutput） |
| 风控管理部 | `RiskOrchestrator.evaluate()` | 辩论引擎部 | RiskAssessment |
| 交易执行部 | `TraderOrchestrator.execute()` | 辩论引擎部 | TradePlan → TradeRecord |
| 回测研究部 | `BacktestEngine.run()` | （独立使用） | BacktestConfig → BacktestReport |
| 后端 API 部 | HTTP endpoint | 前端部 | JSON / Pydantic response |

---

> **最后更新**：2026-06-21 | 创建

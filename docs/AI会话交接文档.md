# 🔄 AI 会话交接文档

> 用途：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
> **新 AI 启动流程：** 阅读本文档 → 阅读 CLAUDE.md → 阅读 AI 自动化工作流程 → 阅读最新工作日志 → 继续工作。

---

## 1. 项目身份卡

| 字段 | 值 |
|------|-----|
| **项目名称** | litchi-head — 多智能体投资决策平台 |
| **当前阶段** | Phase 0 基建期（趋近完成，即将进入 Phase 1 MVP 期） |
| **技术栈** | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / FAISS |
| **代码位置** | `e:\litchi-head` |
| **远程仓库** | GitHub (`origin`)，Gitee (`gitee`) 作为备份 |
| **默认分支** | `main` |
| **CI** | GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13） |
| **最新提交** | `9717697` — test: 编写 62 个业务测试，86 tests 全部通过 |

---

## 2. 当前会话状态（2026-06-07）

### 本次已完成的工作

| 事项 | 详情 |
|------|------|
| ✅ **AgentResult 泛型化 + Pydantic 化** | `src/agents/base.py` — `@dataclass` → `BaseModel + Generic[T]`，向后兼容全部 88 个测试 |
| ✅ **新增 2 个 Generic 测试** | `tests/test_agents_base.py` — 验证类型化输出和序列化 |
| ✅ **关闭 TD-002** | AgentResult 缺泛型问题已解决 |
| ✅ **更新 ADR-008** | 新增 §2a 记录实际实现与设计差异 |
| ✅ **RAG + GREP 双轨知识检索方案** | `docs/金融知识检索架构-RAG+GREP双轨方案.md` 已写入 |
| ✅ **`get_tools()` 接口落地** | ADR-009 代码落地 — BaseAgent 添加空方法，19 tests 全部通过 |
| ✅ **KnowledgeBase 核心实现** | `src/memory/knowledge_base.py` — 基于 n-gram TF 向量的轻量语义检索，15 tests 全通过 |
| ✅ **首批 7 篇金融知识文件** | `data/knowledge_base/` — 概念(3) + 指标(2) + 基本面(2) |
| ✅ **知识库扩充策略文档** | `docs/金融知识检索架构-RAG+GREP双轨方案.md §10` — 四层方案（LLM 生成 → 公开数据集 → API → 社区） |
| ✅ **教育小智 Agent 开发中** | `tests/test_agents_xiao_zhi.py` 已写（RED），实现中 |
| ✅ **AI 工作日志** | `docs/ai-work-logs/2026-06-07.md` 已创建 |

### 当前 Git 状态

```
已修改：
  src/agents/base.py             — get_tools() 接口
  tests/test_agents_base.py      — get_tools() 测试（19 项）
  docs/技术债务与架构决策/技术债务日志.md
  docs/技术债务与架构决策/架构决策记录.md
  docs/ai-work-logs/README.md
  docs/金融知识检索架构-RAG+GREP双轨方案.md  — §10 扩充策略新增
  docs/AI会话交接文档.md               — 本文件

新文件（未跟踪）：
  docs/ai-work-logs/2026-06-07.md
  src/memory/knowledge_base.py          — KnowledgeBase 核心
  tests/test_memory_knowledge_base.py   — 15 个 KB 测试
  tests/test_agents_xiao_zhi.py         — XiaoZhiAgent 测试（写了一半）
  data/knowledge_base/concepts/         — 安全边际、复利、护城河
  data/knowledge_base/indicators/       — MACD、RSI
  data/knowledge_base/fundamentals/     — PE、ROE
```

> **注意：以上变更尚未提交 commit，新会话启动后先提交。**
> **当前阶段关键：XiaoZhiAgent 实现在进行中，Mock LLM 测试通过后还需做真实 LLM 集成测试。**

### 三同步检查（当前会话已通过）

| 检查项 | 状态 |
|--------|------|
| Ruff（代码风格） | ✅ 0 errors |
| Pyright（类型检查） | ✅ 0 errors（src/ 零错误） |
| Pytest（测试） | ✅ 34 passed（19 base + 15 Memory KB） |

---

## 3. 代码结构现状

### 3.1 模块完成度

```
已就绪模块（蓝色）：
  src/utils/
    ├── llm.py              LLM 封装层（核心已完成，模型路由待补）
    ├── config.py           配置加载（Pydantic Settings）
    ├── cost_tracker.py     费用追踪（价格硬编码待处理）
    └── logger.py           结构化日志

  src/core/protocol.py      通信协议（AgentMessage + MessageRouter + EvidenceItem）

  src/agents/base.py        BaseAgent + AgentResult[Generic[T]]（刚刚泛型化完成）

半完成模块（🟡 部分实现）：
  src/memory/
    └── knowledge_base.py  知识库 RAG（ingest/search/save/load 已完成）
                           （三层记忆中的工作/情景/反思仍为空）

空架子模块（白色，仅 __init__.py）：
  src/debate/         辩论引擎（4 组辩论 + 大师投票 + 交叉质疑）
  src/data/           数据采集（akshare 行情 + 新闻）
  src/backtest/       回测引擎
  src/risk/           风控模块（VaR/波动率/一票否决）
```

### 3.2 技术债务一览

```
紧急指数：1.3/10（历史最低）

✅ 已关闭（3 条）：
  TD-002  AgentResult 泛型化（2026-06-07 刚关）
  TD-009  CI 迁移 GitHub Actions
  TD-011  Pyright 路径硬编码

🔧 修复中（2 条）：
  TD-001  LLM 封装层（核心完成，模型路由待补）
  TD-004  测试基座（88 tests，debate/memory 等模块待补）

📋 已确认（6 条）：
  TD-003  MessageRouter 内存存储
  TD-005  双配置源（YAML vs Pydantic Settings）
  TD-006  EvidenceItem 无校验
  TD-007  ensure_dirs 未被调用
  TD-008  模型价格硬编码
  TD-010  README 仍为 Gitee 模板
```

### 3.3 架构决策（ADR）

| ADR | 内容 | 状态 | 代码落地 |
|-----|------|------|---------|
| 001 | Pydantic 全栈 | ✅ | 部分（AgentMessage 是、AgentContext 是 dataclass） |
| 002 | LangGraph 编排 | ✅ | 依赖已装，代码未写 |
| 003 | akshare 数据源 | ✅ | 依赖已装，代码未写 |
| 004 | Streamlit 前端 | ✅ | 依赖已装，代码未写 |
| 005 | 四组辩论+大师投票 | ✅ | 一个 Agent 未写 |
| 006 | 三层记忆架构 | ✅ | 知识库 RAG（`knowledge_base.py`）已落地，工作/情景/反思仍为空 |
| 007 | DeepSeek 主力 LLM | ✅ | `src/utils/llm.py` 已实现 |
| 008 | 数据契约协议 | ✅ | AgentResult 刚落地，其余待做 |
| 009 | MCP 工具扩展 | ✅ | `get_tools()` 接口已落地，具体 Tool 实现待 Phase 1 |

---

## 4. 关键设计决策（新 AI 必读）

### 4.1 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` 或 `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部临时数据，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误是硬性要求
4. **四同步原则** — 改代码必同步更新：测试 + 文档 + 债务日志

### 4.2 AgentResult 泛型化后的用法

```python
# 向后兼容（已有代码不变）
result = AgentResult(data={"key": "val"})

# 新写法（类型化输出，Pyright 可静态校验）
class NewsOutput(BaseModel):
    summary: str
    sentiment: str

result = AgentResult[NewsOutput](data=NewsOutput(...))
result.data.summary  # Pyright 可校验 ✅
```

### 4.3 金融知识检索：RAG + GREP 双轨

方案文档：`docs/金融知识检索架构-RAG+GREP双轨方案.md`

| 轨道 | 覆盖内容 | 技术 |
|------|---------|------|
| **RAG** | 金融文本（概念解释、大师语录、行业知识） | FAISS + BGE-small-zh |
| **GREP** | 公式/代码（MACD 公式、PE 计算、策略逻辑） | 关键词 + 正则 |

双轨不是二选一，是互补——Agent 可同时调用两个工具，结果合并。

---

## 5. 建议的下一步

> 以下来自架构师分析结论，优先级已排序。

### ✅ 已完成的步骤

| 步骤 | 状态 | 说明 |
|:----:|:----:|------|
| 🥇 第 1 步 | ✅ **已完成** | `get_tools()` 接口已落地 — `BaseAgent` 添加空方法，19 tests 通过 |
| 🥇 第 2a 步 | ✅ **已完成** | `KnowledgeBase` 核心实现（ingest/search/save/load），15 tests 通过 |
| 🥇 第 2b 步 | ✅ **已完成** | 首批 7 篇知识文件已写入（概念/指标/基本面） |
| 🥇 第 2c 步 | 🔧 **进行中** | 教育小智 Agent — 测试已写（RED 确认），Mock 实现待完成 |

### 🥇 当前：教育小智 Agent — 完成 Mock LLM 集成（剩 ~30min）

依赖链：`LLM（done）`+ `KnowledgeBase（done）`= 第一个可对话的 Agent。

还剩的工作：
1. 实现 `XiaoZhiAgent.run()`（带知识库检索 + LLM 调用 + 结果组装）
2. 真实 LLM 集成测试（需 API Key）

### 🥇 后续：知识库批量扩充（见 RAG+GREP 方案 §10）

首批 7 篇太单薄，使用四层扩充策略：

| 阶段 | 方案 | 预估 |
|:----:|------|:----:|
| 1 | **LLM 批量生成** 30-50 篇知识点 | 2h |
| 2 | 公开数据集（FinEval/FinanceQA）脚本导入 | 2h |
| 3 | akshare 自动化 + 社区反馈闭环 | Phase 2+ |

### 🥈 第 3 步：大师 Agent（巴菲特+芒格，2h）

复用 RAG 知识库 + 不同 prompt，可快速产出第二个 Agent。

### 🥈 第 3 步：大师 Agent（巴菲特+芒格，2h）

复用 RAG 知识库 + 不同 prompt，可快速产出第二个 Agent。

### 🥉 第 4 步：辩论编排器（LangGraph StateGraph，3-4h）

有了真实 Agent 后再写编排器，才能写出真正需要的编排逻辑。

---

## 6. 常见问答（Q&A）

**Q：AgentResult 改成 BaseModel 后，现有测试需要改吗？**
A：不需要。`data: dict | T = Field(default_factory=dict)` 设计确保所有现有代码向后兼容。88 个测试全部通过验证。

**Q：`AgentContext` 为什么还是 dataclass？**
A：`AgentContext` 是模块内部传递数据，不跨模块序列化，不需要 Pydantic 的校验和 `model_dump()` 能力。如有跨模块序列化需求再改。

**Q：`to_message()` 里面为什么用 `isinstance(self.data, BaseModel)`？**
A：因为 `data` 可能是 `dict`（向后兼容）也可能是 Pydantic 模型（新写法），需要分别处理。Pydantic 对象走 `.model_dump()` 序列化，dict 直接传。

**Q：`get_tools()` 返回 `list[Any]` 为什么不是具体类型？**
A：LangChain 0.3+ 的 Tool 类型签名跨版本有变化，Phase 0 锁定具体类型会导致后续升级困难。Phase 1 接入真实工具时再确定具体类型。

---

## 7. 文件索引

### 核心代码

| 文件 | 说明 |
|------|------|
| `src/agents/base.py` | Agent 基类 + AgentContext + AgentResult[Generic[T]] |
| `src/core/protocol.py` | 通信协议（AgentMessage / EvidenceItem / MessageRouter） |
| `src/utils/llm.py` | LLM 调用封装（DeepSeek/OpenAI 统一接口） |
| `src/utils/config.py` | 配置加载（Pydantic Settings） |
| `src/utils/cost_tracker.py` | 费用追踪 + 持久化 |
| `src/utils/logger.py` | 结构化日志 |

### 测试

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_sanity.py` | 24 | 冒烟测试 + fixture 验证 |
| `tests/test_agents_base.py` | 17 | AgentContext + AgentResult + BaseAgent |
| `tests/test_core_protocol.py` | 20 | EvidenceItem + AgentMessage + MessageRouter |
| `tests/test_utils_cost_tracker.py` | 15 | CostTracker 全功能 |
| `tests/test_utils_llm.py` | 12 | LLMService 非网络部分 |

### 关键文档

| 文档 | 说明 |
|------|------|
| `CLAUDE.md` | 项目指令（新会话必读） |
| `docs/AI自动化工作流程.md` | 标准操作流程 |
| `docs/技术债务与架构决策/技术债务日志.md` | 债务管理系统 |
| `docs/技术债务与架构决策/架构决策记录.md` | 架构决策记录 |
| `docs/技术债务与架构决策/债务新增模板.md` | 新增债务模板 |
| `docs/金融知识检索架构-RAG+GREP双轨方案.md` | RAG + GREP 方案设计 |
| `docs/ai-work-logs/2026-06-07.md` | 最近工作日志 |

---

## 8. 关键命令速查

```bash
# 一键检查
ruff check src/ tests/
pyright src/ tests/
python -m pytest -v --tb=short

# 运行全部测试
python -m pytest

# 运行特定文件
python -m pytest tests/test_agents_base.py -v

# 提交规范
git add -A
git commit -m "<type>: <description>"
# types: feat, fix, refactor, docs, test, chore, perf, ci
# 参照 CLAUDE.md 中的 AI 工作流程
```

---

> **最后更新**：2026-06-07 | **创建目的**：会话交接
> **如何更新**：每次会话结束时，更新 §2（当前状态）+ §5（下一步）+ 本页页尾日期

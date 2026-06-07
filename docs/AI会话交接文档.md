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
| **最新提交** | `b05ea2b` — feat: get_tools() 接口落地 + KnowledgeBase RAG 核心 + 教育小智 Agent |

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
| ✅ **知识库扩充 23 篇** | 概念(5) + 指标(5) + 基本面(5) + 大师理念(3) + 策略(5)，共 **30 篇**知识文件 |
| ✅ **xiaoZhiAgent 实现** | `src/agents/xiao_zhi.py` — RAG + LLM 问答，15 tests 全通过 |
| ✅ **Master Skill 插件盘** | `src/memory/skill_disk.py` — 7 位投资大师 Skill 定义（巴菲特/芒格/格雷厄姆/林奇/达利欧/德鲁肯米勒/索罗斯） |
| ✅ **skill_disk 测试** | `tests/test_memory_skill_disk.py` — 30 个测试，全量覆盖 |
| ✅ **MasterAgent 通用化** | `src/agents/master_agent.py` — 接收 MasterSkill + KB + LLM，130 行 |
| ✅ **MasterAgent 测试** | `tests/test_agents_master.py` — 24 个测试（初始化/Skill 切换/Mock LLM/降级） |
| ✅ **修复 XiaoZhiAgent 测试** | 使用 tmp_path 隔离 30 篇知识库数据干扰 |
| ✅ **修复 Pydantic V2 弃用警告** | `class Config` → `ConfigDict(frozen=True)` |
| ✅ **AI 工作日志** | `docs/ai-work-logs/2026-06-07-3.md` 已更新 |
| ✅ **Git 已推送** | GitHub + Gitee 双远程已同步 |

### 当前 Git 状态

```
工作区干净 ✅
最新 commit: b05ea2b — feat: get_tools() 接口落地 + KnowledgeBase RAG 核心 + 教育小智 Agent
远程: GitHub (origin) ✅ 已推送 | Gitee (gitee) ✅ 已推送
```

> **注意：会话可能因上下文耗尽而中断。新会话启动流程：阅读本文档 → 最新日志 → 继续 MasterAgent 实现。**

### 三同步检查（当前会话已通过）

| 检查项 | 状态 |
|--------|------|
| Ruff（代码风格） | ✅ 0 errors |
| Pyright（类型检查） | ✅ 0 errors（src/ 零错误） |
| Pytest（测试） | ✅ 174 passed（路径 A-3 MasterAgent 已落地） |

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

  src/agents/
    ├── base.py             BaseAgent + AgentResult[Generic[T]]
    ├── xiao_zhi.py         教育小智 Agent（RAG + LLM，15 tests ✅）
    └── master_agent.py     MasterAgent 通用化（Skill + KB + LLM，24 tests ✅）

半完成模块（🟡 部分实现）：
  src/memory/
    ├── knowledge_base.py   知识库 RAG — 30 篇知识文件已导入
    └── skill_disk.py       Master Skill 插件盘 — 7 位大师定义 ✅
                           （三层记忆中的工作/情景/反思仍为空）

  data/knowledge_base/
    ├── concepts/       8 篇 ✅
    ├── indicators/     7 篇 ✅
    ├── fundamentals/   7 篇 ✅
    ├── masters/        3 篇 ✅
    └── strategies/     5 篇 ✅

空架子模块（白色，仅 __init__.py）：
  src/debate/         辩论引擎（4 组辩论 + 大师投票 + 交叉质疑）
  src/data/           数据采集（akshare 行情 + 新闻）
  src/backtest/       回测引擎
  src/risk/           风控模块（VaR/波动率/一票否决）

待实现：
  src/debate/         辩论引擎（4 组辩论 + 大师投票 + 交叉质疑）
  src/data/           数据采集（akshare 行情 + 新闻）
  src/backtest/       回测引擎
  src/risk/           风控模块（VaR/波动率/一票否决）```

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
| 001 | Pydantic 全栈 | ✅ | AgentResult / AgentMessage ✅ / AgentContext dataclass |
| 002 | LangGraph 编排 | ✅ | 依赖已装，代码未写 |
| 003 | akshare 数据源 | ✅ | 依赖已装，代码未写 |
| 004 | Streamlit 前端 | ✅ | 依赖已装，代码未写 |
| 005 | 四组辩论+大师投票 | ✅ | SkillDisk 7 位大师已定义，MasterAgent 待实现 |
| 006 | 三层记忆架构 | ✅ | 知识库 RAG（`knowledge_base.py`）+ 30 篇知识文件已落地 |
| 007 | DeepSeek 主力 LLM | ✅ | `src/utils/llm.py` 已实现（模型路由待补） |
| 008 | 数据契约协议 | ✅ | AgentResult 已泛型化 + Pydantic 化 ✅ |
| 009 | MCP 工具扩展 | ✅ | `get_tools()` 已落地 ✅ |
| — | **SKILL-001 Skill 插件盘** | 🆕 | **本次新增** — `src/memory/skill_disk.py` 7 位大师 Skill |

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

> 路径 A 核心三件套（知识库 + Skill 插件盘 + MasterAgent）已全部落地。
> 下一步是：**GREP FormulaIndex → 配置 API Key 做集成测试 → 处理 TD-010**

### ✅ 当前已完成

| 步骤 | 状态 | 说明 |
|:----:|:----:|------|
| 🥇 路径A-1 | ✅ | 知识库扩充 → 共 **30 篇**知识文件 |
| 🥇 路径A-2 | ✅ | **Master Skill 插件盘** — `src/memory/skill_disk.py` + 30 tests |
| 🥇 路径A-3 | ✅ **新完成** | **MasterAgent 通用化** — `src/agents/master_agent.py` + 24 tests |
| 🥈 路径A-4 | ⬜ | **GREP FormulaIndex** — 公式精确检索 |
| 🥈 路径A-5 | ⬜ * | **真实 LLM 集成测试** — 需配置 `.env` API Key |
| 🥉 路径A-6 | ⬜ | **TD-010** — 替换 Gitee 模板 README |

### 🥇 关键外部资源（供参考）

| 资源 | 链接 | 用途 |
|------|------|------|
| **AI Hedge Fund** ⭐ 59K+ | [github.com/virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | 同 LangGraph 架构，大师 Agent prompt 可借鉴 |
| **AlphaBuffett** | [github.com/brokenlander/AlphaBuffett](https://github.com/brokenlander/AlphaBuffett) | 巴菲特 1977-2023 股东信数据集 → KnowledgeBase 优质语料 |

### 🥈 Phase 1 MVP 核心链路（路径 A 之后）

| 事项 | 预估 | 前置 |
|------|:----:|:----:|
| GREP FormulaIndex | ~1h | — |
| 辩论编排器 LangGraph StateGraph | 3-4h | 大师 Agent 就绪 ✅ |
| akshare 数据采集 | 1-2 周 | — |
| 四组辩论引擎 | 2-3 周 | 编排器就绪 |
| Streamlit 前端 | 2-3 周 | 后端 API 就绪 |

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
| `src/agents/xiao_zhi.py` | 教育小智 Agent（RAG + LLM 问答） |
| `src/agents/master_agent.py` | **MasterAgent 通用化**（Skill 插件盘 + KB + LLM） |
| `src/memory/skill_disk.py` | **Master Skill 插件盘**（7 位投资大师人格定义） |
| `src/memory/knowledge_base.py` | 知识库 RAG（n-gram TF 向量语义检索） |
| `src/core/protocol.py` | 通信协议（AgentMessage / EvidenceItem / MessageRouter） |
| `src/utils/llm.py` | LLM 调用封装（DeepSeek/OpenAI 统一接口） |
| `src/utils/config.py` | 配置加载（Pydantic Settings） |
| `src/utils/cost_tracker.py` | 费用追踪 + 持久化 |
| `src/utils/logger.py` | 结构化日志 |

### 测试

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_sanity.py` | 24 | 冒烟测试 + fixture 验证 |
| `tests/test_agents_base.py` | 19 | AgentContext + AgentResult + BaseAgent + get_tools |
| `tests/test_core_protocol.py` | 20 | EvidenceItem + AgentMessage + MessageRouter |
| `tests/test_utils_cost_tracker.py` | 15 | CostTracker 全功能 |
| `tests/test_utils_llm.py` | 12 | LLMService 非网络部分 |
| `tests/test_memory_knowledge_base.py` | 15 | KnowledgeBase 全功能 |
| `tests/test_memory_skill_disk.py` | **30** | **MasterSkill + SkillDisk 全功能** |
| `tests/test_agents_xiao_zhi.py` | 15 | XiaoZhiAgent 初始化/输入/LLM/prompt |
| `tests/test_agents_master.py` | **24** | **MasterAgent 初始化/Skill 切换/LLM/降级** |

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

> **最后更新**：2026-06-07 (第 4 次对话) | **创建目的**：会话交接
> **如何更新**：每次会话结束时，更新 §2（当前状态）+ §5（下一步）+ 本页页尾日期

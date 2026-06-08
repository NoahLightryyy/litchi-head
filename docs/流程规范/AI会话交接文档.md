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
| **最新提交** | `d7e9d69` — docs: 全面项目审视 + 登记 TD-016 LangGraph 验证缺口 |

---

## 2. 当前会话状态（2026-06-08 全面项目审视——登记 TD-016，识别五项硬伤）

> **前次会话**：2026-06-07 第 7 次（镜子 Agent 构想 + 前端调研 + 项目批判性重评）
> **本次会话**：2026-06-08 全面项目审视

### 本次已完成的工作

| 事项 | 详情 |
|------|------|
| ✅ **全面项目审视** | 覆盖全部 18 个源码文件、18 个测试文件、14 份文档、10 条 ADR、15 条债务 |
| ✅ **新增 TD-016** | LangGraph 零使用未验证 — 从 Phase 0 到 Phase 1 的最大单一风险（S1 严重） |
| ✅ **识别五项硬伤** | ① 4 个空模块 ② LangGraph 零使用 ③ 关键路径阻塞 ④ TD-013/015 未修 ⑤ README 模板 |
| ✅ **更新文档体系** | 工作日志 + 债务日志 + 看板 + 日志索引，四同步完成 |

### 审视核心结论

| 维度 | 评分 | 关键发现 |
|:----|:----:|:---------|
| 工程管理 | A- | ADR/债务/CI — 远超同龄人水平 |
| 代码完成度 | C+ | 7 模块中 4 个是空架子（57% 空洞率） |
| 测试质量 | B+ | 202 测试全绿，但覆盖率集中在 utils/core/agents |
| 文档完整度 | A- | 14 份文档，结构清晰 |
| 产品可演示性 | D | 无可运行 Demo，4 个空模块是最大硬伤 |

### 五项硬伤（新 AI 特别注意）

1. **🔴 4 个空模块** — debate/data/backtest/risk 全是空 `__init__.py`
2. **🔴 LangGraph 零使用** — ADR-002 选了但没跑过一行 StateGraph → TD-016
3. **🟡 关键路径阻塞** — data → debate → 前端，debate 是核心阻塞点
4. **🟡 TD-013/015 未修** — streaming 接口和缓存解耦，趁调用方少赶紧加
5. **🟢 README.en.md 仍是 Gitee 模板** — TD-010

### 当前 Git 状态

```
工作区干净（已提交）

最新 commit: d7e9d69 — docs: 全面项目审视 + 登记 TD-016 LangGraph 验证缺口
远程: GitHub (origin)，Gitee (gitee) 备份
```

### 三同步检查

| 检查项 | 状态 |
|--------|------|
| Ruff（代码风格） | ✅ 0 errors |
| Pyright（类型检查） | ✅ 0 errors |
| Pytest（测试） | ✅ 202 passed |
| 四同步原则 | ✅ 代码 + 测试 + 文档 + 债务全部同步 |

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
紧急指数：1.2/10（新增 TD-016 LangGraph 验证后回升）

✅ 已关闭（5 条）：
  TD-002  AgentResult 泛型化
  TD-009  CI 迁移 GitHub Actions
  TD-011  Pyright 路径硬编码
  TD-012  LLM 参数硬编码（LLMConfig 数据类 + 17 测试）
  TD-014  AgentContext 辩论槽位（+3 字段 +7 测试）

🔧 修复中（2 条）：
  TD-001  LLM 封装层（核心完成，模型路由待补）
  TD-004  测试基座（202 tests，debate 等模块待补）

📋 已确认（10 条）：
  S1 🟠 严重
  TD-016  LangGraph 零使用未验证 ← Phase 0→1 最大风险，优先处理

  S2 🟡 中等
  TD-003  MessageRouter 内存存储
  TD-005  双配置源（YAML vs Pydantic Settings）
  TD-013  缺少 streaming 接口
  TD-015  LLM 缓存不支持多配置

  S3 🟢 轻微
  TD-006  EvidenceItem 无校验
  TD-007  ensure_dirs 未被调用
  TD-008  模型价格硬编码
  TD-010  README 仍为 Gitee 模板

总债务：16 条（5 已关闭 ✅ / 10 开放 / 1 修复中）
```

### 3.3 架构决策（ADR）

| ADR | 内容 | 状态 | 代码落地 |
|-----|------|------|---------|
| 001 | Pydantic 全栈 | ✅ | AgentResult / AgentMessage ✅ / AgentContext dataclass |
| 002 | LangGraph 编排 | ✅ | 依赖已装，⚠️ 代码未写（TD-016：LangGraph 目前零使用，需尽快验证） |
| 003 | akshare 数据源 | ✅ | 依赖已装，代码未写 |
| 004 | Streamlit 前端 | ✅ | 依赖已装，代码未写 |
| 005 | 四组辩论+大师投票 | ✅ | SkillDisk 7 位大师定义 ✅，debate 引擎代码未写 |
| 006 | 三层记忆架构 | ✅ | 知识库 RAG（knowledge_base.py）+ 30 篇知识文件 ✅ |
| 007 | DeepSeek 主力 LLM | ✅ | src/utils/llm.py 已实现 |
| 008 | 数据契约协议 | ✅ | AgentResult 已泛型化 + Pydantic 化 ✅ |
| 009 | MCP 工具扩展 | ✅ | get_tools() 已落地 ✅ |
| **010** | **Agent 运行时增强** | **🔄** | **LLMConfig ✅ / AgentContext ✅ / Streaming 📋 / 缓存策略 📋 — 2/4 已实现** |

---

## 4. 关键设计决策（新 AI 必读）

### 4.1 🎯 产品定位：手榴弹（2026-06-07 本次确认）

```
机构有原子弹（10 个 CFA + Bloomberg + 自研量化系统）
散户只有手榴弹——但手榴弹拉开环扔出去就能炸

产品使命：散户问一句话 → 15 秒拿到结构化的多维决策信息
         10 秒内能看懂、能决策、能行动
```

**产品输出形态：结构化决策卡，不是 AI 文章。**
- 每个 Agent 输出带证据链的结构化观点（评分 + 逻辑 + 支撑数据）
- 辩论引擎汇总多 agent 分歧点
- 最终输出 = 综合判断 + 各维分析 + 核心分歧 + 一句话建议
- 不超过手机上阅读一屏的长度

### 4.2 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` 或 `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部临时数据，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误是硬性要求
4. **四同步原则** — 改代码必同步更新：测试 + 文档 + 债务日志
5. **Agent 输出应为结构化数据，非纯文本** — 向决策卡输出形态靠拢，含评分/证据/置信度
6. **LLMService 调用走 `LLMConfig`** — 不得硬编码 temperature/max_tokens，差异化的 Agent 传不同的 config

### 4.3 已知骨骼缺陷（新 AI 特别注意）

> ✅ **已修复**：TD-012（LLMConfig 数据类）和 TD-014（AgentContext 辩论槽位）
> ❌ **待修复**：TD-013（streaming）和 TD-015（缓存解耦）— 仍有 2 项

| # | 问题 | 位置 | 状态 | 修复方向 |
|:--|:------|:-----|:----:|:---------|
| TD-013 | 无 streaming 接口 | `src/utils/llm.py` | 📋 | 新增 `astream() → AsyncIterator[str]` |
| TD-015 | 按 provider 名缓存 LLM 实例，不同 config 冲突 | `src/utils/llm.py` | 📋 | 非默认 LLMConfig 不缓存 |

**新增架构风险**：
| # | 问题 | 位置 | 状态 | 修复方向 |
|:--|:------|:-----|:----:|:---------|
| TD-016 | LangGraph 零使用未验证 | 全项目 | 📋 | 跑通最小 StateGraph 原型，验证 API 与接口设计的匹配度 |

**设计原则**：所有修改向后兼容，默认值 = 当前行为，零测试回归。

### 4.4 AgentResult 泛型化后的用法

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

方案文档：`docs/架构设计/金融知识检索架构-RAG+GREP双轨方案.md`

| 轨道 | 覆盖内容 | 技术 |
|------|---------|------|
| **RAG** | 金融文本（概念解释、大师语录、行业知识） | FAISS + BGE-small-zh |
| **GREP** | 公式/代码（MACD 公式、PE 计算、策略逻辑） | 关键词 + 正则 |

双轨不是二选一，是互补——Agent 可同时调用两个工具，结果合并。

---

## 5. 建议的下一步

> **⚠️ 优先级已更新（2026-06-08 全面审视后）**
> 
> 最大风险变更：**LangGraph 零使用**（TD-016）取代 TD-012/014 成为头号关注。
> Phase 0 收尾的新顺序：**LangGraph 验证 → TD-013/015 → 空模块骨架 → Phase 1 辩论引擎**

### 🥇 Phase 0 收尾（按顺序执行）

| 优先级 | 事项 | 文件 | 预估 | 说明 |
|:------:|:----|:----|:----:|------|
| 🥇 | **① LangGraph 最小原型验证**（TD-016） | 新建 `tests/test_langgraph_prototype.py` | ~0.5d | **当前最大风险**。跑通 StateGraph，确认 `BaseAgent.run()` 可作为节点、`AgentContext` 可序列化为 State |
| 🥇 | **② TD-015 缓存策略解耦** | `src/utils/llm.py` | ~0.5d | 非默认 LLMConfig 不缓存（已有 is_default 检测，主要补测试） |
| 🥇 | **③ TD-013 Streaming 接口** | `src/utils/llm.py` | ~0.5d | 新增 `astream() → AsyncIterator[str]`，趁只有 2 个调用方 |
| 🥈 | **④ MasterAgent 输出结构化** | `src/agents/master_agent.py` | ~1d | 纯文本 → 结构化评级 + 证据 + 置信度 |
| 🥈 | **⑤ Phase 0 收尾修复** | 多处 | ~45min | Pyright tests/ 标注、config.py deprecation、.env.example、pytest-cov |
| 🥉 | **⑥ 4 个空模块骨架代码** | debate/data/backtest/risk | ~15min | 每个加 `raise NotImplementedError` + 模块文档 |
| 🥉 | **⑦ A-6 TD-010 README** | `README.en.md` | ~30min | 替换 Gitee 模板 |

### 🥇 Phase 1 MVP（Phase 0 收尾后）

| 优先级 | 步骤 | 说明 | 前置 |
|:------:|:----:|:-----|:----:|
| 🥇 | **辩论编排器 LangGraph StateGraph** | 辩论引擎的第一步 | LangGraph 原型验证 ✅ |
| 🥇 | **辩论分组逻辑** | 4 组大师分组辩论实现 | 编排器就绪 |
| 🥇 | **数据采集接入** | akshare 行情 + 新闻 | data 模块骨架就绪 |
| 🥇 | **前端 MVP（3 页面）** | Streamlit 首页/分析/我的 | 端到端链路就绪 |
| 🥈 | **用户行为镜子 Agent 记录期原型** | 1-9 次决策行为记录 | 辩论引擎就绪 |
| 🥈 | **回测模块基础** | 简单策略回测 | data 模块就绪 |

### 🆕 未来构想

| 事项 | 阶段 | 前置 |
|:-----|:----:|:-----|
| 用户行为镜子 Agent（对比期/出师期） | Phase 1+ | 辩论引擎就绪 |
| 风控模块（VaR/波动率） | Phase 2+ | data 模块就绪 |
| 前端决策卡可视化升级 | Phase 2+ | MVP 前端就绪 |
| 英文 README | Phase 2+ | Phase 1 MVP 完成 |

> 镜子 Agent 完整设计见 `docs/架构设计/用户行为镜子Agent设计构想.md`（9 章）
> 前端 MVP 需求见 `docs/产品需求/前端MVP需求文档-基于市场对标.md`（3 页线框图）

### 🆕 前端 MVP 需求（基于市场对标）

> 2026-06-07 新增 — 见 `docs/产品需求/前端MVP需求文档-基于市场对标.md`

调研了 TradingAgents(70k⭐) / AI Hedge Fund(51k⭐) / Vibe-Trading(9.3k⭐) 的前端方案后提炼的 MVP 需求。

**核心决策**：
- 不搬 AI Hedge Fund 的拖拽式工作流（和"手榴弹"定位冲突）
- 不搬 Vibe-Trading 的回测图表（没有后端支持）
- 参考 TradingAgents 的 Streamlit 分支风格（表单+决策卡+进度条）
- 风格定位：「决策卡」—— 快、清晰、一屏看完

**3 个页面**：首页（市场）→ 分析页（核心）→ 我的页面（镜子 Agent 入口）

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
| `tests/test_integration_master_agent.py` | **4** 🆕 | **MasterAgent 真实 DeepSeek API 集成测试** |

### 关键文档

| 文档 | 说明 |
|------|------|
| `CLAUDE.md` | 项目指令（新会话必读） |
| `CLAUDE.md` | 项目指令（新会话必读） |
| **`docs/计划/README.md`** | 🎯 **项目看板（新建）** — **一站式总览进度** |
| `docs/流程规范/` | 📐 **流程规范** — AI自动化工作流程、会话交接文档 |
| `docs/技术债务与架构决策/技术债务日志.md` | 债务管理系统 |
| `docs/技术债务与架构决策/架构决策记录.md` | 架构决策记录 |
| `docs/技术债务与架构决策/债务新增模板.md` | 新增债务模板 |
| `docs/架构设计/` | 🏗️ **架构设计** — 技术方案、金融检索、镜子Agent |
| `docs/产品需求/` | 📋 **产品需求** — 初版要求、前端MVP需求 |
| `docs/调研分析/` | 🔍 **调研分析** — 竞品调研、对比分析 |
| `docs/项目介绍/` | 📖 **项目介绍** — 通俗版介绍 |
| `docs/ai-work-logs/` | 📓 工作日志索引（按年月分组） |
| `docs/ai-work-logs/README.md` | 日志索引（按年月分组） |

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

> **最后更新**：2026-06-08 (全面项目审视 — 新增 TD-016 LangGraph 验证缺口，五项硬伤识别) | **创建目的**：会话交接
> **如何更新**：每次会话结束时，更新 §2（当前状态）+ §5（下一步）+ 本页页尾日期

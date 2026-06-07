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
| **最新提交** | `c26ae20` — docs: AI 工作日志按日分文件夹重组 + 全面项目审查 |

---

## 2. 当前会话状态（2026-06-07 第 7 次对话——镜子 Agent 构想 + 前端调研 + 项目批判性重评）

### 本次已完成的工作

| 事项 | 详情 |
|------|------|
| ✅ **用户行为镜子 Agent 设计构想** | 完整设计文档 `docs/架构设计/用户行为镜子Agent设计构想.md` — 9 章（哲学/定位/旅程/解锁/数据/架构/输出/计划/FAQ） |
| ✅ **竞品前端调研** | 调研 TradingAgents/AI Hedge Fund/Vibe-Trading 前端方案，提取共性 |
| ✅ **前端 MVP 需求文档** | `docs/产品需求/前端MVP需求文档-基于市场对标.md` — 3 页线框图 + 数据契约 + 做/不做清单 |
| ✅ **项目批判性重评** | 修正"工程管理是护城河"→"产品叙事是护城河"。4 处硬伤：LangGraph 零使用、4空目录、镜子冷启动、无英文 README |
| ✅ **"框架先行+AI填肉"模式确认** | 你管骨架（接口/类型/契约），AI 管填肉。框架先行策略正确，但 LangGraph 最小原型需尽快验证 |
| ✅ **作者信息记录** | 长安大学大三（人工智能中外合办），项目用于留学申请 + 求职 + 给爸妈用 |

### 本次核心产出：用户行为镜子 Agent

**定位**：既是镜子，也是最好的老师。不分析市场，分析用户自己的投资行为。

```
镜子说：
"你的 10 笔交易中，7 笔亏损，3 笔盈利。"

老师 + 镜子说：
"你的 10 笔交易中，7 笔亏损，3 笔盈利。
 值得注意的是：3 笔盈利的平均持有 45 天，7 笔亏损的平均持有 3 天。
 你的问题不是选股，是拿不住。"
```

**三段式解锁**：📝 记录期(1-9次) → 🔍 对比期(10+次) → 🗣️ 出师期(30+次)

### 本次核心产出：前端 MVP 需求（基于竞品调研）

调研结论：三个竞品前端路线完全不同——

| 竞品 | 前端风格 | 反映的定位 | 我们搬不搬 |
|:----|:---------|:-----------|:----------:|
| TradingAgents | Streamlit 表单+决策卡+进度条 | 投研工具 | ✅ 参考风格 |
| AI Hedge Fund | React Flow 拖拽工作流 | 量化研究员工作台 | ❌ 和手榴弹冲突 |
| Vibe-Trading | React 19 聊天+回测图表 | 量化策略工作室 | ❌ 无后端支持 |

**前端设计原则**：「决策卡」—— 快、清晰、一屏看完。3 个页面：首页（市场）→ 分析页（核心）→ 我的页面。

### 项目批判性重评（2026-06-07 本次修正）

```
旧判断："工程管理是护城河"
新判断："工程管理是基础，产品叙事才是护城河"

镜子 Agent 是当前项目最有可能建立叙事差异化的点。
但时间窗口可能只有 6-12 个月——竞品也在进化。
```

**评分（以大三学生留学/求职为评价标准）**：

| 维度 | 评分 | 说明 |
|:----|:----:|:-----|
| 技术深度 | A- | 多 Agent + RAG + 辩论架构，远超大多本科项目 |
| 工程规范 | A | ADR/债务/CI/类型系统 — 拉开差距的地方 |
| 产品完成度 | C | 4个空目录是硬伤，LangGraph 零使用 |
| 可展示性 | C | 无前端，无 Demo，招生官没法一眼看懂 |
| 含金量（做完） | A | 如果能跑通端到端 Demo，留学/求职都是加分项 |

### 当前 Git 状态

```
工作区有修改（未提交）
变更文件：
  M docs/ai-work-logs/README.md                     ← 日志索引新增
  M docs/技术债务与架构决策/架构决策记录.md           ← 新增 ADR-010
  M docs/技术债务与架构决策/技术债务日志.md           ← 新增 TD-012~015
  ?? docs/ai-work-logs/2026/06/07/2026-06-07-6.md  ← 本次工作日志

最新 commit: c26ae20 — docs: AI 工作日志按日分文件夹重组 + 全面项目审查
远程: GitHub (origin)
```

### 三同步检查

| 检查项 | 状态 |
|--------|------|
| Ruff（代码风格） | ✅ 仅改文档 |
| Pyright（类型检查） | ✅ 仅改文档 |
| Pytest（测试） | ✅ 178 passed |
| 四同步原则 | ✅ 代码(无变更) + 测试(无变更) + 文档(3处) + 债务(已更新) |

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
紧急指数：1.8/10（因本次审查新增 4 条骨骼级债务）

✅ 已关闭（3 条）：
  TD-002  AgentResult 泛型化
  TD-009  CI 迁移 GitHub Actions
  TD-011  Pyright 路径硬编码

🔧 修复中（2 条）：
  TD-001  LLM 封装层（核心完成，模型路由待补）
  TD-004  测试基座（178 tests，debate 等模块待补）

📋 已确认（12 条）：
  TD-003  MessageRouter 内存存储
  TD-005  双配置源（YAML vs Pydantic Settings）
  TD-006  EvidenceItem 无校验
  TD-007  ensure_dirs 未被调用
  TD-008  模型价格硬编码
  TD-010  README 仍为 Gitee 模板
  ── 本次新增（骨骼级，Phase 0 收尾前应修复）──
  TD-012  LLM 参数硬编码（temperature/max_tokens 不可按 Agent 覆盖）🟠 S1
  TD-013  缺少 streaming 接口 🟡 S2
  TD-014  AgentContext 缺辩论槽位 🟠 S1 ✅ 已修复
  TD-015  LLM 缓存不支持多配置 🟡 S2
```

### 3.3 架构决策（ADR）

| ADR | 内容 | 状态 | 代码落地 |
|-----|------|------|---------|
| 001 | Pydantic 全栈 | ✅ | AgentResult / AgentMessage ✅ / AgentContext dataclass |
| 002 | LangGraph 编排 | ✅ | 依赖已装，⚠️ 代码未写（注意：LangGraph 目前零使用） |
| 003 | akshare 数据源 | ✅ | 依赖已装，代码未写 |
| 004 | Streamlit 前端 | ✅ | 依赖已装，代码未写 |
| 005 | 四组辩论+大师投票 | ✅ | SkillDisk 7 位大师定义 ✅，debate 引擎代码未写 |
| 006 | 三层记忆架构 | ✅ | 知识库 RAG（knowledge_base.py）+ 30 篇知识文件 ✅ |
| 007 | DeepSeek 主力 LLM | ✅ | src/utils/llm.py 已实现 |
| 008 | 数据契约协议 | ✅ | AgentResult 已泛型化 + Pydantic 化 ✅ |
| 009 | MCP 工具扩展 | ✅ | get_tools() 已落地 ✅ |
| **010** | **Agent 运行时增强** | **✅** | **LLMConfig / streaming / 辩论上下文 / 缓存策略 — 设计已定，代码待实现** |

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

以下 4 处是 Phase 0 必须修复的骨骼问题（ADR-010 已设计，代码未实现）：

| # | 问题 | 位置 | 修复方向 |
|:--|:------|:-----|:---------|
| TD-012 | LLM 参数硬编码：temperature=0.3, max_tokens=8192 不可覆盖 | `src/utils/llm.py` | 新增 `LLMConfig` 数据类，`ainvoke()` 加可选参数 |
| TD-013 | 无 streaming 接口 | `src/utils/llm.py` | 新增 `astream() → AsyncIterator[str]` |
| TD-014 | AgentContext 只能传 question，无法接收 peer 输出 | `src/agents/base.py` | 加 `peer_outputs`/`current_round`/`target_audience` |
| TD-015 | 按 provider 名缓存 LLM 实例，不同 config 冲突 | `src/utils/llm.py` | 非默认 LLMConfig 不缓存 |

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

> **⚠️ 优先级已更新（2026-06-07 本轮会话）**
> TD-014 已修复 ✅，**TD-012 也已修复 ✅**（LLMConfig 数据类 + 17 测试，202 全量通过）。
> 剩余 2 项骨骼缺陷：**TD-015 → TD-013**（缓存策略 → streaming，可并行推进）。

### 立即修复（Phase 0 收尾前应完成）

| 优先级 | 事项 | 文件 | 预估 | 说明 |
|:------:|:----|:----|:----:|------|
| ~~🥇~~ | ~~**TD-014 AgentContext 辩论槽位**~~ | ~~`src/agents/base.py`~~ | ~~~30min~~ | **✅ 已完成**（+3 字段 +7 测试，185 全量通过） |
| ~~🥇~~ | ~~**TD-012 LLMConfig + 参数暴露**~~ | ~~`src/utils/llm.py`~~ | ~~~1d~~ | **✅ 已完成**（LLMConfig 数据类 + 接口修改 + 29 测试，202 全量通过） |
| 🥇 | **TD-015 缓存策略解耦** | `src/utils/llm.py` | ~0.5d | 非默认 LLMConfig 不缓存（已有 is_default 检测，主要补测试） |
| 🥇 | **TD-013 Streaming 接口** | `src/utils/llm.py` | ~0.5d | 新增 `astream() → AsyncIterator[str]` |
| 🥈 | **MasterAgent 输出结构化** | `src/agents/master_agent.py` | ~1d | 将纯文本改为结构化评级 + 证据 + 置信度 |
| 🥈 | **Phase 0 收尾修复** | 多处 | ~45min | Pyright tests/ 标注、config.py deprecation、.env.example、pytest-cov |

### 之后（原计划路径）

| 优先级 | 步骤 | 说明 | 前置 |
|:------:|:----:|:-----|:----:|
| 🥉 | A-4 GREP FormulaIndex | 公式精确检索 | — |
| 🥉 | A-6 TD-010 README | 替换 Gitee 模板 | — |
| 🥉 | 辩论编排器 LangGraph StateGraph | 辩论引擎的第一步 | TD-014 修复后 |
| 🥉 | 产品定位文档 | 按「手榴弹」方向写正式的 PRD/产品设计 | — |

### 🆕 未来构想：用户行为镜子 Agent

> 2026-06-07 新增 — 产品构想阶段，见 `docs/架构设计/用户行为镜子Agent设计构想.md`

**定位**：既是镜子，也是最好的老师。不分析市场，分析用户自己的投资行为。

**核心机制**：
- 📝 **记录期**（1-9 次决策）：只记录不出声，积累行为基线
- 🔍 **对比期**（10+ 次决策）：出对比报告，展示"当前操作 vs 你的历史相似操作"
- 🗣️ **出师期**（30+ 次决策）：可在辩论票中占一个可选席位

**≠ 交易教练**。不做预判、不给指令，只展示模式让用户自行判断。

依赖：辩论引擎就绪 → 出师后可占席位；知识库就绪 → 偏差检测后可关联教育内容。

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

> **最后更新**：2026-06-07 (TD-012 修复 — LLMConfig 数据类 + 17 测试，202 全量通过) | **创建目的**：会话交接
> **如何更新**：每次会话结束时，更新 §2（当前状态）+ §5（下一步）+ 本页页尾日期

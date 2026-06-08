# 🔄 AI 会话交接文档

> 用途：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
> **新 AI 启动流程：**
> 
> ```
> 记忆层自动注入       ← project-identity + architecture-decisions + current-state
>   ↓                  （来自 memory 系统，不需要我读文件）
> 交接文档 §2 + §5     ← 当前状态 + 下一步（约 3K token）
>   ↓
> 最新工作日志         ← 前一次会话具体内容
>   ↓
> 按需加载（用到才读）← 债务日志 / 设计文档 / 历史日志
> ```
> 
> 注意：不再逐个完整读取债务日志、自动化工作流程文档、CLAUDE.md（其核心内容已由 memory 层覆盖）。

---

## 1. 项目身份卡

| 字段 | 值 |
|------|-----|
| **项目名称** | litchi-head — 多智能体投资决策平台 |
| **当前阶段** | Phase 1 MVP 期（data/ 已上线，debate/ 待启动） |
| **技术栈** | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / akshare / FAISS |
| **代码位置** | `e:\litchi-head` |
| **远程仓库** | GitHub (`origin`)，Gitee (`gitee`) 作为备份 |
| **默认分支** | `main` |
| **CI** | GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13） |
| **最新提交** | `7067edf` — feat: Phase 0 核心收尾完成（TD-013/015/010 + MasterAgent 结构化） |

---

## 2. 当前会话状态（2026-06-08 第 4 次 — Phase 1 数据层上线 ✅）

> **前次会话**：2026-06-08 第 3 次 — Phase 0 收尾完成
> **本次会话**：2026-06-08 第 4 次 — Phase 1 data/ 模块完整实现

### 本次已完成的工作

| 事项 | 详情 |
|------|------|
| ✅ **src/data/models.py** | 5 个 Pydantic 数据契约（StockInfo/StockQuote/KLine/NewsItem/BoardInfo），17 测试 |
| ✅ **src/data/cache.py** | DataCache 内存 TTL 缓存层（30s~1h 可配），11 测试 |
| ✅ **src/data/collector.py** | DataCollector 封装 6 类 akshare 数据（行情/K线/新闻/板块/股票列表），15 测试 |
| ✅ **src/data/__init__.py** | 模块文档 + 公共 API 导出 |
| ✅ **tests/test_data_models.py / test_data_cache.py / test_data_collector.py** | 43 单元测试全绿 |
| ✅ **tests/test_data_integration.py** | 集成测试框架（按数据源独立 skip，代理环境自动跳过） |
| ✅ **质量门禁** | Ruff ✅ Pyright ✅ 272 passed |
| ✅ **文档同步** | 工作日志 + current-state + roadmap + 交接文档全部更新 |
| ✅ **新增债务** | **0** — 四同步执行良好 |
| ✅ **工作流复盘** | §9 新增工作流优化建议章节 |

### 项目核心状态（2026-06-08 第 4 次）

| 维度 | 评分 | 关键发现 |
|:----|:----:|:---------|
| 工程管理 | A | ADR/债务/CI/记忆系统 — 成熟度持续提升 |
| 代码完成度 | C+ | 8 模块中 5 个就绪，3 个空架（debate/backtest/risk） |
| 测试质量 | B+ | **272** 测试全绿（+43 data 新增） |
| 文档完整度 | A- | 15+ 份文档，结构清晰 |
| 产品可演示性 | D | 无可运行 Demo，debate 是核心阻塞点 |

### 硬伤跟踪

1. **🔴 3 个空模块** — debate/backtest/risk（仅 `__init__.py`）
2. **🟢 ~~data 模块~~** — ✅ **已实现**（Phase 1 第一步完成）
3. **🟡 关键路径阻塞** — debate 是下一核心阻塞点

### 当前 Git 状态

```
工作区有未提交变更（代码 + 文档 + 日志）

最新 commit: 7067edf — feat: Phase 0 核心收尾完成（TD-013/015/010 + MasterAgent 结构化）
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|---------|:------:|---------|
| `tests/test_data_models.py` | 17 | StockInfo/StockQuote/KLine/NewsItem/BoardInfo |
| `tests/test_data_cache.py` | 11 | DataCache set/get/TTL/delete/clear |
| `tests/test_data_collector.py` | 15 | DataCollector 6 类数据 + 缓存 + 错误处理 |
| `tests/test_data_integration.py` | 5（skip） | 真实 akshare 集成测试 |
| **全量** | **272 passed, 4 skipped** | |

---

## 3. 代码结构现状

### 3.1 模块完成度

```
已就绪模块（✅）：
  src/utils/       — llm / config / cost_tracker / logger（100%）
  src/core/        — protocol（AgentMessage + MessageRouter）
  src/agents/      — base / xiao_zhi / master_agent（全部通用化）
  src/data/        — models / cache / collector（Phase 1 ✅ 本期新增）

部分实现模块（🟡）：
  src/memory/      — knowledge_base（30篇知识）/ skill_disk（7位大师）
                     工作记忆/情景记忆/反思仍为空

空架子模块（⬜）：
  src/debate/      — 辩论引擎（下一核心目标）
  src/backtest/    — 回测引擎
  src/risk/        — 风控模块
```

### 3.2 技术债务一览

```
紧急指数：0.6/10（持续下降）

✅ 已关闭（9 条）：
  TD-002 / TD-009 / TD-010 / TD-011 / TD-012 / TD-013 / TD-014 / TD-015 / TD-016

🔧 修复中（2 条）：
  TD-001  LLM 封装层（核心完成，模型路由待补）
  TD-004  测试基座（272 tests，debate/memory/risk 待补）

📋 已确认（5 条，全部低优）：
  S2 🟡 TD-003 MessageRouter 内存存储 / TD-005 双配置源
  S3 🟢 TD-006 EvidenceItem 无校验 / TD-007 ensure_dirs / TD-008 价格硬编码

开放债务：5 条（历史最低）
```

---

## 4. 关键设计决策

### 4.1 产品定位：手榴弹

```
机构有原子弹（10 个 CFA + Bloomberg + 自研量化系统）
散户只有手榴弹——但手榴弹拉开环扔出去就能炸

产品使命：散户问一句话 → 15 秒拿到结构化的多维决策信息
         10 秒内能看懂、能决策、能行动
```

### 4.2 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` / `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误
4. **四同步原则** — 代码 + 测试 + 文档 + 债务日志同步更新
5. **Agent 输出结构化** — 含评分/证据/置信度，非纯文本
6. **LLMService 调用走 `LLMConfig`** — 不硬编码 temperature/max_tokens

### 4.3 AgentResult 泛型化后的用法

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

### 4.4 data 模块使用示例

```python
from src.data import DataCollector

collector = DataCollector()

# 全部 A 股（缓存 1h）
stocks = collector.get_all_stocks()

# 实时行情（缓存 30s）
quotes = collector.get_realtime_quotes()

# 个股 K 线（缓存 5min）
klines = collector.get_klines("000001", period="daily")
```

---

## 5. 下一步优先级

### 🥇 Phase 1 MVP 核心链路

| 优先级 | 步骤 | 说明 | 前置 |
|:------:|:----:|:-----|:----:|
| 🥇 | **辩论编排器** `src/debate/` | LangGraph StateGraph 串联辩论流程（~4-6h） | LangGraph 原型 ✅ + data 模块 ✅ |
| 🥇 | **data → debate 接驳** | 辩论 Agent 使用 DataCollector 获取实时数据 | 编排器就绪 |
| 🥈 | **三层记忆 MVP** | JSON 持久化（工作/情景/反思） | — |
| 🥉 | **前端 MVP** | Streamlit 3 页面 | 端到端链路就绪 |

### 🥉 低优清理

| 事项 | 说明 |
|:----|:------|
| TD-003 MessageRouter 持久化 | JSON snapshot 或 SQLite |
| TD-005 双配置源协调 | settings.yaml + Pydantic Settings 优先级文档化 |
| TD-007 ensure_dirs 调用 | Settings init 后自动调用 |
| TD-008 价格表外置 | 移到 `config/prices.yaml` |

---

## 6. 工作流优化建议 ← 新增

> 2026-06-08 第 4 次会话复盘产出。
> 以下问题影响开发效率，建议新会话优先配置或遵循。

### 6.1 已知效率问题与修复

| 问题 | 影响 | 修复方案 | 状态 |
|:----|:----:|:---------|:----:|
| **质量修复循环过多** | 每次写代码后 3-6 轮 Ruff/Pyright 修复 | 配置 PostWrite hook 自动 `ruff check --fix`（见下） | ✅ 已配置 `~/.claude/settings.local.json` |
| **pandas 类型反复** | `row["code"]` 被推断为 Series，Pyright 报错 | 记忆已记录模式：必须 `str(row["col"])` 显式转换 | ✅ 已记录 |
| **Windows make 不可用** | 每次手动敲 3 条命令 | 用 `.\scripts\check.ps1` 代替 `make check` | ❌ 待验证 |
| **Agent API 不兼容 DeepSeek** | planner/Explore 代理因 reasoning_effort 失败 | 降级到 Plan Mode 并记入 memory | ✅ 已记录 |
| **集成测试 skip 检测反复** | 代理环境特殊，试了 3 种方案才稳定 | 使用 HTTP urlopen 检测，按数据源独立标记 | ✅ 已解决 |

### 6.2 推荐配置：PostWrite hook（最关键改动）

在 `~/.claude/settings.local.json` 或 `.claude/settings.json` 添加：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "ruff check --fix \"$FILE_PATH\"",
        "description": "Write/Edit 后自动修复 Ruff 格式问题，消除质量修复循环"
      }
    ]
  }
}
```

**预期效果**：每次写完代码自动修复缩进、行长、未使用 import、import 排序，减少 6 轮 → 1 轮。

### 6.3 已知 pandas 类型模式（必须遵守）

akshare 返回 `pd.DataFrame`，`df.iterrows()` 的 `row["col"]` 被 Pyright 推断为 `Series | ndarray | Any`。直接传给 Pydantic `str` 字段会报类型错误。

**必须写**：
```python
# ❌ 错误：Pyright 报 type mismatch
StockInfo(code=row["code"], name=row["name"])

# ✅ 正确：显式转换
StockInfo(code=str(row["code"]), name=str(row["name"]))
StockQuote(price=float(row["最新价"]), volume=int(row["成交量"]))
```

### 6.4 会话草稿模式（推荐工作习惯）

当前流程：全部代码写完 → 最后集中补写工作日志 / memory。
改进：用一个 scratchpad 文件或内存列表，每完成一个 todo item 追加一行，最终日志直接以此为基础编写。

```markdown
# 每次完成一个 todo，追加一行：
- [x] 步骤 ①: models.py + 17 测试
- [x] 步骤 ②: cache.py + 11 测试
...
# 会话结束 = 日志骨架已就绪
```

---

## 7. 常见问答

**Q：AgentResult 改成 BaseModel 后，现有测试需要改吗？**
A：不需要。`data: dict | T = Field(default_factory=dict)` 设计确保所有现有代码向后兼容。

**Q：为什么 AgentContext 还是 dataclass？**
A：模块内部传递数据，不跨模块序列化。如有跨模块序列化需求再改。

**Q：集成测试为什么跳过？**
A：代理环境屏蔽了东方财富 API（push2.eastmoney.com），`urllib.request.urlopen(..., timeout=3)` 检测失败时自动跳过。CI 环境会正常跑通。

---

## 8. 文件索引

### src/data/（本期新增）

| 文件 | 说明 |
|------|------|
| `src/data/models.py` | 5 个 Pydantic 数据契约（StockInfo/StockQuote/KLine/NewsItem/BoardInfo） |
| `src/data/cache.py` | DataCache 内存 TTL 缓存 |
| `src/data/collector.py` | DataCollector 封装 akshare 6 类数据 |
| `tests/test_data_models.py` | 17 测试 |
| `tests/test_data_cache.py` | 11 测试 |
| `tests/test_data_collector.py` | 15 测试 |
| `tests/test_data_integration.py` | 集成测试（按数据源独立 skip） |

### 核心代码

| 文件 | 说明 |
|------|------|
| `src/agents/base.py` | Agent 基类 + AgentContext + AgentResult[Generic[T]] |
| `src/agents/xiao_zhi.py` | 教育小智 Agent（RAG + LLM 问答） |
| `src/agents/master_agent.py` | MasterAgent 通用化（Skill 插件盘 + KB + LLM + 结构化输出） |
| `src/memory/skill_disk.py` | Master Skill 插件盘（7 位投资大师人格定义） |
| `src/memory/knowledge_base.py` | 知识库 RAG（n-gram TF 向量语义检索） |
| `src/core/protocol.py` | 通信协议（AgentMessage / EvidenceItem / MessageRouter） |
| `src/utils/llm.py` | LLM 调用封装（DeepSeek/OpenAI 统一接口 + Streaming + LLMConfig） |
| `src/utils/config.py` | 配置加载（Pydantic Settings） |
| `src/utils/cost_tracker.py` | 费用追踪 + 持久化 |
| `src/utils/logger.py` | 结构化日志 |

### 测试概览

| 文件 | 测试数 | 覆盖 |
|------|:------:|------|
| `tests/test_sanity.py` | 24 | 冒烟测试 |
| `tests/test_agents_base.py` | 19 | AgentContext + AgentResult |
| `tests/test_core_protocol.py` | 20 | 通信协议 |
| `tests/test_utils_cost_tracker.py` | 15 | 费用追踪 |
| `tests/test_utils_llm.py` | 29 | LLMService + LLMConfig + Streaming |
| `tests/test_memory_knowledge_base.py` | 15 | 知识库 RAG |
| `tests/test_memory_skill_disk.py` | 30 | MasterSkill + SkillDisk |
| `tests/test_agents_xiao_zhi.py` | 15 | 小智 Agent |
| `tests/test_agents_master.py` | 24 | MasterAgent |
| `tests/test_integration_master_agent.py` | 4 | 真实 LLM 集成测试 |
| `tests/test_data_models.py` | 17 | **数据模型（本期新增）** |
| `tests/test_data_cache.py` | 11 | **缓存层（本期新增）** |
| `tests/test_data_collector.py` | 15 | **采集器（本期新增）** |
| `tests/test_data_integration.py` | 5 | **集成测试（本期新增）** |

---

> **最后更新**：2026-06-08 第 4 次（Phase 1 data/ 模块上线 ✅） | **如何更新**：每次会话结束时更新 §2 + §5 + 本行

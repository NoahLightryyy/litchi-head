# 🔄 AI 会话交接文档

> **用途**：上下文窗口达到上限，需要切换对话时，新会话从本文档恢复工作状态。
>
> **人类速查**：看 [HANDOVER_TIP.md](HANDOVER_TIP.md)（一页纸，扫一眼就够）。
>
> **上下文耗尽自动交接**：当 AI 检测到上下文接近上限时（~20K tokens 剩余），
> 自动执行交接流程（更新日志+债务+看板+提交），不推进新工作。
> 详细流程见 CLAUDE.md「上下文耗尽自动交接」节。

---

## 📋 如何读本文档

**本文档是全局仪表盘**，各部门的专有信息已下沉到各自部门文件夹：

```
docs/06-departments/
├── 00-cross-cutting/HANDOVER.md   ← 跨部门状态总览（推荐先读这个）
├── 01-data/HANDOVER.md            ← 数据管道部工作交接
├── 02-debate-engine/HANDOVER.md   ← 辩论引擎部工作交接
├── 03-ai-agents/HANDOVER.md       ← AI Agent 架构部工作交接
├── ...                             ← 其他部门同理
└── README.md                      ← 完整部门索引 + 协作规程
```

**工作流文档**也已完成按阶段拆分：

```
docs/01-guides/
├── WORKFLOW.md                       ← 索引（50 行，决策树导航）
└── workflow/
    ├── STARTUP.md                    ← 🚀 新会话启动 + 部门角色加载
    ├── DEVELOPMENT.md                ← 🔨 日常开发 + 代码规范
    ├── CLOSING.md                    ← ✅ 会话收尾 + 债务管理
    └── EMERGENCIES.md                ← ⚠️ 审视清单 + 突发情况
```

**各部门的债务**在 `DEBT.md` 中：
```
docs/06-departments/01-data/DEBT.md
docs/06-departments/02-debate-engine/DEBT.md
...
```

> **新 AI 启动**：执行 `/resume-session` Skill → 自动加载身份卡 + 当前状态 + 工作日志。

---

## 1. 项目身份卡

| 字段 | 值 |
|------|-----|
| **项目名称** | litchi-head — 多智能体投资决策平台 |
| **当前阶段** | Phase 1 MVP + Phase R 实盘加固 |
| **技术栈** | Python 3.12+ / LangGraph / DeepSeek-Chat / Pydantic / akshare / FAISS |
| **代码位置** | `e:\litchi-head` |
| **远程仓库** | GitHub (`origin`)，Gitee (`gitee`) 作为备份 |
| **默认分支** | `main` |
| **CI** | GitHub Actions（Ruff + Pyright + Pytest on 3.12/3.13） |
| **最新提交** | `266765f` — docs: FD-001 文档同步 + 剩余任务下放对应部门 |
| **全量测试** | 1012 collected, 全部通过 ✅ |
| **设计哲学** | 🏛️ [DESIGN_PHILOSOPHY.md](../00-overview/DESIGN_PHILOSOPHY.md) — 虚拟小投行蓝图 |
| **Pyright** | src/ 0 errors, backend/ 0 errors ✅ |
| **CI 状态** | 🟢 → 最近 4 次全绿 ✅ |

---

## 🏢 各部门一览

| 部门 | 代码 | 状态 | 开放债务 | → 看这里 |
|:-----|:-----|:----:|:--------:|:---------|
| 🗄️ 数据管道部 | `src/data/` | ✅ | 3 | [HANDOVER](06-departments/01-data/HANDOVER.md) |
| 🎯 辩论引擎部 | `src/debate/` | ✅ | 2 | [HANDOVER](06-departments/02-debate-engine/HANDOVER.md) |
| 🤖 AI Agent 架构部 | `src/agents/` + `src/core/` | ✅ | 3 | [HANDOVER](06-departments/03-ai-agents/HANDOVER.md) |
| 🧠 记忆系统部 | `src/memory/` | ✅ | 1 | [HANDOVER](06-departments/04-memory-systems/HANDOVER.md) |
| 🛡️ 风控管理部 | `src/risk/` | ✅ | 0 | [HANDOVER](06-departments/05-risk-management/HANDOVER.md) |
| 💹 交易执行部 | `src/trader/` | ✅ | 0 | [HANDOVER](06-departments/06-trading/HANDOVER.md) |
| 🔬 回测研究部 | `src/backtest/` | ✅ | 0 | [HANDOVER](06-departments/07-backtesting/HANDOVER.md) |
| 🌐 后端 API 部 | `backend/` | ✅ | 2 | [HANDOVER](06-departments/08-backend-api/HANDOVER.md) |
| 🎨 前端部 | `frontend/` | ✅ | 1 | [HANDOVER](06-departments/09-frontend/HANDOVER.md) |
| ⚙️ 基础设施部 | `src/utils/` | ✅ | 5 | [HANDOVER](06-departments/10-infrastructure/HANDOVER.md) |
| 🔄 质量保障部 | `.github/workflows/` + CI 文档 | 🟢 | 2 | [HANDOVER](06-departments/11-quality-assurance/HANDOVER.md) |

**全代码库开放债务**: 27 条（紧急指数 4.0/10）→ [跨部门债务](06-departments/00-cross-cutting/DEBT.md)

---

## 🎯 当前跨部门优先级

> **2026-06-23 重排** — 基于 8 月底出国截止日期倒推。简历提交 9 月初。
> **核心约束**：爸妈用 A 股，你看 A 股 + 美股。
> **完整时间线**：见 [ROADMAP.md](../00-overview/ROADMAP.md)「按 8 月底倒排的优先级」节。

### P0 — 实盘命脉（8 月中旬前完成）

| 优先级 | 事项 | 牵头部门 | 预估 |
|:------:|:-----|:---------|:----:|
| 🔥 P0 | **YahooFinanceSource Provider** — 美股数据源（K 线+基本面+Provider Protocol） | 数据管道部 | ~半天 |
| 🔥 P0 | **美股前端 Tab** — 市场切换 + 美股行情 | 前端部 | ~半天 |
| 🔥 P0 | **FD-001 基本面数据接入** — ✅ 模型+Provider+辩论注入+分析师增强（数据部+辩论部完成），⬜ 后端 API 端点+前端 Tab | 数据管道部 ✅ → 辩论引擎部 ✅ → 后端 API ⬜ → 前端部 ⬜ | ~0.5 天剩余 |
| 🔥 P0 | **R4 置信度量化** — AI 建议附带明确置信度数字 | 辩论引擎部 | ~2 天 |
| 🔥 P0 | **交易复盘看板（极简版）** — TradeRecord 记录+AI推荐 vs 实际盈亏 | 后端 API 部+前端部 | ~2 天 |

### P1 — 提升赚钱概率（8 月底前）

| 优先级 | 事项 | 牵头部门 | 预估 |
|:------:|:-----|:---------|:----:|
| 🔥 P1 | **DP-004 TrustTracker 旋钮扩展** — 发言顺序/参与资格/置信度校准 | 辩论引擎部 | ~2h |
| 🔥 P1 | **DP-005 灵感官 Agent** — 高随机性反共识分析师 | AI Agent 架构部 | ~1h |
| 🔥 P1 | **DP-007 信息隔离** — StateGraph 只传结构化摘要，裁剪 state | 辩论引擎部 | ~2h |
| 🟡 P1 | **美股新闻/财报事件接入** — 重大事件提醒 | 数据管道部 | ~1 天 |
| 🟡 P1 | **TD-041 数据新鲜度标注** | 数据管道部+前端部 | ~2h |

### P2 — 出国后迭代

| 事项 | 原预估 | 原因 |
|:-----|:------:|:-----|
| DP-006 镜子反思 | ~3h | 美观但不致命 |
| UI Phase 2~4 完整闭环 | ~14h | 到国外安顿后迭代 |
| FD-003/004 供应链图谱 | ~5-7 天 | 有更好，没有也能炒 |
| Phase 3 实盘下单 | — | 先熟悉当地券商合规 |
| orchestrator.py 拆分 | — | 重构，不影响功能 |

各部门的详细下一步 → 看各自 `HANDOVER.md` 的"下一步优先级"节。

---

## 关键设计决策（跨部门）

### 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` / `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误
4. **五同步原则** — 代码 + 测试 + 文档 + 债务日志 + **引用清理**同步更新
5. **Agent 输出结构化** — 含评分/证据/置信度，非纯文本
6. **LLMService 调用走 `LLMConfig`** — 不硬编码 temperature/max_tokens

### AgentResult 泛型化

```python
# 向后兼容（已有代码不变）
result = AgentResult(data={"key": "val"})

# 新写法（类型化输出，Pyright 可静态校验）
result = AgentResult[NewsOutput](data=NewsOutput(...))
result.data.summary  # Pyright 可校验 ✅
```

---

## 工作流优化建议

### 已知效率问题

| 问题 | 修复方案 | 状态 |
|:----|:---------|:----:|
| 质量修复循环过多 | PostWrite hook 自动 `ruff check --fix` | ✅ 已配置 |
| pandas 类型反复 | 必须 `str(row["col"])` 显式转换 | ✅ 已记录 |
| CI 红着没人修 | Batch Loop 收尾前自动跑 `ruff check .` + `pyright src/` | ✅ |
| Windows torch crash | `__init__.py` 惰性导入 | ✅ 已解 |
| 手动 make check 跑全量测试太慢 + Windows 无 make | `scripts/check.py` 跨平台替代 + 智能按变更选测试（~40s 日常，~3min 全量子集） | ✅ 2026-06-23 |

### pandas 类型模式（必须遵守）

```python
# ❌ 错误
StockInfo(code=row["code"], name=row["name"])

# ✅ 正确
StockInfo(code=str(row["code"]), name=str(row["name"]))
StockQuote(price=float(row["最新价"]), volume=int(row["成交量"]))
```

---

## 7. 常见问答

**Q：AgentResult 改成 BaseModel 后，现有测试需要改吗？**
A：不需要。`data: dict | T = Field(default_factory=dict)` 确保向后兼容。

**Q：集成测试为什么跳过？**
A：代理环境屏蔽东方财富 API，`urllib.request.urlopen(..., timeout=3)` 检测失败时自动跳过。CI 环境正常跑。

**Q：我要进某个部门工作，先看什么？**
A：`docs/06-departments/{id}/ROLE.md` → 了解角色 → `STANDARDS.md` → 技术规范 → `HANDOVER.md` → 当前状态 → `DEBT.md` → 债务。

**Q：WORKFLOW.md 怎么变这么短了？**
A：从 1047 行拆成了 4 份聚焦文档。索引在 [WORKFLOW.md](WORKFLOW.md)，启动看 [workflow/STARTUP.md](workflow/STARTUP.md)，干活看 [workflow/DEVELOPMENT.md](workflow/DEVELOPMENT.md)，收尾看 [workflow/CLOSING.md](workflow/CLOSING.md)，出问题看 [workflow/EMERGENCIES.md](workflow/EMERGENCIES.md)。

---

> **最后更新**：2026-07-23 | FD-001 Step 1 财务指标数据模型上线 + 文档同步对齐

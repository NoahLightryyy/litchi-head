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
| **最新提交** | `8025fb5` — docs: 10 部门体系上线 + WORKFLOW 按阶段拆分 + 全文档同步 |
| **全量测试** | 945 collected, 全部通过 ✅ |
| **Pyright** | src/ 0 errors, backend/ 0 errors ✅ |
| **CI 状态** | 🔴 → [CI 治理部](06-departments/11-ci-governance/HANDOVER.md) |

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
| ⚙️ 基础设施部 | `src/utils/` | ✅ | 7 | [HANDOVER](06-departments/10-infrastructure/HANDOVER.md) |
| 🔄 CI 治理部 | `.github/workflows/` | 🔴 | 2 | [HANDOVER](06-departments/11-ci-governance/HANDOVER.md) |

**全代码库开放债务**: 30 条（紧急指数 4.5/10）→ [跨部门债务](06-departments/00-cross-cutting/DEBT.md)

---

## 🎯 当前跨部门优先级

| 优先级 | 事项 | 牵头部门 |
|:------:|:-----|:---------|
| 1 🔴 | **TD-038 密钥管理** — `.env` 明文 API Key 修复 | 基础设施部 |
| 2 🟡 | **TD-039 API 速率限制** — debate/run 限流 | 后端 API 部 |
| 3 🟡 | **TD-040 LLM fallback 链** — DeepSeek→OpenAI 自动降级 | 基础设施部 |
| 4 🟡 | **TD-041 数据新鲜度标注** — 采集时间戳 + 前端展示 | 数据管道部 + 前端部 |
| 5 🟢 | **orchestrator.py 拆分** — 1622 行 → orchestrator/nodes/ | 辩论引擎部 |
| 6 🟢 | **WORKFLOW 拆分验收** — 4 文件结构运行一段时间确认无遗漏 | 基础设施部 |
| 7 🔴 | **CI-001 修复** — 18/20 连红，需获取 GH Actions 日志定位根因 | CI 治理部 |

各部门的详细下一步 → 看各自 `HANDOVER.md` 的"下一步优先级"节。

---

## 关键设计决策（跨部门）

### 技术红线

1. **所有 LLM 调用必经 `src/utils/llm.py`** — 不得直接实例化 `ChatDeepSeek` / `ChatOpenAI`
2. **Pydantic 作为模块间数据契约** — `@dataclass` 仅限模块内部，跨模块传递用 `BaseModel`
3. **类型注解必须完整** — Pyright basic mode 零错误
4. **四同步原则** — 代码 + 测试 + 文档 + 债务日志同步更新
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

> **最后更新**：2026-06-21 | WORKFLOW 按阶段拆分 + 11 部门体系全面接入 + 所有架构引用清理

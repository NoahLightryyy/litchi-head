# litchi-head — AI 项目指令

> 多智能体投资决策平台（LangGraph + DeepSeek）
> 当前阶段：Phase 1 MVP 期（data → debate 接驳完成）

---

## 核心规则

1. **会话启动**：执行 `/resume-session` Skill（项目级），或手动读取 `docs/01-guides/HANDOVER.md` §2+§5 + 最新工作日志
2. **三同步原则**：代码 + 文档 + 债务日志，改一个必须改全部
3. **发现债务必登记** — 使用 `docs/01-guides/debt/TEMPLATE.md` 模板
4. **每次会话结束必须更新**：AI 工作日志 + 债务日志（如有变更）
5. **Batch Loop 模式**（用户指方向 → 我自动跑）：见下方「Batch Loop 模式」节
6. **上下文耗尽自动交接**：检测到上下文窗口接近上限时，立即执行交接流程（更新日志+债务+看板+提交），不继续推进新工作
7. **模型策略**：日常用 `deepseek-chat`（快速，无思考），复杂任务才切 `deepseek-v4-pro`（推理）。见下方「模型策略」节。

## 技术栈关键约定

- **Pydantic** `BaseModel` — 所有模块间数据传输（见 ADR-001）
- **LangGraph** `StateGraph` — Agent 编排（见 ADR-002）
- **DeepSeek-Chat** — 主力 LLM，OpenAI 为 fallback（见 ADR-007）
- **类型注解必须完整** — Pyright basic mode 零错误通过
- **`src/utils/llm.py`** — 所有 LLM 调用必经此层，不得直接实例化 ChatDeepSeek

## 项目文档索引（新结构）

> `docs/` 已按「受众 × 生命周期」重组。旧路径仍可通过 `.legacy` 目录访问。

| 文档 | 位置 |
|------|------|
| 🏠 项目总览 | `docs/00-overview/OVERVIEW.md` |
| 📐 AI 工作流程 | `docs/01-guides/WORKFLOW.md` |
| 📐 会话交接 | `docs/01-guides/HANDOVER.md` |
| 📐 环境配置 | `docs/01-guides/ENVIRONMENT.md` |
| 🐛 债务路由 | `docs/01-guides/debt/ROUTER.md` |
| 🐛 债务模板 | `docs/01-guides/debt/TEMPLATE.md` |
| 🏛️ 跨模块 ADR | `docs/05-decisions/README.md` |
| 🔧 **模块规格（核心）** | `docs/03-modules/` → 辩论引擎 → `02-debate-engine/` |
| 📋 产品需求 | `docs/02-requirements/` |
| 📋 AI 工作日志 | `docs/04-changelog/logs/` |
| 🗄️ 归档 | `docs/99-archive/` |

## 模型策略（快慢分离）

| 模型 | 定位 | 思考模式 | 适用场景 |
|------|------|:---:|------|
| `deepseek-chat` | **默认**（日常开发） | ❌ 无 | 代码编辑、Git、文件读写、简单问答、文档更新 |
| `deepseek-v4-pro` | 按需切换（复杂任务） | ✅ 推理 | 架构设计、根因分析、复杂重构、安全审查、多模块影响评估 |

```bash
# 日常开发（Windows 用户环境变量，默认值）
ANTHROPIC_MODEL=deepseek-chat

# 遇到复杂任务时，临时改为 deepseek-v4-pro，重启 Claude Code
```

> **原则**：规则和 Skill 越多，越需要关闭默认思考——推理模型会穷举遍历所有规则的交叉影响，即使任务只涉及其中一个。

## Batch Loop 模式

用户上班指方向后（或不说方向让 AI 自动推进），走以下流程：

```
你上班或说方向（一句/两句）
  → 我自动跑一个 Batch:
      ├── 恢复上下文（resume-session）           ← 全自动
      ├── 按优先级拆任务成原子 todo               ← 拆完给你看一眼
      ├── 逐个实现（TDD → 代码 → 测试）           ← 自动，卡决策点停
      ├── 遇到方向性决策 → 停下来问你             ← 必须停
      ├── 完成一个原子功能 → 叫你审               ← 必须停
      └── 重复直到你说停或上下文耗尽
你下班/说"写进文档"
  → 我自动更新日志 + 债务 + 看板 + 提交           ← 全自动
```

**不需要停的事**（我自动处理）：
- 测试没过 → 自己修
- lint 没过 → hook 自动修
- 小重构 → 顺手做
- 技术细节选择（A 库还是 B 库）

**必须停的事**：
- 功能做什么/不做什么
- 字段设计、优先级判断
- 跟钱/风险相关的默认值
- 是否需要写新文档

## 上下文耗尽自动交接

> **触发条件**：上下文窗口估计剩余 < 20%（约 20K tokens），或我发现输出质量下降（回信变短、遗忘早期指令）。

> **纪律**：检测到将耗尽 = 立即停，不推进新工作。

### 交接流程（约 5 分钟）

```
┌─ 1. 更新工作日志 ─────────────────────────────────┐
│  docs/04-changelog/logs/YYYY-MM-DD/YYYY-MM-DD-N.md
│  → 记录本次做了什么、改了哪些文件、测试结果           │
│  → 标记「上下文耗尽，需续接」                        │
├─ 2. 更新债务日志 ─────────────────────────────────┤
│  docs/01-guides/debt/ROUTER.md → 对应类型文件      │
│  → 如有新增债务，按模板登记                          │
├─ 3. 更新时间线文档 ───────────────────────────────┤
│  docs/00-overview/ROADMAP.md (看板)                 │
│  docs/01-guides/HANDOVER.md §2 + §5               │
│  → 同步当前阶段、完成度、下一步优先级                  │
├─ 4. 提交当前工作 ──────────────────────────────┤
│  git add -A && git commit -m "..."              │
│  → 提交信息注明「context-exhausted-handover」    │
│  → **不 push**（等你确认）                       │
├─ 5. 通知你继续 ────────────────────────────────┤
│  → 输出提示：「上下文已耗尽，交接文档就绪，         │
│     开新会话后执行 /resume-session 继续」          │
└──────────────────────────────────────────────────┘
```

> **在新会话中**：`/resume-session` 会自动检测到上次标记了「上下文耗尽」，
> 额外加载上一会话的完整上下文恢复信息。

## 快速命令

```bash
make install   # 安装依赖
make check     # 一键检查（lint + type + test）
make lint      # Ruff 代码风格
make type      # Pyright 类型检查
make test      # Pytest 测试

# Docker 开发环境
make docker-build   # 构建开发镜像
make docker-test    # 在容器中跑测试
make docker-check   # 在容器中全量检查
make docker-shell   # 进入容器 bash
```

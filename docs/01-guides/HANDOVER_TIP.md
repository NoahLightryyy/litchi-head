# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP + Phase R 实盘加固     Python 测试: 1731 passed / 1754 collected ✅
债务: 31 条开放表项（紧急指数 5.6/10）
代码库: 11 部门体系（docs/06-departments/）
数据源: 零造假数据 ✅ | 四源架构（akshare/adata/zzshare/fallback）
数据链路: K线 KR-3B-2 ✅ | 首页市场双源/五态联合验收 ✅ | 健康快照原子性 ✅
```

## 🏢 部门一览

| 部门 | 代码 | 债务 | 状态 |
|:-----|:-----|:----:|:----:|
| 🗄️ 数据管道部 | `src/data/` + `src/data/indicators/` | 4 | 🟡 |
| 🎯 辩论引擎部 | `src/debate/`+`src/risk/` | 3 | 🟡 |
| 🤖 AI Agent 架构部 | `src/agents/`+`src/core/` | 3 | ✅ |
| 🧠 记忆系统部 | `src/memory/` | 2 | 🟡 |
| 🛡️ 风控管理部 | `src/risk/` | 0 | ✅ |
| 💹 交易执行部 | `src/trader/` | 0 | ✅ |
| 🔬 回测研究部 | `src/backtest/` | 0 | ✅ |
| 🌐 后端 API 部 | `backend/` | 2 | 🟡 |
| 🎨 前端部 | `frontend/` | 1 | ✅ |
| ⚙️ 基础设施部 | `src/utils/` | 5 | 🟡 |

每个部门 = 👤 ROLE.md + 📐 STANDARDS.md + 📋 HANDOVER.md + 🐛 DEBT.md
→ `docs/06-departments/{id}/`

## 🎯 当前优先级

| 优先级 | 事项 | 牵头部门 |
|:------:|:-----|:---------|
| 1 ⏸️ | **转段选择** — 继续 KR-4～6，或先做最小效果验证 | 用户决策 |
| 2 ⏸️ | **BW-052 健康恢复语义** — 历史失败后何时恢复当前健康 | 用户决策 + 基础设施部 |
| 3 🟢 | **BW-031/032 RED + BW-053 QA 矩阵** — 不冻结新字段、不改变资金/风险默认值 | Agent/风控/QA |
| 4 🧪 | **TD-072 20 日同分钟量能基线** — 继续自然暖机和影子验证 | 数据管道部 |

## 🔁 Loop 入口

新聊天窗口直接发送：

```text
启动 litchi-head loop
```

AI 将自动读取上下文、选择最高优先级、推进一个原子任务、跑相关验证并写工作日志。

只做收尾：

```text
收尾 loop
```

## 📁 你要干嘛 → 找哪个部门

| 你要干嘛 | 牵头部 | 先看 |
|:---------|:-------|:-----|
| 修数据采集/缓存 | 🗄️ 数据管道部 | `docs/06-departments/01-data/ROLE.md` |
| 改辩论流程/Agent 编排 | 🎯 辩论引擎部 | `docs/06-departments/02-debate-engine/ROLE.md` |
| 加新 Agent/改通信协议 | 🤖 AI Agent 架构部 | `docs/06-departments/03-ai-agents/ROLE.md` |
| 调记忆/知识库 | 🧠 记忆系统部 | `docs/06-departments/04-memory-systems/ROLE.md` |
| 改风控逻辑 | 🛡️ 风控管理部 | `docs/06-departments/05-risk-management/ROLE.md` |
| 改交易执行/仓位计算 | 💹 交易执行部 | `docs/06-departments/06-trading/ROLE.md` |
| 调回测引擎 | 🔬 回测研究部 | `docs/06-departments/07-backtesting/ROLE.md` |
| 改 API 路由/错误处理 | 🌐 后端 API 部 | `docs/06-departments/08-backend-api/ROLE.md` |
| 改前端展示/交互 | 🎨 前端部 | `docs/06-departments/09-frontend/ROLE.md` |
| 改 LLM/Config/日志 | ⚙️ 基础设施部 | `docs/06-departments/10-infrastructure/ROLE.md` |
| 跨多个部门 | 🔄 跨部门 | `docs/06-departments/00-cross-cutting/HANDOVER.md` |

## 🚀 快速命令

```bash
cd C:/Users/ASUS/Desktop/litchi-head-backend
python scripts/check.py          # 智能检查（推荐）
python scripts/check.py --full   # 全量子集
make check                       # Linux/macOS
pip install -e ".[dev]"          # 安装依赖
python -m uvicorn backend.main:app --port 8000   # 启动后端
cd frontend && pnpm dev                          # 启动前端
```

## 📖 文档快速索引

| 你要干嘛 | 看哪个文件 |
|:---------|:-----------|
| 完整工作流程（给 AI） | [WORKFLOW.md](WORKFLOW.md) |
| Codex Batch Loop 自动化 | [LOOP.md](LOOP.md) |
| 完整交接文档（给 AI） | [HANDOVER.md](HANDOVER.md) |
| 债务路由 | [debt/ROUTER.md](debt/ROUTER.md) |
| 部门体系总览 | `docs/06-departments/README.md` |
| 全局进度看板 | `docs/00-overview/ROADMAP.md` |
| 环境配置 | [ENVIRONMENT.md](ENVIRONMENT.md) |
| 技术栈 | `docs/00-overview/TECH_STACK.md` |

---
> 每次会话结束时 AI 自动更新本页。如有出入请提醒。
> **最后更新**：2026-08-30 | 后端 BW-052 / TD-080 交接与推送前收尾

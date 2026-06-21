# ⚡ 快速交接卡 — 扫一眼就知道做到哪了

> **给人类看的**。完整的交接文档在 [HANDOVER.md](HANDOVER.md)（给 AI 读的）。

## 📊 当前状态

```
阶段: Phase 1 MVP + Phase R 实盘加固     Python 测试: 945 ✅
债务: 26 条开放（紧急指数 4.5/10）
代码库: 10 部门体系（docs/06-departments/）
数据源: 零造假数据 ✅ | 四源架构（akshare/adata/zzshare/fallback）
```

## 🏢 部门一览

| 部门 | 代码 | 债务 | 状态 |
|:-----|:-----|:----:|:----:|
| 🗄️ 数据管道部 | `src/data/` | 3 | ✅ |
| 🎯 辩论引擎部 | `src/debate/`+`src/risk/` | 2 | ✅ |
| 🤖 AI Agent 架构部 | `src/agents/`+`src/core/` | 3 | ✅ |
| 🧠 记忆系统部 | `src/memory/` | 1 | ✅ |
| 🛡️ 风控管理部 | `src/risk/` | 0 | ✅ |
| 💹 交易执行部 | `src/trader/` | 0 | ✅ |
| 🔬 回测研究部 | `src/backtest/` | 0 | ✅ |
| 🌐 后端 API 部 | `backend/` | 2 | ✅ |
| 🎨 前端部 | `frontend/` | 1 | ✅ |
| ⚙️ 基础设施部 | `src/utils/` | 7 | ✅ |

每个部门 = 👤 ROLE.md + 📐 STANDARDS.md + 📋 HANDOVER.md + 🐛 DEBT.md
→ `docs/06-departments/{id}/`

## 🎯 当前优先级

| 优先级 | 事项 | 牵头部门 |
|:------:|:-----|:---------|
| 1 ✅ | TD-038 密钥安全已修复 | 基础设施部 |
| 2 🟡 | TD-039 API 速率限制 | 后端 API 部 |
| 3 🟡 | TD-040 LLM fallback 链 | 基础设施部 |
| 4 🟡 | TD-041 数据新鲜度标注 | 数据管道部 + 前端部 |
| 5 🟢 | orchestrator.py 拆分（1622 行） | 辩论引擎部 |

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
cd e:/litchi-head
make check        # lint + type + test 一键完成
make install      # 安装依赖
python -m uvicorn backend.main:app --port 8000   # 启动后端
cd frontend && pnpm dev                          # 启动前端
```

## 📖 文档快速索引

| 你要干嘛 | 看哪个文件 |
|:---------|:-----------|
| 完整工作流程（给 AI） | [WORKFLOW.md](WORKFLOW.md) |
| 完整交接文档（给 AI） | [HANDOVER.md](HANDOVER.md) |
| 债务路由 | [debt/ROUTER.md](debt/ROUTER.md) |
| 部门体系总览 | `docs/06-departments/README.md` |
| 全局进度看板 | `docs/00-overview/ROADMAP.md` |
| 环境配置 | [ENVIRONMENT.md](ENVIRONMENT.md) |
| 技术栈 | `docs/00-overview/TECH_STACK.md` |

---
> 每次会话结束时 AI 自动更新本页。如有出入请提醒。
> **最后更新**：2026-06-21 | 部门体系全面接入

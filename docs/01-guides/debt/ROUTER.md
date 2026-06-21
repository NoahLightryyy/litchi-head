# 🐛 技术债务路由

> **债务已按部门拆分**。每个部门的债务清单在各自 `docs/06-departments/{id}/DEBT.md` 中。
> 本文件只保留路由索引和全局仪表盘。

---

## 📂 按部门索引

| 部门 | 债务清单 | 开放债务数 |
|:-----|:---------|:----------:|
| 🔄 [跨部门](../../06-departments/00-cross-cutting/DEBT.md) | 影响全代码库的债务 | **5+3** |
| 🗄️ [数据管道部](../../06-departments/01-data/DEBT.md) | Provider / Collector / 数据模型 | **3** |
| 🎯 [辩论引擎部](../../06-departments/02-debate-engine/DEBT.md) | 编排器 / 信任度 / 反射 | **2** |
| 🤖 [AI Agent 架构部](../../06-departments/03-ai-agents/DEBT.md) | BaseAgent / MasterAgent / 协议 | **3** |
| 🧠 [记忆系统部](../../06-departments/04-memory-systems/DEBT.md) | KnowledgeBase / MemoryStore | **1** |
| 🛡️ [风控管理部](../../06-departments/05-risk-management/DEBT.md) | 风控编排 / 风险画像 | **0** |
| 💹 [交易执行部](../../06-departments/06-trading/DEBT.md) | 交易模型 / 桥接 | **0** |
| 🔬 [回测研究部](../../06-departments/07-backtesting/DEBT.md) | 回测引擎 / 绩效指标 | **0** |
| 🌐 [后端 API 部](../../06-departments/08-backend-api/DEBT.md) | 路由 / 技术指标 | **2** |
| 🎨 [前端部](../../06-departments/09-frontend/DEBT.md) | 组件 / 类型 / 构建 | **1** |
| ⚙️ [基础设施部](../../06-departments/10-infrastructure/DEBT.md) | LLM / Config / CostTracker | **6** |

**总计：25 条开放债务（紧急指数 4.5/10）**

---

## 仪表盘

```
开放债务: 25 条    已关闭: 36 条
紧急指数: 4.5 / 10
```

### 按严重度分布

| 严重度 | 数量 | 说明 |
|:------:|:----:|:------|
| 🟡 Moderate | 13 | 测试、功能缺失、性能 |
| 🟢 Low | 12 | 代码质量、小修复 |

### 按部门分布

```
基础设施部: 6 条 ← 最多（LLM fallback/config）
跨部门:     5+3 条 ← 全代码库级
数据管道部: 3 条
AI Agent 部:3 条
辩论引擎部: 2 条
后端 API 部:2 条
前端部:     1 条
记忆系统部: 1 条
风控部:     0 条 ✅
交易部:     0 条 ✅
回测部:     0 条 ✅
```

---

## 快速新增

新增债务时：

1. 判断债务属于哪个部门（改哪个 `src/{dir}/` 的代码）
2. 在该部门的 `DEBT.md` 末尾追加
3. 如果是跨部门债务，加在 `00-cross-cutting/DEBT.md`
4. **不用**更新本路由（本文件自动从部门文件汇总）

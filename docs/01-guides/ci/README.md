# 🔄 CI 治理体系

> **目的**：确保 CI 永远不红。红了就是最高优先级，不修好不推新代码。
>
> 归属部门：[⚙️ 基础设施部](../../06-departments/10-infrastructure/ROLE.md)

---

## 📊 当前 CI 看板

| 指标 | 值 |
|:-----|:----|
| GitHub Actions 最新状态 | ⛔ 11/12 连红（#33~#44 仅 #36 绿） |
| 最近一次绿色 | Run #36 — `chore: 上下文路由架构优化`（2026-06-17） |
| CI 债务 | [CI 债务清单](ISSUES.md) |

> **状态实时查看**：[GitHub Actions](https://github.com/NoahLightryyy/litchi-head/actions)

---

## 📑 文档索引

| 文档 | 读给谁 | 内容 |
|:-----|:-------|:-----|
| [STANDARDS.md](STANDARDS.md) | 全部开发者 | CI 检查清单、门禁定义、绿/黄/红标准 |
| [WORKFLOW.md](WORKFLOW.md) | 全部开发者 | CI 失败处理工作流——从发现到闭环 |
| [CHECKS.md](CHECKS.md) | 全部开发者 | 推送前本地检查清单 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | AI + 开发者 | CI 常见失败根因与修复方案（持续积累） |
| [ISSUES.md](ISSUES.md) | 基础设施部 | CI 问题追踪日志（类似债务，专用） |
| [HANDBOOK.md](HANDBOOK.md) | 基础设施部 | CI 维护手册（改 workflow、加检查项） |

---

## ⚙️ 核心原则

### 1. CI 红 = 最高优先级

> 任何会话中，如果 CI 是红的：
> 1. 先修 CI，再做新功能
> 2. 修完验证通过，继续原工作
> 3. 记录根因到 `TROUBLESHOOTING.md`

### 2. 本地拦截优先

> 能在本地 `make check` 跑过的，不要让 CI 来抓。
> - 每次提交前：`make check`
> - 基础设施部负责维护 pre-push hook（参见 [HANDBOOK.md](HANDBOOK.md#pre-push-hook)）

### 3. 四同步延伸到 CI

> 修 CI 同样遵循「代码 + 测试 + 文档 + 债务日志」四同步：
> - 修复 CI 的代码改动
> - 更新 `TROUBLESHOOTING.md` 记录根因
> - CI 本身也算一次可跟踪的工作项

### 4. 不积累 CI 债

> - CI 红了 → 本次工作多一个 todo：修 CI
> - 修不了的 → 登记为 CI 债务（`ISSUES.md`）
> - 连续 3 次红 → 自动触发审视

---

## 🔗 关联系统

| 系统 | 关系 |
|:-----|:-----|
| [WORKFLOW.md](../WORKFLOW.md) | Batch Loop 收尾必须跑 CI 健康自检 |
| [HANDOVER.md](../HANDOVER.md) | 🏢 各部门一览包含 CI 状态 |
| [基础设施部 DEBT.md](../../06-departments/10-infrastructure/DEBT.md) | CI 相关技术债务 |
| [CLAUDE.md](../../../CLAUDE.md) | Batch Loop、CI 健康自检纪律 |

---

> **最后更新**: 2026-06-21 | CI 治理体系创建

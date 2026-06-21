---
department: AI Agent 架构部
---

# 🐛 AI Agent 架构部债务清单

> 本文件只列 AI Agent 架构部（`src/agents/`, `src/core/`）的债务。

---

## 开放债务

| ID | 标题 | 严重度 | 类型 | 状态 |
|:---|:-----|:------:|:----|:----|
| TD-003 | MessageRouter 纯内存存储，进程重启全部丢失 | 🟡 moderate | 功能缺失 | 📋 待评估 |
| TD-006 | EvidenceItem 无校验逻辑 | 🟢 low | 代码质量 | 📋 待评估 |
| TD-050 | XiaoZhiAgent 无 LLM 错误路径测试 | 🟡 moderate | 测试覆盖 | 📋 待评估 |

## 已关闭债务

| ID | 标题 | 修复日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-002 | AgentResult 缺泛型 | 2026-06-07 | Pydantic BaseModel + Generic[T]，88 tests |
| TD-014 | AgentContext 缺辩论槽位 | 2026-06-07 | +3 字段 +7 测试 |

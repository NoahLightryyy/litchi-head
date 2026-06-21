---
department: 辩论引擎部
---

# 🐛 辩论引擎部债务清单

> 本文件只列辩论引擎部（`src/debate/`, `src/risk/`）的债务。

---

## 开放债务

| ID | 标题 | 严重度 | 类型 | 状态 |
|:---|:-----|:------:|:----|:----|
| TD-018 | 编排层缺少成本优化（~15 次 LLM 调用/辩论） | 🟡 moderate | 性能 | 📋 待评估 |
| TD-017 | 缺少反思/学习闭环（M2 交易后反思） | 🟢 low | 功能缺失 | 📋 待评估 |

## 已关闭债务

| ID | 标题 | 修复日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-021 | 16 处 `except Exception: pass` 静默吞异常 | 2026-06-17 | 全部改为 logger.warning |
| TD-022 | collect_data_node 变量未初始化 | 2026-06-17 | 代码已有初始化，无需修改 |
| TD-042 | _run_rebuttal/_run_independent_review 静默吞异常 | 2026-06-18 | +logger.exception() |
| TD-044 | reflection 生成/决策记忆加载静默失败 | 2026-06-18 | +logger.exception() |
| TD-045 | trust 写/读/load_outcomes 丢失异常细节 | 2026-06-18 | +str(e) 补全日志 |
| TD-048 | collect_data_node + 记忆节点日志升级 | 2026-06-18 | 6 处 logger.warning→logger.exception |
| TD-043 | risk/orchestrator 异常完全丢弃 | 2026-06-18 | +logger.exception() + session_id |

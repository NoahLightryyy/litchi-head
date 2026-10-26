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

###### RESEARCH-FOLLOWUP-TYPE-001 未完成补证破坏周期限制字段类型

| 属性 | 值 |
|---|---|
| 分类 | `[bug]` `severity:moderate` `module:agents` `impact:research` |
| 发现日期 | 2026-10-26 |
| 发现人 | 入场计划链路核查 |
| 状态 | ✅ 已修复 |
| 本金估算 | 本轮完成 |
| 日利息 | 补证失败可能升级为整个流派结果校验失败 |
| 实盘影响 | 已有分析不能呈现，周期观点丢失 |
| 触发场景 | 检索失败、复核失败或时间预算不足，research_queries仍非空 |
| 用户能发现吗 | 会看到分析失败，不知道是本地字段类型错误 |

**描述／具体问题**：model_copy不重新验证字段，旧代码把limitations字符串展开成字符列表。
**利息分析**：临时补证缺口变成模型契约错误，掩盖可读的初稿。
**修复结果**：保持字符串，原缺口与追加提示总长不超过600，仍标insufficient。
真实run的三个mock分支和AgentAnalysis JSON往返回归通过；该测试文件28项通过。

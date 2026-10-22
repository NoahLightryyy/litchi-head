---
department: 交易执行部
---

# 🐛 交易执行部债务清单

> 本文件只列交易执行部（`src/trader/`）的债务。

---

## 开放债务

新增待评估项见下文。

## 已关闭债务

（暂无已关闭债务）

###### PC-AUDIT-002 交易桥比例语义及动作方向未统一

| 属性 | 值 |
|------|-----|
| **分类** | `[可靠性]` `severity:Moderate` `module:06-trading` `impact:research` |
| **发现日期** | 2026-10-18 |
| **发现人** | 并行盘点 / 主窗口复核 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼0.5–1人日，待复现校准 |
| **日利息** | 被直接复用后会放大错误结论 |
| **实盘影响** | 复用为执行数量可能错算仓位或买卖方向 |
| **触发场景** | quantity_pct定义为总资金占比，bridge又乘总仓位；非hold写buy |
| **用户能发现吗** | 输出数量看似合理，用户未必发现 |

**描述**：src/trader/models.py::ExecutionStep与src/trader/bridge.py::trade_plan_to_records；固定整百股且无费用预留。 本轮只读审查，未运行行为复现，也未修复。

**具体问题**：quantity_pct定义为总资金占比，bridge又乘总仓位；非hold写buy。

**利息分析**：新政策/本金闭环不能依赖未经验证的旧输出；新增功能开发前需确定隔离或修复。

**修复方向**：冻结比例/方向语义，验证sell和分步仓位；真实计算器独立接证券单位和费用。

关联：[能力盘点](../../02-requirements/differentiation/CAPABILITY_INVENTORY.md)。

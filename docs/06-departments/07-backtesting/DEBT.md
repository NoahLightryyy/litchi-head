---
department: 回测研究部
---

# 🐛 回测研究部债务清单

> 本文件只列回测研究部（`src/backtest/`）的债务。

---

## 开放债务

新增待评估项见下文。

## 已关闭债务

| ID | 标题 | 修复日期 | 修复说明 |
|:---|:-----|:--------|:---------|
| TD-046 | _calc_holding_days except:pass | 2026-06-18 | +logger.warning(entry/exit/e) |

###### PC-AUDIT-001 回测卖出收入与实际卖出数量口径不一致

| 属性 | 值 |
|------|-----|
| **分类** | `[可靠性]` `severity:Moderate` `module:07-backtesting` `impact:research` |
| **发现日期** | 2026-10-18 |
| **发现人** | 并行盘点 / 主窗口复核 |
| **状态** | `🆕 待评估` |
| **本金估算** | ∼0.5–1人日，待复现校准 |
| **日利息** | 被直接复用后会放大错误结论 |
| **实盘影响** | 请求卖出量超过持仓时可能高估收益，影响评测可信度 |
| **触发场景** | BacktestEngine.run出场：收入用trade.quantity，扣仓用min(quantity,持仓) |
| **用户能发现吗** | 单看收益报告不易发现 |

**描述**：src/backtest/engine.py:132–140；另max_single_position未用于引擎约束。 本轮只读审查，未运行行为复现，也未修复。

**具体问题**：BacktestEngine.run出场：收入用trade.quantity，扣仓用min(quantity,持仓)。

**利息分析**：新政策/本金闭环不能依赖未经验证的旧输出；新增功能开发前需确定隔离或修复。

**修复方向**：以实际成交量计算现金与盈亏，测试超量卖出、入场未成交和部分退出。

关联：[能力盘点](../../02-requirements/differentiation/CAPABILITY_INVENTORY.md)。

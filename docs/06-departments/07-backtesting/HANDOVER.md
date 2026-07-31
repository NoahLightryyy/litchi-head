---
department: 回测研究部
codebase: src/backtest/
last_updated: 2026-07-30 (点时复权与回测数据血缘职责确认)
---

# 🔬 回测研究部工作交接

## 当前状态

### 模块完成度

| 子系统 | 状态 | 说明 |
|:-------|:----:|:------|
| BacktestEngine 回测引擎 | ✅ | 模拟交易执行 + 持仓管理 |
| Metrics 绩效指标 | ✅ | 夏普/回撤/胜率/盈亏比/CAGR |
| BacktestConfig/Report 模型 | ✅ | 结构化回测配置和报告 |
| 辩论→回测桥接（bridge.py） | ✅ | TradeRecord → 回测信号转换 |

### 测试

| 测试集 | 测试数 |
|:-------|:------:|
| 回测模块测试 | 65 |
| 桥接适配器 | 20 |
| **合计** | **85** |

### 关键架构决策

- **无未来信息**：t 时刻只用 t 之前的数据，天然防御未来信息
- **点时复权**：技术指标只用当时可获得的因子；成交价格仍使用 RAW
- **多市覆盖**：上涨/下跌/震荡三市场景
- **行业标准一致**：夏普/回撤计算与知名库交叉验证

---

## 开放债务

当前无本部门独立债务；仍承担跨部门 TD-069/KR-6 和 TD-074。85 个测试通过证明指标和
模拟组件可用，不等于已经完成样本外、含成本的 AI 增量价值验证。

## 下一步优先级

| 优先级 | 事项 | 依赖 |
|:------:|:-----|:----:|
| 1 🥈 | **UI-2c 回测集成 RC-004** — `BacktestEngine.run()` 末尾 dispatch `BACKTEST_COMPLETED` 事件到 ResultCallbackEngine，触发 RC-004 RP-TUNE 风险参数自适应 | RC-001 核心引擎 | ~30min |
| 2 🟢 | Monte Carlo 模拟（1000 次随机回测） | 无 |
| 3 🟢 | 按市场环境分层回测报告 | 无 |
| 4 🟢 | 性能基线建立（5 年日频 ≤ 10s） | 无 |
| 🔥 | **TD-069/KR-6 点时复权回放** — 数据版本、因子版本和 `as_of` 进入报告；验证无未来因子 | 2B1 深市事件已完成；等待 2B2/2C 与 KR-6。累计快照和条款事件都不能直接回测 |

## 决策 baseline / 影子验证责任（TD-074）

完整口径见 [跨部门唯一协议](../../02-requirements/DECISION_BASELINE_AND_SHADOW_VALIDATION.md)。
回测部牵头 B0～B4 baseline 编排、配对比较、walk-forward、置信区间和市场状态分层。
报告必须同时展示预测、经济、安全和运行指标，以及完整分母、失败样本和实验版本。

---

## 关键文件索引

| 文件 | 行数 | 说明 |
|:-----|:----:|:------|
| `src/backtest/engine.py` | 234 | BacktestEngine 回测模拟引擎 |
| `src/backtest/metrics.py` | 234 | 绩效指标计算（夏普/回撤/胜率） |
| `src/backtest/models.py` | 153 | 回测数据模型 |
| `src/backtest/bridge.py` | — | 辩论→回测桥接 |
| `docs/06-departments/07-backtesting/ROLE.md` | — | 👤 回测研究部角色定义 |
| `docs/06-departments/07-backtesting/STANDARDS.md` | — | 📐 回测研究部技术规范 |

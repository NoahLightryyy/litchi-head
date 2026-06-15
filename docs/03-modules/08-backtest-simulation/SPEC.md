# 模块：回测与仿真

> 策略历史回测验证、仿真环境、绩效评估。

## 模块定义

交易策略的历史回测验证、仿真环境、绩效评估。纯计算模块，不涉及 LLM 调用。

**职责边界**：
- ✅ 历史数据上的策略回测（确定性策略）
- ✅ 绩效指标计算（收益率/夏普/最大回撤/胜率/盈亏比/CAGR）
- ✅ 持仓净值曲线模拟（逐日盯市+入场出场事件）
- ✅ 多笔交易组合回放
- ❌ 不负责 LLM 辩论场景的概率性回测（需在 debate 层完成多次采样）
- ❌ 不负责实时交易（那是交易执行模块的事）
- ❌ 不负责因子有效性验证（那是因子研究模块的事）

## 代码结构

| 文件 | 说明 |
|------|------|
| `src/backtest/__init__.py` | 模块入口，导出全部公开 API |
| `src/backtest/models.py` | 数据契约（5 个 Pydantic 模型） |
| `src/backtest/engine.py` | 回测引擎核心（BacktestEngine） |
| `src/backtest/metrics.py` | 绩效指标计算（7 个纯函数） |
| `tests/test_backtest_models.py` | 数据模型测试（5 tests） |
| `tests/test_backtest_engine.py` | 回测引擎测试 |
| `tests/test_backtest/__init__.py` | 测试辅助（空，预留） |

## 架构（当前状态）

```
TradeRecord[] + KLine[]
         │
         ▼
  ┌──────────────────┐
  │  BacktestEngine   │  逐日回放：
  │  ┌──────────────┐ │  入场建仓 → 逐日盯市 → 出场结算
  │  │ 事件索引      │ │  → 每交易日产出 PortfolioSnapshot
  │  │ 逐日事件驱动  │ │  → 累计 realized_trades
  │  │ 持仓追踪      │ │
  │  └──────────────┘ │
  └────────┬─────────┘
           ▼
  ┌──────────────────┐
  │  calculate_metrics│  纯函数聚合：Sharpe / DD / WinRate / PF / CAGR
  └────────┬─────────┘
           ▼
     BacktestReport
  ├─ config: BacktestConfig
  ├─ metrics: PerformanceMetrics
  ├─ trades: TradeRecord[]
  └─ equity_curve: PortfolioSnapshot[]
```

**设计原则**：
- 无状态引擎（方法不修改外部状态）
- 纯计算模块，不涉及 LLM 调用
- 与 debate/trader 模块解耦，只依赖 `data.models.KLine`

## 数据契约（关键模型）

| 模型 | 字段 | 说明 |
|:-----|:-----|:-----|
| `BacktestConfig` | initial_capital, commission_rate, slippage, max_single_position | 回测运行参数 |
| `TradeRecord` | ticker, direction, entry/exit_date, entry/exit_price, quantity, pnl, holding_days, exit_reason | 单笔完整交易（入场→出场） |
| `PortfolioSnapshot` | date, total_value, cash, position_value, daily_return, cumulative_return, drawdown | 每日持仓快照 |
| `PerformanceMetrics` | total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, profit_factor, total_trades, cagr, avg_holding_days | 绩效指标体系 |
| `BacktestReport` | config, metrics, trades, equity_curve, start_date, end_date, ticker, total_days | 完整回测报告 |

## 当前实现状态

| 特性 | 状态 | 测试数 |
|:-----|:----:|:------:|
| BacktestEngine 核心 | ✅ P0 完成 | 45 tests |
| PerformanceMetrics 计算（Sharpe/DD/WinRate/PF/CAGR/年化） | ✅ 完成 | 内置 |
| PortfolioSnapshot 净值曲线生成 | ✅ 完成 | 内置 |
| TradeRecord 入场→出场完整生命周期 | ✅ 完成 | 内置 |
| LLM 辩论场景概率性回测 | ⬜ Phase 1 | — |
| 时光机压力测试 | ⬜ Phase 2 | — |
| 虚拟投资功能桥接 | ⬜ Phase 1 | — |

## 下一步

| 优先级 | 事项 | 依赖 | 预估 |
|:------:|:-----|:----|:----:|
| 🟡 P1 | **回测→辩论桥接** — TradePlan → TradeRecord 适配器，使辩论输出可直接喂入回测引擎 | debate 层就绪 | 中 |
| 🟡 P1 | **虚拟投资功能基础版** — 记录每次决策与后续走势，生成简单绩效报表 | 桥接完成 | 中 |
| ⬇️ P2 | **时光机压力测试** — 预设历史事件切片，Agent "穿越"回当时做决策 | P1 完成 | 大 |

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景

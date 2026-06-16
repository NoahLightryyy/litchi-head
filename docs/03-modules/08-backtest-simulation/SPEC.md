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
| `src/backtest/__init__.py` | 模块入口，导出全部公开 API（含桥接函数） |
| `src/backtest/models.py` | 数据契约（5 个 Pydantic 模型） |
| `src/backtest/engine.py` | 回测引擎核心（BacktestEngine） |
| `src/backtest/metrics.py` | 绩效指标计算（7 个纯函数） |
| `src/backtest/bridge.py` | **辩论←→回测桥接适配器（🆕）** |
| `tests/test_backtest_models.py` | 数据模型测试（5 tests） |
| `tests/test_backtest_engine.py` | 回测引擎测试 |
| `tests/test_backtest_bridge.py` | 桥接适配器测试（20 tests 🆕） |
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
| **辩论←→回测桥接适配器** | ✅ **完成（🆕）** | **20 tests** |
| LLM 辩论场景概率性回测 | ⬜ Phase 1 | — |
| 时光机压力测试 | ⬜ Phase 2 | — |
| 虚拟投资功能桥接 | ⬜ Phase 1 | — |

## 桥接适配器（bridge.py）

> **职责**：在 TradePlan（交易员输出）和 TradeRecord（回测引擎消费）之间转换。

### 数据流向

```
DebateResult
  └─ trader_round.trade_plan (TradePlan)
        │
        ▼
  ┌──────────────────────────┐
  │  trade_plan_to_records() │  ← 核心转换函数
  │   debate_result_to_     │  ← 高级封装（自动提取）
  │      records()          │
  └──────────┬───────────────┘
             ▼
  TradeRecord[]  ──→  BacktestEngine.run()  ──→  BacktestReport
```

### 映射规则

| TradePlan 字段 | TradeRecord 字段 | 转换逻辑 |
|:--------------|:----------------|:---------|
| `ticker` | `ticker` | 直接映射 |
| `direction` (Bullish/Bearish) | `direction` (buy/sell) | Bullish→buy, Bearish→sell, Neutral→空列表 |
| `total_position_pct × step.quantity_pct` | `position_pct` | 逐层乘法 |
| `execution_steps[].action` | `direction` | hold 跳过，其余正常 |
| 缺省 | `entry_price` | 优先显式传入，否则取 klines[0].close |
| 缺省 | `exit_price` | 优先显式传入，否则取 klines[-1].close |
| `time_horizon_days` | `holding_days` + `exit_date`（K线偏移） | 直接映射 |
| `execution_steps[].*` + TradePlan 元数据 | `trade_plan`（dict 快照） | 序列化保留原始计划 |

### 三个公开函数

1. **`trade_plan_to_records(trade_plan, klines=None, entry_price=None, exit_price=None) → list[TradeRecord]`**
   — 核心转换。TradePlan → TradeRecord。
   - Neutral 方向返回空列表
   - 空 execution_steps 抛出 ValueError

2. **`debate_result_to_records(debate_result, klines=None) → list[TradeRecord]`**
   — 高级封装。自动从 DebateResult 提取 trader_round.trade_plan 和推荐参数。

3. **`backtest_trade_plan(trade_plan, klines, config=None) → BacktestReport`**
   — 一步到位。TradePlan → 回测 → 绩效报告。
   - Neutral 方向返回空报告（0 交易）

4. **`backtest_debate_result(debate_result, klines, config=None) → BacktestReport`**
   — 辩论结果直接回测。DebateResult → 回测 → 绩效报告。

## 下一步

| 优先级 | 事项 | 依赖 | 预估 |
|:------:|:-----|:----|:----:|
| ~~🟡 P1~~ | ~~**回测→辩论桥接**~~ — ✅ **已完成（2026-06-16）** | — | 中 |
| 🟡 P1 | **虚拟投资功能基础版** — 记录每次决策与后续走势，生成简单绩效报表 | 桥接完成 | 中 |
| ⬇️ P2 | **时光机压力测试** — 预设历史事件切片，Agent "穿越"回当时做决策 | P1 完成 | 大 |

> **关联文档**：[RESEARCH.md](RESEARCH.md) — 调研背景

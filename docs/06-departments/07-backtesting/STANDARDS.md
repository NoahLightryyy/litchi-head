# 📐 回测研究部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的回测模块特定规范。

---

## 代码规范

### 回测配置

```python
# ✅ 正确：结构化配置
class BacktestConfig(BaseModel):
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100000, ge=0)
    commission_pct: float = Field(default=0.03, ge=0, le=1, description="手续费率%")
    slippage_pct: float = Field(default=0.05, ge=0, le=1, description="滑点%")
    benchmark: str | None = Field(default="000300", description="基准指数代码")
    
# ❌ 禁止：无参数化
# backtest(start="2025-01-01", end="2026-01-01")  # 手续费和滑点呢？
```

### 绩效指标计算

```python
# ✅ 正确：纯函数，输入数据→输出指标
def calculate_sharpe(returns: list[float], risk_free_rate: float = 0.03) -> float:
    """计算夏普比率"""
    excess = [r - risk_free_rate / 252 for r in returns]
    return float(np.mean(excess) / np.std(excess) * np.sqrt(252))

def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """计算最大回撤 %"""
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / peak
    return float(np.min(drawdown))
    
# ❌ 禁止：全局状态影响计算结果
class MetricsCalculator:
    _cache = {}  # 禁止：全局状态
    def calculate(self):
        ...
```

### 避免未来信息

```python
# ✅ 正确：t 时刻只用 t 之前的数据
for i in range(window, len(prices)):
    current_data = prices[:i]       # 只有到现在为止的数据
    current_price = prices[i]       # 当天的价格
    future_price = prices[i + window]  # 禁止：这是未来数据！

# ❌ 禁止：使用未来信息
signal = generate_signal(prices[:i])  # 用过去数据生成信号
return prices[i+1] > prices[i]        # 禁止：用了未来价格判断信号是否正确
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `engine.py` | 234 | **500** | ✅ |
| `metrics.py` | 234 | **500** | ✅ |
| `models.py` | 153 | **400** | ✅ |
| `bridge.py` | — | **400** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ 上涨市回测（验证策略跟随大盘）
- ✅ 下跌市回测（验证回撤控制）
- ✅ 震荡市回测（验证无过度交易）
- ✅ 空数据输入（异常处理）
- ✅ 最大回撤计算与行业标准一致
- ✅ 夏普比率计算交叉验证（与 Excel 对比）
- ✅ 无未来信息检测（随机数据穿透）
- ✅ 不同手续费/滑点设置的敏感性

### 覆盖率目标

- 回测引擎：≥85%
- 绩效指标：≥90%（与知名库交叉验证）
- 桥接适配器：≥85%

---

## 性能标准

| 指标 | 目标 |
|:-----|:----:|
| 5 年日频回测（单标的）| ≤ 10s |
| 绩效指标计算（夏普/回撤/胜率）| ≤ 500ms |
| Monte Carlo 模拟（1000 次）| ≤ 30s |
| 桥接转换 1000 条 | ≤ 1s |

---

## 部门间契约

### 输入契约

```python
# 回测引擎需要：
# 1. 历史 K 线数据（数据管道部提供）
# 2. 交易信号 TradeRecord（交易执行部提供）
# 
# 如果这两者的格式变了，回测结果直接出错
```

### 输出契约

```python
class BacktestReport(BaseModel):
    config: BacktestConfig
    total_return_pct: float
    annual_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    equity_curve: list[float]
    benchmark_return_pct: float | None
    market_condition: str  # bull/bear/oscillate
```

---

## 回测结果报告标准

每次回测输出必须包含：

```
## 回测摘要
- 期间: 2025-01-01 → 2026-06-01
- 初始资金: ¥100,000
- 最终资金: ¥142,350
- 总收益率: +42.35%
- 年化收益率: +28.7%
- 夏普比率: 1.42
- 最大回撤: -12.3%
- 胜率: 58.3%
- 盈亏比: 2.1
- 总交易次数: 48
- 市场环境: 震荡偏牛
- 基准收益: +18.2%（沪深300）
- Alpha: +10.1%
```

---

## 审查清单

- [ ] 无未来信息（t 时刻只用前 t 数据）？
- [ ] 手续费和滑点配置了？
- [ ] 多市场环境覆盖测试？
- [ ] 绩效指标与行业标准一致？
- [ ] 空数据边缘情况处理？
- [ ] 结果可重现（seed 固定）？
- [ ] 报告包含市场环境和基准？

# 06 纯 Python 技术指标计算

## 一句话

> **不用 numpy、不用 pandas、不用 TA-Lib，纯 Python 代码算 MA、RSI、MACD、布林带。** 这样部署简单、没有 C 库依赖、浏览器上也能跑。

---

## 为什么自己算？

### 三种方案对比

| 方案 | 优点 | 缺点 |
|:-----|:-----|:-----|
| **TA-Lib**（专业计算库） | 快，准确 | 装起来要命（C 扩展编译），Windows 上尤其痛苦 |
| **Pandas 计算** | 代码简洁 | 依赖 pandas，前端不能用 |
| **纯 Python** | 零依赖，浏览器也能跑 | 慢一点（但 K 线数据量小，感觉不到） |

项目选的是**纯 Python**——因为我们的目标不是高频交易微秒级计算，而是给前端展示趋势。几十个 K 线数据点，纯 Python 算得过来。

---

## 每个指标怎么算的？

打开 `backend/indicators.py`，一个个看：

### MA（移动平均线）

最简单的指标——N 天的收盘价求平均。

```python
def calc_ma(closes: list[float], period: int = 5) -> list[float | None]:
    """简单移动平均线"""
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)        # 前 N-1 天算不了
        else:
            # 取最近 N 天的收盘价求平均
            window = closes[i - period + 1 : i + 1]
            avg = sum(window) / period
            result.append(avg)
    return result
```

**教学案例：**
```python
closes = [10, 11, 12, 13, 14, 15]   # 6 天的收盘价

# MA(3)：
# 第1天 → None（不够 3 天）
# 第2天 → None（不够 3 天）
# 第3天 → (10+11+12)/3 = 11.0
# 第4天 → (11+12+13)/3 = 12.0
# 第5天 → (12+13+14)/3 = 13.0
# 第6天 → (13+14+15)/3 = 14.0
```

---

### RSI（相对强弱指数）

衡量**最近涨得多还是跌得多**。0-100，一般认为 >70 超买、<30 超卖。

```python
def calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    result = []
    for i in range(len(closes)):
        if i < period:
            result.append(None)
            continue
        
        # 计算 period 天内每天的涨跌
        gains, losses = 0, 0
        for j in range(i - period + 1, i + 1):
            change = closes[j] - closes[j - 1]
            if change > 0:
                gains += change       # 累加涨幅
            else:
                losses += abs(change) # 累加跌幅（取绝对值）
        
        avg_gain = gains / period
        avg_loss = losses / period
        
        if avg_loss == 0:
            rsi = 100   # 从来没跌过
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        result.append(rsi)
    return result
```

**直觉理解：**
- RSI = 70 → 过去 N 天涨幅是跌幅的 **2.33 倍** → 涨太多了，可能要回调
- RSI = 30 → 过去 N 天跌幅是涨幅的 **2.33 倍** → 跌太多了，可能要反弹

---

### MACD（指数平滑异同移动平均线）

最复杂也最有用的指标：

```python
def calc_macd(closes: list[float]) -> dict:
    """
    MACD 有三条线：
      - DIF:  快线（12日EMA） - 慢线（26日EMA） → 反映短期趋势
      - DEA:  DIF 的 9 日 EMA → 信号线
      - MACD柱: (DIF - DEA) × 2 → 两条线之间的差距
    """
    ema12 = _calc_ema(closes, 12)   # 快线：对价格变化反应快
    ema26 = _calc_ema(closes, 26)   # 慢线：对价格变化反应慢
    dif = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    dea = _calc_ema(dif, 9)
    macd_bar = [(d - dea_val) * 2 for d, dea_val in zip(dif, dea)]
    
    return {"dif": dif, "dea": dea, "macd_bar": macd_bar}
```

**核心思想**：当短期趋势（快线）向上突破长期趋势（慢线）→ 金叉 → 买入信号。

---

### 布林带（Bollinger Bands）

中间是 MA，上下两条是 `MA ± k × 标准差`：

```python
def calc_bollinger(closes: list[float], period: int = 20, k: float = 2.0):
    ma = calc_ma(closes, period)
    upper, lower = [], []
    
    for i in range(len(closes)):
        if ma[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            # 计算标准差：每个价格离均线多远
            window = closes[i - period + 1 : i + 1]
            mean = ma[i]
            variance = sum((x - mean) ** 2 for x in window) / period
            std_dev = variance ** 0.5
            
            upper.append(mean + k * std_dev)  # 上轨
            lower.append(mean - k * std_dev)  # 下轨
    
    return {"middle": ma, "upper": upper, "lower": lower}
```

**意思**：价格碰到上轨 → 可能偏高；碰到下轨 → 可能偏低。但布林带不告诉你方向，只告诉你"偏高还是偏低"。

---

## 面试会怎么问你

> **Q: 为什么自己算指标，不用 TA-Lib？**
> 
> A: 两个原因。一是部署复杂度——TA-Lib 需要 C 扩展编译，我们的应用不是高频交易，纯 Python 够用。二是前端也想复用——如果将来指标计算移到浏览器端，pure Python 可以直接用 JavaScript 重写。

> **Q: RSI 超过 70 就一定卖吗？**
> 
> A: 不是。强趋势行情里 RSI 可以长期在 70 以上（一直涨一直涨）。RSI 只是辅助，不能单独决策——这也是我们用多 Agent 辩论而不是单一指标的原因。

---

## 自己试试（5 分钟）

1. 打开 `backend/indicators.py`
2. 找 `calc_all` 函数——这个函数把 MA/RSI/MACD/布林带全部算好
3. 试着手算一下：
   ```python
   closes = [10, 11, 12, 13, 14, 15]
   # 用脑袋算 MA(3) 的最后一天值
   # 答案在代码里
   ```
4. 启动后端，直接调接口：
   ```bash
   curl http://localhost:8000/api/stocks/000001/technical-indicators
   ```

---

**上一篇：[Provider 抽象模式](05-provider-pattern.md)**

**下一篇：[类型注解与 Pyright](07-type-hints-pyright.md)** — 为什么每行代码都要写类型

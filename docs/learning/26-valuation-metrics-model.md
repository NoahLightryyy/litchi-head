# 26 估值比率模型 — ValuationMetrics PE/PB/PS

## 一句话

> 股价 + 财务指标 → 估值比率（PE/PB/PS），纯计算模型，不需要新的数据源 API。

---

## 为什么需要它？

### 问题场景

基本面数据接入后（FD-001），分析师能看到 ROE、毛利率、资产负债率，但还缺关键信息——**市场怎么给这只股票定价**？

- PE = 10 表示市场愿意为每 1 元利润付 10 元——"便宜"还是"贵"？
- PB = 1 表示市场价等于清算价——破净还是溢价？
- PS = 5 表示市值是年营收的 5 倍——烧钱公司的估值锚

没有这些，基本面分析少了一个维度。

### 设计思路

估值比率 = 股价 / 财务指标。股价平均每秒变一次，财务指标每季度变一次。所以：

- **原始数据**走 DataSource 协议（get_financials / get_realtime_quotes）
- **估值比率**是消费层的计算（DataCollector.get_valuation）

这样就遵循了「计算与数据分离」的原则：

```
Data Source get_financials → FinancialMetrics (季度更新)
Data Source get_realtime_quotes → StockQuote (每秒更新)
                                     ↓  DataCollector.get_valuation
                              ValuationMetrics (PE/PB/PS)
```

---

## 项目里的真实代码

### ValuationMetrics 模型

打开 `src/data/models.py`：

```python
class ValuationMetrics(BaseModel):
    """个股估值比率（由财务指标 + 股价计算）"""
    stock_code: str
    report_date: str = ""
    pe: float = Field(default=0.0, ge=0.0, description="市盈率 = 股价 / EPS")
    pb: float = Field(default=0.0, ge=0.0, description="市净率 = 股价 / 每股净资产")
    ps: float = Field(default=0.0, ge=0.0, description="市销率 = 总市值 / 主营业务收入")
    market_cap: float = Field(default=0.0, ge=0.0, description="总市值(元)")
```

**为什么所有字段 `ge=0.0`？**
- 亏损公司 EPS 为负 → `pe = 0.0`（负 PE 无经济含义，投资者不会说"这家公司市盈率负 10 倍"）
- 资不抵债公司 BVPS 为负 → `pb = 0.0`
- 零就是"不适用"的数值表示
- 对比 `FinancialMetrics` 允许负 EPS 和负增长率——财务指标可以有负值，估值比率不应为负

### StockQuote.market_cap 字段

PE/PB 只需要价格和财务数据，但 PS 需要总市值。akshare 的 `stock_zh_a_spot_em` API 已返回总市值：

```python
# src/data/providers/akshare.py — _row_to_quote
return StockQuote(
    ...
    market_cap=safe_float(row.get("总市值", 0.0)),
)
```

向后兼容：不使用 `market_cap` 的代码不传即可，默认 0.0。

### DataCollector.get_valuation()

打开 `src/data/collector.py`：

```python
def get_valuation(self, code: str) -> ValuationMetrics | None:
    financials = self.get_financials(code)
    if not financials:
        return None
    quote = self.get_realtime_quote(code)
    if quote is None or quote.price <= 0:
        return None

    latest = financials[0]  # 最新一期
    pe = round(quote.price / latest.eps, 2) if latest.eps > 0 else 0.0
    pb = round(quote.price / latest.book_value_per_share, 2) if latest.book_value_per_share > 0 else 0.0
    ps = round(quote.market_cap / latest.operating_revenue, 2) if quote.market_cap > 0 and latest.operating_revenue > 0 else 0.0

    return ValuationMetrics(
        stock_code=code,
        report_date=latest.report_date,
        pe=pe, pb=pb, ps=ps,
        market_cap=quote.market_cap,
    )
```

**计算细节：**
- PE 只算 `eps > 0`，跳过负值 → `0.0`
- 缓存 TTL = 5 分钟（股价变化时估值变化，比财务数据缓存短）
- `round(..., 2)` 保持输出整洁（不需要 PE=37.612345）

---

## 自己试试（5 分钟）

1. 打开 `src/data/collector.py`，找到 `get_valuation()` 方法
2. 打开 REPL：
   ```python
   from src.data.collector import DataCollector
   collector = DataCollector()
   # 如果网络不通，用刚才的 MockDataSource 方式：
   from tests.test_data.conftest import MockDataSource
   from src.data.cache import DataCache
   collector = DataCollector(source=MockDataSource(), cache=DataCache())
   vm = collector.get_valuation("000001")
   print(f"PE={vm.pe}, PB={vm.pb}")  # PE=10.0, PB=1.0
   ```
3. 思考题：为什么 PE 不用 TTM 算法（近 4 个季度 EPS 之和）？（提示：当前只取最新一期，因为历史数据不足 4 个季度时为空）

---

**上一篇：[财务指标数据模型](25-financial-indicator-model.md)**

# 25 财务指标数据模型（DataSource 协议扩展模式）

## 一句话

> A 股财务指标（EPS/ROE/毛利率/资产负债率等）从 akshare 原始 DataFrame → Pydantic 模型 → DataSource 协议 → DataCollector 的统一接入模式。

---

## 为什么需要它？

### 问题场景

辩论引擎分析股票时，基本面层一直是"暂无基本面数据"占位符：

```
----- 基本面层 -----
（暂无基本面数据）
```

大师们只能看到行情 + K 线 + 新闻，看不到 PE/PB/ROE/营收增长率等核心财务指标。就像医生看病不验血——能做判断，但精度差一到两个数量级。

akshare 有一个功能强大的接口 `stock_financial_analysis_indicator()`，返回 86 列季度财务分析数据（每股指标、盈利能力、增长能力、财务健康、运营效率、规模全部覆盖），但没人把它接进来。

### 它的解法

按项目中已有的 **DataSource 协议扩展模式** 把财务数据接入三步走：

1. **Pydantic 模型** — 定义 `FinancialMetrics(BaseModel)`，从 86 列中挑出 17 个关键指标
2. **Provider 协议** — `DataSource` 新增 `get_financials()` 方法，所有数据源实现
3. **Collector 封装** — `DataCollector.get_financials()` 缓存 + 健康监控

这样上层代码（辩论引擎、前端）完全不需要知道数据是从 akshare、adata 还是 zzshare 来的，也看不见 86 列原始数据——它们只跟 17 个精心挑选的字段打交道。

---

## 项目里的真实代码

### FinancialMetrics 模型

打开 `src/data/models.py`：

```python
class FinancialMetrics(BaseModel):
    """个股核心财务指标（季度）"""

    stock_code: str
    report_date: str = ""

    # ── 每股指标 ──
    eps: float = Field(default=0.0, description="摊薄每股收益(元)")
    book_value_per_share: float = Field(default=0.0, ge=0.0, description="每股净资产_调整后(元)")
    operating_cf_per_share: float = Field(default=0.0, description="每股经营性现金流(元)")

    # ── 盈利能力 ──
    roe: float = Field(default=0.0, description="净资产收益率(%)")
    roa: float = Field(default=0.0, description="总资产利润率(%)")
    gross_margin: float = Field(default=0.0, description="销售毛利率(%)")
    net_profit_margin: float = Field(default=0.0, description="销售净利率(%)")

    # ── 增长能力 ──
    revenue_growth: float = Field(default=0.0, description="主营业务收入增长率(%)")
    net_profit_growth: float = Field(default=0.0, description="净利润增长率(%)")

    # ── 财务健康 ──
    debt_ratio: float = Field(default=0.0, ge=0.0, le=100.0, description="资产负债率(%)")
    current_ratio: float = Field(default=0.0, ge=0.0, description="流动比率")
    quick_ratio: float = Field(default=0.0, ge=0.0, description="速动比率")

    # ── 运营效率 ──
    inventory_turnover: float = Field(default=0.0, ge=0.0, description="存货周转率(次)")
    asset_turnover: float = Field(default=0.0, ge=0.0, description="总资产周转率(次)")

    # ── 规模 ──
    total_assets: float = Field(default=0.0, ge=0.0, description="总资产(元)")
    operating_revenue: float = Field(default=0.0, description="主营业务利润(元)")
```

**关键设计决策：**
- 约束不是一刀切 `ge=0.0`：EPS、增长率、主营业务利润都可能为负（亏损公司），所以允许负值
- `debt_ratio` 有 `ge=0.0, le=100.0`：资产负债率定义上就在 0~100% 之间
- 字段名称用英文（`eps` 而非 `摊薄每股收益`），`description` 写中文——代码可读性和人机界面分离

### akshare 列名映射

打开 `src/data/providers/akshare.py`：

```python
def _row_to_financial(row: pd.Series, code: str) -> FinancialMetrics:
    return FinancialMetrics(
        stock_code=code,
        report_date=safe_str(row.get("日期", "")),
        eps=safe_float(row.get("摊薄每股收益(元)", 0.0)),
        book_value_per_share=safe_float(row.get("每股净资产_调整后(元)", 0.0)),
        # ... 每个字段映射一个中文列名
    )
```

akshare 的列名是中文（"摊薄每股收益(元)"），并且版本间可能变化。用 `.get()` 带默认值保证：
- 列名变了 → 字段默认为 0.0，系统不崩溃
- None 值 → `safe_float` 返回 0.0

### DataSource 协议扩展

打开 `src/data/providers/base.py`：

```python
class DataSource(Protocol):
    # ... 原有的 7 个方法

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        """获取个股财务指标"""
        ...
```

所有 4 个 Source 类都实现了这个方法：
- `AKShareSource` → 真实调用 akshare API
- `ADataSource` / `ZzshareSource` → 返回 `[]`（待后续接入）
- `FallbackSource` → 委托主/备源的该方法

### DataCollector 封装

打开 `src/data/collector.py`：

```python
class DataCollector:
    TTL_FINANCIALS = 3600  # 财务数据 1 小时缓存（日内不变）

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        cache_key = f"financials:{code}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        # ... 调 source + 写缓存 + 记录健康统计
```

---

## 完整数据流：从 akshare → LLM 分析师（FD-001e~g）

> 打通了"财务数据 → 辩论引擎"的全链路。

### 数据流水线

```
akshare.stock_financial_analysis_indicator(code)
  ↓  86 列中文原始数据
_row_to_financial()
  ↓  17 个 FinancialMetrics 字段
AKShareSource.get_financials()
  ↓
DataCollector.get_financials()    ← TTL=1h 缓存
  ↓
collect_data_node()                ← src/debate/orchestrator.py
  ├── market_data["financials"]    ← 结构化数据（供后续扩展）
  └── format_market_brief()        ← 格式化为人读文本
       ↓
       "基本面层" 区段被填充真实数据
  ↓
_run_single_analyst()
  ↓  brief 追加到 analyst prompt
LLM 分析师收到结构化的 6 大维度数据
```

### format_market_brief 格式化逻辑

打开 `src/data/collector.py`：

```python
def format_market_brief(
    stock_code: str,
    stock_name: str,
    quote: StockQuote | None = None,
    klines: list[KLine] | None = None,
    news: list[NewsItem] | None = None,
    financials: list[FinancialMetrics] | None = None,  # 🆕 FD-001e
) -> str:
```

收到 `FinancialMetrics` 列表后，取最新一期（列表第一项），按 6 大维度分别格式化：

```
----- 基本面层 -----
最新报告期: 2024-12-31
📊 每股指标: EPS 1.2500 元 | 每股净资产 18.50 元 | 每股经营现金流 2.10 元
📈 盈利能力: ROE 12.50% | ROA 5.20% | 毛利率 45.80% | 净利率 18.30%
🚀 增长能力: 营收增长 +8.50% | 净利润增长 +15.20%
🛡️ 财务健康: 资产负债率 55.0% | 流动比率 1.80 | 速动比率 1.20
⚙️ 运营效率: 存货周转率 4.50 | 总资产周转率 0.85
🏢 规模: 总资产 50000.00 亿元 | 主营利润 1500.00 亿元
```

**关键设计：**
- 零值字段自动跳过（`if latest.eps != 0.0`）—— 避免满屏 `0.00`
- 负值正确显示负号（`growth:+.2f` → `-5.30%`）
- 总资产/主营利润除以 1 亿以「亿元」显示，避免长数字不可读
- 取最新一期而非多期（简报足够辅助决策，多期对比留给专项分析）

### collect_data_node 接驳

打开 `src/debate/orchestrator.py` 的 `collect_data_node`：

```python
try:
    financial_data = collector.get_financials(code)
except Exception as e:
    logger.exception("财务数据获取失败 [%s]: %s", code, e)

brief = format_market_brief(
    ...
    financials=financial_data,  # ← 传入财务数据
)

# 同时保留结构化数据供后续扩展
return {
    "market_data": {
        ...
        "financials": [f.model_dump() for f in financial_data],
    },
}
```

### 分析师自动受益

分析师 prompt 已经通过 `market_data["brief"]` 接收简报文本：

```python
# _run_single_analyst ← src/debate/orchestrator.py:335
brief = market_data.get("brief", "")
if brief:
    enhanced += f"\n\n📊 以下为当前市场数据：\n{brief}"
```

现在 fundamentals 区段包含真实财务指标，基本面分析师的 prompt（`src/debate/analysts.py`）中提到的 "ROE、利润率、负债率" 终于有了真实数据可分析。

### 数据链路完整性验证

| 环节 | 验证 |
|:-----|:-----|
| FinancialMetrics 模型 | ✅ 19 tests（构造/约束/边界/序列化） |
| AKShare akshare 映射 | ✅ 5 tests（行转换/错误处理） |
| DataCollector.get_financials() | ✅ 4 tests（正常/失败/缓存） |
| format_market_brief 含财务 | ✅ 6 tests（全维度/空列表/零值/部分/负增长） |
| collect_data_node 接驳 | ✅ 17 tests（含 mock get_financials） |
| 辩论全链路无回归 | ✅ 261 tests |

---

| 维度 | 以前（没有统一模式） | 现在（DataSource 协议） |
|:-----|:-------------------|:----------------------|
| 数据源切换 | 每改一个源改所有调用点 | 换源 = 换一个 Provider 类 |
| 测试 | 要 mock 具体库的 API | MockDataSource 就够了 |
| 健康监控 | 没有 | 自动记录成功/失败/延迟 |
| 列名变化 | 到处修 | 一个 `_row_to_*` 函数 |
| 新增数据类型 | 要从头搭 | 4 步模板：模型→协议→Provider→Collector |

---

## 自己试试（5 分钟）

1. 打开 `src/data/models.py`，找到 `FinancialMetrics` 类
2. 打开 Python REPL，跑一下：
   ```python
   import akshare as ak
   df = ak.stock_financial_analysis_indicator(symbol="000001", start_year="2024")
   list(df.columns)  # 看看 86 列里有哪些我们没用上的
   ```
3. 思考题：为什么 PE（市盈率）不放在 `FinancialMetrics` 里而需要单独定义？（提示：PE = 股价 / EPS，股价每秒都在变）

---

**上一篇：[结果回调引擎架构](23-result-callback-engine.md)**

**下一篇：待定**

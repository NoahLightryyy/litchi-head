# 27 🆕 PD 动态指标体系 — 行业感知的关键指标选择

> **一句话**：不把所有股票套同一个财务指标模板（银行看存货周转率就没意义），而是按行业+产业链位置动态选择最关键的 5-10 个指标。

## 问题

当前 `FinancialPanel` 对所有股票展示完全相同的 17 个财务指标。这导致：

| 场景 | 问题 |
|:-----|:------|
| 平安银行 → 显示存货周转率 | ❌ 银行没存货，永远为 0 |
| 贵州茅台 → 显示应收帐款周转率 | ❌ 茅台先款后货，应收帐款极少 |
| 宁德时代 → 只显示毛利率不显示研发费用 | ❌ 中游制造最该看的就是研发和客户集中度 |

产品定位战略（PRODUCT-POSITIONING.md）明确指出：**不和 Wind 比 6000 个指标。只取当前股票行业最有效的 5-10 个。**

## 解决方案：三阶段动态选择

```
股票代码 "000001"
  → stock_individual_info_em()           ← 调东方财富 API
  → raw_industry = "银行Ⅱ"               ← 返回二级行业名
  → normalize_industry("银行Ⅱ")           ← 归一化到一级
  → industry = "银行"
  → classify_chain_position("银行")       ← 判断产业链位置
  → position = "financial"
  → REGISTRY["银行"]                      ← 查注册表
  → ["pe", "pb", "roe", "eps", "debt_ratio", ...]  ← 只返回相关指标
```

## 关键组件

### `src/data/indicators/registry.py` — 心脏

三个核心数据结构：

1. **`_INDUSTRY_NORMALIZE`** — 455 条映射，覆盖东方财富全部 496 个子板块到 31 个一级行业

```python
_INDUSTRY_NORMALIZE = {
    "银行Ⅱ": "银行",          # 二级 → 一级
    "白酒Ⅱ": "食品饮料",      # 二级 → 一级
    "半导体": "电子",          # 三级 → 一级
    "煤炭开采": "煤炭",
    "股份制银行Ⅲ": "银行",
    # ... 455 条
}
```

2. **`REGISTRY`** — 31 个一级行业 × 每个 5-8 个关键指标

```python
REGISTRY = {
    "银行": ["pe", "pb", "roe", "eps", "debt_ratio", "roa", "net_profit_growth", ...],
    "食品饮料": ["pe", "roe", "eps", "gross_margin", "net_profit_margin", ...],
    "煤炭": ["pe", "roe", "eps", "gross_margin", "debt_ratio", ...],
    # ... 31 个行业
}
```

3. **`INDICATOR_DEFS`** — 18 个指标的完整定义（每个含中文解释、单位、正常区间）

```python
IndicatorDef(
    id="roe",
    name="净资产收益率",
    description="净利润/净资产，衡量股东回报效率",
    field="roe", unit="%",
    normal_range_hint="10-20%",
    priority=10,
)
```

### `src/data/indicators/selector.py` — 大脑

```python
class DynamicIndicatorSelector:
    def for_stock(self, code: str) -> SelectorResult:
        # 1. 调 API 拿行业
        raw = self._source.get_stock_industry(code)  # "银行Ⅱ"
        # 2. 归一化
        industry = normalize_industry(raw)             # "银行"
        # 3. 产业链位置
        position = classify_chain_position(industry)   # financial
        # 4. 查注册表
        ids = REGISTRY.get(industry, [])               # ["pe", "pb", ...]
        # 5. 展开定义
        defs = [INDICATOR_DEFS_MAP[i] for i in ids]
        return SelectorResult(...)
```

### 产业链位置分类

```
上游（资源采掘）→ 煤炭、石油石化、有色金属、钢铁、基础化工
中游（制造加工）→ 电子、计算机、汽车、机械设备、电力设备、国防军工...
下游（品牌/渠道）→ 食品饮料、医药生物、房地产、传媒、商贸零售...
金融 → 银行、非银金融
```

## 实锤验证（非拍脑袋）

2026-07-24 实际调通 API 确认：

```python
ak.stock_board_industry_name_em()          # → 496 个行业板块 ✅
ak.stock_individual_info_em("000001")      # → "银行Ⅱ" ✅
```

## 自己试试

```bash
# 1. 打开 src/data/indicators/registry.py
#    找到 REGISTRY 字典，看看每个行业配了哪些指标

# 2. 运行测试
pytest tests/test_data/test_indicators.py -v

# 3. 试着加一个新行业的映射
#    在 _INDUSTRY_NORMALIZE 加一条，在 REGISTRY 加对应指标列表
```

## 设计要点

| 方面 | 做法 |
|:-----|:------|
| 数据存储 | **静态 dict** — 编译时已知，不进数据库。启动即加载 |
| 行业体系 | **东方财富行业分类** → 归一化到 31 个一级行业（与申万一级对齐） |
| 扩展方式 | 直接在 `registry.py` 加映射 + 加指标即可 |
| 缓存策略 | DataCollector 层 TTL 1 天（行业不会天天变） |

## 项目里的真实代码

| 文件 | 做什么 |
|:-----|:-------|
| `src/data/indicators/registry.py` | 模型 + 注册表 + 归一化映射 |
| `src/data/indicators/selector.py` | 动态选择器 |
| `src/data/collector.py` | DataCollector 新增 3 个方法 |
| `tests/test_data/test_indicators.py` | 34 个测试覆盖全链路 |

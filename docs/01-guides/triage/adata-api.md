# 📊 adata API 兼容性急救

> adata（免费开源 A 股量化库）的 API 在不同版本间不够稳定，
> 参数名、属性名随时可能变。以下是我们遇到过的坑。

---

## 症状速查

| 症状 | 原因 |
|:-----|:------|
| `No parameter named "stock_codes"` | 参数名是 `code_list` 不是 `stock_codes` |
| `'Info' object has no attribute 'all_industry'` | 某些版本没有此属性 |
| DataFrame 列名和预期不一致 | adata 版本升级改了列名 |

---

## `list_market_current` 参数名

```python
# ❌ 错误（Pyright 会报）
df = adata.stock.market.list_market_current(stock_codes=codes)

# ✅ 正确
df = adata.stock.market.list_market_current(code_list=codes)
```

> **原因**：adata 实际参数名叫 `code_list`，但老版本文档/代码示例用了 `stock_codes`。
>
> 验证方法：
> ```python
> help(adata.stock.market.list_market_current)
> # → 看签名: list_market_current(code_list=None)
> ```

---

## `all_industry` 属性不存在

```python
# ❌ 错误：某些 adata 版本没有这个属性
df = adata.stock.info.all_industry()

# ✅ 正确：用 getattr 安全访问
industry = getattr(adata.stock.info, "all_industry", None)
if industry is None:
    return []
df = industry()
```

> **原因**：adata 版本不同，`all_industry` 可能没暴露出来。
>
> 验证方法：
> ```python
> import adata
> hasattr(adata.stock.info, "all_industry")  # True/False
> ```

---

## DataFrame 行 → Pydantic 模型

adata 返回的 DataFrame 用 `iterrows()` 逐行处理，Pyright 会把 `row["col"]` 推断为 `Series | ndarray | Any`。

```python
# ❌ 错误：Pyright 报 type mismatch
StockInfo(code=row["stock_code"], name=row["stock_name"])

# ✅ 正确：显式转换
StockInfo(
    code=safe_str(row.get("stock_code", "")),
    name=safe_str(row.get("stock_name", "")),
)
```

---

## 通用原则

1. **所有 adata API 调用前先 `help()` 看签名** — 参数名可能和文档不一致
2. **用 `getattr` + 默认值包装** — 防止属性不存在时直接抛异常
3. **对 DataFrame 列用 `row.get("col", default)` + 显式转换** — 避免 Pyright 类型推断问题
4. **版本锁定的备选方案** — 如果 adata 升级破坏兼容，在 `pyproject.toml` 里锁定版本：
   ```
   adata>=2.9.0,<2.10.0
   ```

# 📐 数据管道部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的数据模块特定规范。

---

## 代码规范

### Provider 层实现

```python
# ✅ 正确：继承协议
class MyNewSource(BaseDataSource):
    """我的新数据源"""
    
    async def get_stock_quotes(self, codes: list[str]) -> list[StockQuote]:
        """采集股票行情"""
        ...
```

### 错误处理

```python
# ❌ 禁止
try:
    result = akshare.stock_data()
except Exception:
    pass

# ✅ 正确
try:
    result = akshare.stock_data()
except requests.Timeout:
    logger.warning("[MySource] 请求超时: %s", codes)
    raise  # 让 FallbackSource 兜底
except Exception as e:
    logger.exception("[MySource] 采集失败: %s", e)
    raise
```

### pandas 类型转换

```python
# ❌ 错误 — Pyright 报 type mismatch
StockInfo(code=row["code"], name=row["name"])

# ✅ 正确
StockInfo(code=str(row["code"]), name=str(row["name"]))
StockQuote(price=float(row["最新价"]), volume=int(row["成交量"]))
```

### 缓存策略

| 数据类型 | 缓存 TTL | 说明 |
|:---------|:--------:|:-----|
| 股票列表 | 3600s | 一天变化不超过一次 |
| 实时行情 | 30s | 高频刷新 |
| K 线数据 | 300s | 分钟级更新 |
| 板块排行 | 60s | 盘中经常变化 |
| 新闻公告 | 300s | 分钟级更新 |

---

## 测试规范

### 必须覆盖的场景

- ✅ 正常数据返回
- ✅ 数据源超时
- ✅ 数据源返回空数据
- ✅ 数据源返回异常
- ✅ FallbackSource 主→备切换
- ✅ FallbackSource 备→主恢复
- ✅ 数据解析错误（格式异常的行）

### Mock 策略

```python
# 使用 tests/test_data/conftest.py 中的 MockDataSource
# 不要重复造 mock fixture

def test_fallback_recovery(mock_data_source, mock_failing_source):
    """验证主源恢复后自动切回"""
    source = FallbackSource(mock_data_source, mock_failing_source)
    result = source.fetch("quotes", ["000001"])
    assert source._using_fallback["quotes"] is False
```

### 最小覆盖率

- Provider 层：≥90%
- DataCollector：≥80%
- 数据模型：100%（容易达到）

---

## 文档标准

每个 Provider 文件头部必须注明：

```python
"""
数据源: akshare (东方财富)
局限性: 仅 A 股，无港股/美股
频率: 实时
费用: 免费
失败模式: 网络中断时抛 requests 异常
"""
```

---

## 性能标准

- 单次数据采集 ≤ 5s（含网络延迟）
- 缓存命中率目标 ≥ 70%
- 批量查询（如 50 只股票）≤ 15s

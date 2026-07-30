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

### 盘中 K 线状态

- 历史完整日 K 使用 `FINAL_DAILY`，不得包含未收盘交易日；
- 已结束分钟、实时行情和今日动态 OHLC 分别使用
  `FINAL_MINUTE`、`LIVE_QUOTE`、`PROVISIONAL`；
- `PROVISIONAL` 可以供盘中 AI 使用，但不能混入完整日 K 或覆盖正式指标；
- 动态状态必须携带 `as_of`、交易阶段和来源诊断；
- 收盘且多源确认后才允许从 `PROVISIONAL` 晋升为 `FINAL_DAILY`。

### 完成日线 RAW、双源与复权

本部门执行 [ADR-013](../../05-decisions/ADR-013-multi-source-evidence.md) 和
[K 线实施计划](../../02-requirements/KLINE_EVIDENCE_IMPLEMENTATION_PLAN.md)，不得
在适配器中自行放宽：

- 沪深 Phase R 使用新浪直连 + 腾讯直连 RAW 日线；按不同 `upstream_id` 计数；
- 北交所缺可靠第二上游时返回
  `INCOMPLETE / independent_upstream_missing`，不自动退化为单源成功；
- RAW、公司行动/因子和派生复权序列分开建模、保存和版本化；
- 完成日线 RAW OHLC 按证券 `price_tick` 规范化后必须相等；一个最小价位差异也
  返回 `CONFLICTED`；
- 成交量统一为股，并记录来源精度；只有已声明的“手”级精度才允许小于一个精度
  单位的差异；
- 不直接比较不同供应商前复权成品价。统一复权由 RAW + 版本化公司行动生成；
- 盘中技术分析使用指定 `as_of` 的前复权序列；回测读取点时因子；成交和订单核对
  永远使用 RAW/实时真实价格。

实时快照的 0.01 元容差、L1 分时的 500 股经验容差和完成日线规则相互独立。任何
实现都必须在错误码、配置名和测试文件中体现所属数据时态，禁止共用一个模糊阈值。

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

# 📐 后端 API 部技术规范

> 扩展 [coding-style.md](../../01-guides/WORKFLOW.md#1-核心原则) 的后端 API 特定规范。

---

## 代码规范

### HTTP 状态码语义

```python
# ✅ 正确：严格区分状态码
@router.get("/stocks/{code}/quote")
async def get_quote(code: str):
    try:
        data = await collector.get_realtime_quotes([code])
        if not data:
            return JSONResponse(  # 正常空返回 404
                content={"detail": f"股票 {code} 暂无数据", "code": "NO_DATA"},
                status_code=404,
            )
        return data[0].model_dump()
    except DataSourceError as e:
        raise HTTPException(status_code=503, detail=f"数据源不可用: {e}")
    except Exception as e:
        logger.exception("[stocks] 获取行情异常: %s", e)
        raise HTTPException(status_code=500, detail="服务器内部错误")

# ❌ 禁止：全部返回 200
return {"data": maybe_none, "error": None}  # 错误也 200，前端无法区分！
```

### 异步超时控制

```python
# ✅ 正确：所有数据采集调用有超时
from backend.async_utils import run_sync

@router.get("/market/sectors")
async def get_sectors():
    result = await run_sync(collector.get_sectors, timeout=15.0)
    return result

# ❌ 禁止：无超时的同步调用
result = collector.get_sectors()  # 可能卡死整个 event loop
```

### 响应格式一致性

```python
# ✅ 正确：统一响应结构
class APIResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    meta: dict = Field(default_factory=dict)  # 分页、时间戳等

# 或者对列表类型：
@router.get("/stocks/search")
async def search_stock(q: str):
    results = await collector.search_stocks(q)
    return {
        "items": results,
        "total": len(results),
        "query": q,
    }
```

---

## 文件大小红线

| 文件 | 当前行数 | 红线 | 状态 |
|:-----|:--------:|:----:|:----:|
| `routers/market.py` | — | **400** | ✅ |
| `routers/stocks.py` | — | **400** | ✅ |
| `routers/debate.py` | — | **400** | ✅ |
| `routers/trust.py` | — | **400** | ✅ |
| `main.py` | — | **300** | ✅ |
| `indicators.py` | — | **300** | ✅ |

---

## 测试规范

### 必须覆盖的场景

- ✅ 每个 endpoint 正常返回 200
- ✅ 空数据返回 404（不是 200）
- ✅ 异常返回 500/503（不是 200）
- ✅ 同步调用超时验证
- ✅ 搜索防抖验证（前端 useDebounce）
- ✅ CORS 跨域验证
- ✅ 数据源 mock → 验证 JSON 输出结构

### Mock 策略

```python
# 使用 tests/test_backend/conftest.py 中的 MockCollector
# 不要重复造 mock fixture

def test_get_quote_success(test_client):
    """验证行情 endpoint 返回正确结构"""
    response = test_client.get("/api/stocks/000001/quote")
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert "price" in data

def test_get_quote_no_data(test_client, mock_collector):
    """验证无数据时返回 404"""
    mock_collector.get_realtime_quotes.return_value = []
    response = test_client.get("/api/stocks/999999/quote")
    assert response.status_code == 404
    assert data["code"] == "NO_DATA"
```

### 覆盖率目标

- 每个 endpoint ≥ 90%（含失败路径）
- 工具函数（async_utils / config / indicators）≥ 85%

---

## 性能标准

| 指标 | 目标 |
|:-----|:----:|
| 单个 endpoint 响应（缓存命中）| ≤ 200ms |
| 单个 endpoint 响应（缓存未命中）| ≤ 5s |
| debate/run 触发 | ≤ 30s（含 LLM 调用）|
| /api/health 响应 | ≤ 100ms |
| 并发 10 请求 | 无 5xx |

---

## 部署规范

### CORS 配置

```python
# ✅ 正确：从环境变量读取
origins = os.getenv(
    "BACKEND_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    ...
)

# ❌ 禁止：硬编码
origins = ["http://localhost:3000"]  # 禁止
```

### 环境变量

| 变量 | 默认值 | 说明 |
|:-----|:------:|:-----|
| `BACKEND_CORS_ORIGINS` | `http://localhost:3000` | 跨域白名单 |
| `API_HOST` | `0.0.0.0` | 监听地址 |
| `API_PORT` | `8000` | 监听端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 审查清单

- [ ] 每个 endpoint 区分 200/404/500/503？
- [ ] 所有同步调用有超时？
- [ ] CORS 从环境变量读取？
- [ ] 不直接调 akshare/adata（通过 DataCollector）？
- [ ] 路由函数 ≤ 50 行？
- [ ] 每个异常路径有日志？
- [ ] 前端 API 变更通知了？

# 18 FastAPI 路由测试：TestClient + MockCollector 模式

## 一句话

> FastAPI 路由测试的核心技巧：用 `TestClient` 做 HTTP 请求，用 `MockCollector` 隔离数据源层，让你不碰网络就测遍所有端点。

---

## 为什么需要它？

### 问题场景

后端的 FastAPI 路由通常长这样：

```python
router = APIRouter(prefix="/api/market")
collector = DataCollector()  # ← 模块级全局实例

@router.get("/indices")
async def get_indices():
    quotes = await run_sync(collector.get_realtime_quotes)
    ...
```

问题很明显：`DataCollector` 内部调 akshare（东方财富 API），单元测试不能真的去连网。不 mock 的话，测试要么慢、要么网络挂了全跳过、要么烧 API 额度。

一个常见的错误是直接在测试里 patch akshare 的每个函数：

```python
# ❌ 太脆弱：改了数据源（akshare → adata）所有测试报废
with patch("akshare.stock_zh_index_spot_em", return_value=...):
    ...
```

### 它的解法

**MockCollector 模式**：把 mock 点从"底层数据源"上提到"应用层接口"，让测试只关心路由逻辑，不关心数据从哪来。

```
测试 → HTTP → TestClient → 路由函数 → MockCollector（静态数据）
                                      ↛ 不碰 akshare / adata / 网络
```

这样换了数据源，路由测试一行都不用改。

---

## 项目里的真实代码

打开 `tests/test_backend/conftest.py`：

```python
class MockCollector:
    """模拟 DataCollector，所有方法为同步

    通过属性配置返回数据：
        mock._quotes     — get_realtime_quotes / get_realtime_quote
        mock._stocks     — get_all_stocks
        mock._klines     — get_klines
        mock._news       — get_news
        mock._capital_flow — get_capital_flow
        mock._boards     — get_industry_boards
    """

    def __init__(self) -> None:
        # 默认数据：三大指数
        self._quotes: list[StockQuote] = [
            make_mock_quote(code="000001", name="上证指数", price=3200.0),
            make_mock_quote(code="399001", name="深证成指", price=10500.0),
            make_mock_quote(code="399006", name="创业板指", price=2200.0),
        ]
        # 更多默认数据...

    def get_realtime_quotes(self) -> list[StockQuote]:
        return self._quotes

    def get_realtime_quote(self, code: str) -> StockQuote | None:
        for q in self._quotes:
            if q.code == code:
                return q
        return None

    # ... 全部方法签名与原 DataCollector 一致


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture
def mock_collector() -> MockCollector:
    return MockCollector()
```

然后测试里这样用：

```python
class TestGetIndices:
    def test_returns_indices(self, client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3

    def test_missing_index_fills_default(self, client, mock_collector):
        mock_collector._quotes = []  # ← 空行情场景
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        assert all(item["price"] == 0.0 for item in resp.json()["data"])
```

关键技巧：

1. **MockCollector 是完整实现的类，不是 MagicMock** — 每个方法有明确的返回值，可读性强
2. **通过属性修改行为** — `mock._quotes = []` 模拟空数据，不需要重写 mock 方法
3. **router 模块级的 `collector` 被替换** — `patch("backend.routers.market.collector", mock_collector)`，因为路由文件的 `collector = DataCollector()` 是模块全局

### 对 debate/trust 这类有惰性导入的路由

debate 和 trust 路由用 `_get_orchestrator()` / `_get_tracker()` 惰性加载，不走模块级全局。所以 patch 点不一样：

```python
# ✅ 正确：patch 惰性导入函数
with patch("backend.routers.debate._get_orchestrator", return_value=mock_orch):
    resp = client.post("/api/debate/run", json={"stock_code": "000001"})
```

---

## 和 patch("akshare.xxx") 有什么不同？

| 对比 | 直接 patch akshare | MockCollector 模式 |
|:-----|:-------------------|:-------------------|
| **mock 点** | 底层数据源（akshare/adata 函数） | 应用层 DataCollector |
| **换数据源影响** | 所有测试 patch 报废 | ✅ 测试一行不改 |
| **空数据/异常场景** | 需要 mock 不同函数 | ✅ 改一个属性即可 |
| **可读性** | 散落在各测试文件的 patch 中 | ✅ 集中在 conftest.py |
| **维护成本** | 高 | ✅ 低 |

---

## 面试会怎么问

> **Q: FastAPI 路由测试怎么隔离数据库/外部 API？**
>
> A: 用 `TestClient` 发 HTTP 请求，用 `unittest.mock.patch` 替换路由依赖的全局对象。对于项目规范，应该在 `conftest.py` 定义 `TestClient` fixture 和专用 mock 类（如 MockCollector），测试文件只关心断言。

> **Q: 路由模块的全局变量（如 `collector = DataCollector()`）怎么在测试中替换？**
>
> A: `with patch("模块路径.collector", mock_instance)` — Python 的 `patch` 在 `with` 块中替换模块命名空间里的名字。直接替换实例，不替换类。

---

## 自己试试（5 分钟）

1. 打开 `tests/test_backend/conftest.py`，找到 `MockCollector` 类
2. 打开 `tests/test_backend/test_market.py`，看 `TestGetIndices` 怎么用 `mock_collector._quotes = []` 模拟空数据
3. 再打开 `tests/test_backend/test_debate.py`，看 debate 路由用了不同的 patch 策略（`_get_orchestrator`）
4. 思考题：如果要测「网络超时」场景，MockCollector 需要加什么方法？

---

**上一篇：[测试架构与模块自治](17-testing-architecture.md)**

**下一篇：*待续***

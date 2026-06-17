# 04 FastAPI 桥接层架构

## 一句话

> FastAPI 是**连接 Python 后端和前端浏览器的桥梁**。前端要数据，通过 HTTP 问 FastAPI；FastAPI 从 Python 系统拿到数据，包装成 JSON 回给前端。

---

## 为什么需要桥接层？

我们的系统是 Python（LangGraph + Pydantic），前端是 JavaScript（React / Next.js）。

**Python 不能直接和 JavaScript 说话。** 它们需要一种共同语言——HTTP + JSON。

```
浏览器 (JavaScript)  ──HTTP请求──→  FastAPI (Python)  ──调用──→  Agent系统
                     ←──JSON响应──                   ←──返回──
```

FastAPI 在这里的作用：
1. **翻译** — 把 HTTP 请求转成 Python 函数调用
2. **数据包装** — 把 Python 对象（Pydantic Model）转成 JSON
3. **路由组织** — 不同的功能走不同的 URL

---

## 目录结构

打开 `backend/` 目录：

```
backend/
├── main.py                 # 入口，启动服务器
├── config.py               # 后端配置
├── indicators.py           # 技术指标计算
├── routers/
│   ├── stocks.py           # /api/stocks/  → 股票相关
│   ├── market.py           # /api/market/  → 板块/大盘
│   ├── debate.py           # /api/debate/  → AI 辩论
│   └── trust.py            # /api/trust/   → 信任度
```

每个路由文件负责一类 API。

---

## 一个典型的路由

打开 `backend/routers/stocks.py`：

```python
from fastapi import APIRouter

# 创建一个路由器，所有路由以 /api/stocks 开头
router = APIRouter(prefix="/api/stocks", tags=["stocks"])

@router.get("/{code}/quote")        # GET /api/stocks/000001/quote
async def get_quote(code: str):
    """获取股票行情"""
    data = await stock_service.get_quote(code)
    return {"code": code, "data": data}

@router.get("/{code}/news")         # GET /api/stocks/000001/news
async def get_news(code: str, limit: int = 10):
    """获取股票新闻"""
    news = await stock_service.get_news(code, limit)
    return {"code": code, "news": news}
```

### URL 是怎么设计的？

| 前端调用 | FastAPI 路由 | 对应的 backend 方法 |
|:---------|:------------|:-------------------|
| `GET /api/stocks/000001/quote` | `@router.get("/{code}/quote")` | `stock_service.get_quote("000001")` |
| `GET /api/market/sectors` | `@router.get("/sectors")` | `market_service.get_sectors()` |
| `POST /api/debate/start` | `@router.post("/start")` | `debate_service.start_debate(...)` |

规律很清晰：**URL 路径 ≈ 函数调用，参数在路径或查询参数里。**

---

## 异步（async）为什么重要

FastAPI 天生的异步支持：

```python
@router.get("/{code}/debate")
async def get_debate(code: str):     # ← async 关键字
    # 同时做两件事 ↓
    quote = await fetch_quote(code)  # 等行情（等待时不阻塞）
    news = await fetch_news(code)    # 等新闻（等待时不阻塞）
    # 实际上面前两行可以并行：
    quote, news = await asyncio.gather(
        fetch_quote(code),
        fetch_news(code)
    )
    return {"quote": quote, "news": news}
```

**前端请求 → 不会因为等 Python 数据而卡住整个服务器。** 这就是异步的意义。

---

## 从前端到后端的数据流

```
用户在浏览器搜索 "000001"
  → 前端：fetch("/api/stocks/000001/quote")
  → FastAPI：调用 stock_service.get_quote("000001")
  → Python 业务层：从 akshare 拿数据
  → 返回 Pydantic Model
  → FastAPI：自动转成 JSON
  → 前端：拿到 JSON，渲染到页面上
```

整个过程对用户来说就是"搜索 → 看到结果"。

---

## 和直接在 Python 里做 Web 有什么区别？

| | Flask | Streamlit | FastAPI |
|:--|:-------|:-----------|:--------|
| 异步 | 不支持（慢） | 不支持 | 原生支持 ✅ |
| 自动文档 | 无 | 无 | Swagger UI ✅ |
| 性能 | 一般 | 差（每次 rerun 全页） | 高 ✅ |
| 类型校验 | 手写 | 无 | Pydantic 自动 ✅ |

---

## 自己试试（5 分钟）

1. 启动后端：
   ```bash
   cd e:/litchi-head && python -m uvicorn backend.main:app --port 8000
   ```
2. 打开浏览器访问 `http://localhost:8000/docs` — 你会看到 Swagger UI 文档，**所有 API 自动生成的可交互页面**
3. 试试调一个 API：
   ```bash
   curl http://localhost:8000/api/stocks/000001/quote
   ```
4. 打开 `backend/main.py`，找到 `app = FastAPI()` 下面怎么引入路由的

---

**上一篇：[LLM 统一封装层](03-llm-unified-layer.md)**

**下一篇：[Provider 抽象模式（数据源）](05-provider-pattern.md)** — 多种数据源切换的设计

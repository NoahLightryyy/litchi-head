# litchi-head FastAPI 桥接层

> 连接 Python 后端（akshare / LangGraph / TrustTracker / 技术指标）与 React 前端的 API 中间层。

## 架构定位

```
[React 前端] ← HTTP/JSON → [FastAPI 桥接层] ← 直接调用 → [Python 后端]
  localhost:3000          localhost:8000               src/
```

桥接层不做业务逻辑——只是将 Python 类的调用转换成 HTTP API。

## 快速启动

```bash
# 安装依赖（首次）
pip install -r requirements.txt

# 启动开发服务器
uvicorn main:app --reload --port 8000

# API 文档
# → http://localhost:8000/docs
```

生产环境自动配置数据源（见 `config.py`）：
```bash
LITCHI_DATASOURCE=auto uvicorn main:app --port 8000
```

## 目录结构

```
backend/
├── main.py              # FastAPI 入口 + CORS + 异常处理 + 健康检查
├── config.py            # 生产数据源配置（adata / akshare 自动切换）
├── indicators.py        # 技术指标离线计算（MA/RSI/MACD/布林带，纯 Python）
├── requirements.txt     # fastapi + uvicorn + sse-starlette + adata
└── routers/
    ├── __init__.py
    ├── market.py        # /api/market/* — 指数 / 板块 / 板块详情 / AI 简报（TD-020 ✅）
    ├── stocks.py        # /api/stocks/* — 搜索 / 行情 / K 线 / 新闻 / 资金流向 / 技术指标
    ├── debate.py        # /api/debate/* — 辩论触发 / 状态轮询 / 结果获取
    └── trust.py         # /api/trust/* — 信任度报告 / 排行榜（TrustTracker 完整接入）
```

## API 端点

| 方法 | 路径 | 说明 | 状态 |
|:----:|:-----|:------|:----:|
| GET | `/api/health` | 健康检查 | ✅ |
| GET | `/api/health/data-source` | 数据源健康监控 | ✅ |
| GET | `/api/market/indices` | 三大指数实时行情 | ✅ |
| GET | `/api/market/sectors` | 板块排行（含涨跌幅+主力净流入+热度和top_stocks） | ✅ TD-020 |
| GET | `/api/market/sector/{id}` | 板块详情 + 产业链映射 + AI 分析 | ✅ TD-020 |
| GET | `/api/market/brief` | AI 宏观简报 | ✅ |
| GET | `/api/stocks/search` | 股票搜索 | ✅ |
| GET | `/api/stocks/{code}/quote` | 个股实时行情 | ✅ |
| GET | `/api/stocks/{code}/kline` | K 线数据 | ✅ |
| GET | `/api/stocks/{code}/news` | 个股新闻 | ✅ |
| GET | `/api/stocks/{code}/capital-flow` | 资金流向（主力/散户/机构） | ✅ |
| GET | `/api/stocks/{code}/technical-indicators` | 技术指标（MA/RSI/MACD/布林带） | ✅ |
| POST | `/api/debate/run` | 触发 AI 辩论 | ✅ |
| GET | `/api/debate/status/{id}` | 辩论状态查询 | ✅ |
| GET | `/api/debate/result/{id}` | 辩论结果获取 | ✅ |
| GET | `/api/trust/report/{name}` | 信任度报告 | ✅ |
| GET | `/api/trust/leaderboard` | 信任度排行榜 | ✅ |

## 关键设计

- **CORS**：允许 `localhost:3000` + `127.0.0.1:3000` 跨域访问
- **缓存头**：所有返回数据含 `meta.cached` 和 `latency_ms`
- **错误转换**：Python 异常 → `{ error: { code, message } }` 统一格式
- **惰性导入**：`debate.py` 用 `_get_orchestrator()` 懒加载，避免 Windows torch crash
- **生产数据源**：`lifespan` 启动时自动调用 `config.setup_production_source()`，支持 `LITCHI_DATASOURCE` 环境变量

## 响应格式

```json
{
  "data": { ... },
  "meta": {
    "cached": false,
    "latency_ms": 123
  }
}
```

## 技术栈

| 层 | 技术 |
|:---|:-----|
| 框架 | FastAPI 0.137+ |
| 运行时 | Uvicorn 0.49+ |
| 数据源 | akshare / adata（双源自动 fallback） |
| 技术指标 | 纯 Python 计算，无 numpy/ta-lib 依赖 |
| Python | 3.12+（与后端一致） |

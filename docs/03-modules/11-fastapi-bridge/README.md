# FastAPI 桥接层 — litchi-head

> 连接 Python 后端（akshare / LangGraph / TrustTracker）与 React 前端的 API 中间层。

## 职责

| 功能 | 对接后端 | 说明 |
|:-----|:---------|:-----|
| 指数行情 | `src/data/collector.py` | 上证/深证/创业板实时行情 |
| 板块排行 | `src/data/collector.py` | 行业/概念板块排行 + 资金流向 |
| 个股行情 | `src/data/collector.py` | 实时行情单只过滤 |
| K 线数据 | `src/data/collector.py` | 日/周/月 K 线 |
| 个股新闻 | `src/data/collector.py` | 新闻列表 |
| AI 辩论 | `src/debate/orchestrator.py` | 触发辩论并获取结果 |
| 信任度 | `src/debate/trust.py` | TrustTracker 查询 |

## 目录结构

```
backend/
├── main.py                 # FastAPI 入口 + CORS + 生命周期
├── requirements.txt        # 依赖（uvicorn, fastapi, sse-starlette）
├── routers/
│   ├── __init__.py
│   ├── market.py           # /api/market/*
│   ├── stocks.py           # /api/stocks/*
│   ├── debate.py           # /api/debate/*
│   └── trust.py            # /api/trust/*
└── README.md
```

## 快速开始

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API 文档: http://localhost:8000/docs
```

## 关键设计

- **CORS**：允许 `localhost:3000` 跨域访问
- **缓存头**：返回 `meta.cached` 和 `latency_ms` 供前端展示
- **错误转换**：将 Python 异常统一转换为 `{ error: { code, message } }` 格式
- **惰性导入**：避免 Windows 环境 torch 访问冲突（沿用 `src/debate/__init__.py` 模式）

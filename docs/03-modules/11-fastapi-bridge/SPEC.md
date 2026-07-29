# FastAPI 桥接层规格

## 1. 架构定位

```
[React 前端] ← HTTP/JSON → [FastAPI 桥接层] ← 直接调用 → [Python 后端]
   localhost:3000          localhost:8000               src/
```

桥接层不做业务逻辑——只是将 Python 类的调用转换成 HTTP API。

## 2. 路由实现

### market.py — `/api/market`

```python
from fastapi import APIRouter
from src.data.collector import DataCollector
from src.utils.llm import llm_service   # AI 宏观简报

router = APIRouter(prefix="/api/market")
collector = DataCollector()

@router.get("/indices")
async def get_indices():
    """三大指数行情"""
    quotes = collector.get_realtime_quotes()
    # 过滤出 000001(上证), 399001(深证), 399006(创业板)
    ...

@router.get("/sectors")
async def get_sectors(sort: str = "fund_flow"):
    """板块排行"""
    industry = collector.get_industry_boards()
    concept = collector.get_concept_boards()
    ...

@router.get("/sector/{sector_id}")
async def get_sector_detail(sector_id: str):
    """板块详情 + 产业链分析"""
    ...
```

### stocks.py — `/api/stocks`

```python
@router.get("/{code}/kline")
async def get_kline(code: str, period: str = "daily", start: str = "", end: str = ""):
    klines = collector.get_klines(code, period, start, end)
    return {"data": [k.model_dump() for k in klines]}
```

### debate.py — `/api/debate`

```python
# 惰性导入避免 torch crash
def _get_orchestrator():
    from src.debate.orchestrator import DebateOrchestrator
    return DebateOrchestrator(
        news_evidence_service=get_news_evidence_runtime().service,
        quote_evidence_service=get_realtime_quote_evidence_runtime().service,
    )

@router.post("/run")
async def run_debate(req: DebateRequest):
    orch = _get_orchestrator()
    result = await orch.run(DebateInput(stock_code=req.stock_code, question=req.question))
    return {"data": {"session_id": result.session_id, "status": "completed", "result": result.model_dump()}}
```

### evidence.py — `/api/v1/evidence`

```python
@router.post("/news/aggregate")
async def aggregate_news(payload: NewsAggregateRequest):
    """并发采集东方财富与新浪，返回统一 EvidenceEnvelope。"""

@router.post("/quotes/aggregate")
async def aggregate_quotes(payload: QuoteAggregateRequest):
    """并发采集并校验东方财富与新浪实时行情。"""
```

请求时间必须带时区。单源失败或时间窗覆盖不足仍返回完整逐源诊断；只有两个独立
上游都处于成功状态时，信封的 `complete` 才为 `true`。

实时行情聚合接口默认使用 `LITCHI_RATE_LIMIT_QUOTE_AGGREGATE=6/minute`，避免
重复请求耗尽线程和触发两家免费上游封禁。

`POST /api/debate/run` 固定请求最近 3 天新闻，并在连续竞价时请求双源实时行情。
新闻、行情任一必需上游不完整，或行情陈旧/错时/冲突时返回 HTTP 503。默认构造
`DebateOrchestrator()` 同样启用门禁，非 FastAPI 调用不能绕过：

```json
{
  "error": {
    "code": "EVIDENCE_INCOMPLETE",
    "message": "必要市场数据不完整或不一致，AI 分析未启动",
    "detail": {
      "missing_upstream_ids": ["sina"],
      "retry_after_seconds": 300
    }
  }
}
```

响应同时带 `Retry-After: 300`，失败会保存在 session 状态中，且不会调用 LLM。
若股票主数据无法解析名称，也返回同一错误码并标注缺失 `stock_name`，防止新浪
标题仅含公司名称时被误判为空。后台采集任务异常退出时 `/api/health` 返回
`status=degraded`、`news_ingestion=failed`。

## 3. CORS 配置

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)
```

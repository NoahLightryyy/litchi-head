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
    return DebateOrchestrator()

@router.post("/run")
async def run_debate(req: DebateRequest):
    orch = _get_orchestrator()
    result = await orch.run(DebateInput(stock_code=req.stock_code, question=req.question))
    return {"data": {"session_id": result.session_id, "status": "completed", "result": result.model_dump()}}
```

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

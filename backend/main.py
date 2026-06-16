"""FastAPI 桥接入口 —— litchi-head

将 Python 后端（akshare / LangGraph / TrustTracker）暴露为 HTTP API，
供 React 前端（localhost:3000）调用。

启动：
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routers import debate, market, stocks, trust

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-24s  %(message)s")
logger = logging.getLogger("backend")


# ── 全局错误响应格式 ──────────────────────────────────────────


class ErrorResponse(JSONResponse):
    """统一的 API 错误响应格式

    返回：{ error: { code, message } }
    """

    def __init__(self, code: str, message: str, status: int = 500, detail: object = None):
        body: dict[str, object] = {"error": {"code": code, "message": message}}
        if detail is not None:
            body["error"]["detail"] = detail  # type: ignore[assignment]
        super().__init__(body, status_code=status)


# ── 生命周期 ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子"""
    logger.info("FastAPI 桥接层启动 — http://localhost:8000")
    logger.info("API 文档: http://localhost:8000/docs")
    yield
    logger.info("FastAPI 桥接层关闭")


app = FastAPI(
    title="litchi-head API",
    description="多智能体投资决策平台 — FastAPI 桥接层",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # React dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────────────

app.include_router(market.router)
app.include_router(stocks.router)
app.include_router(debate.router)
app.include_router(trust.router)


# ── 全局异常处理 ──────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获未处理异常，统一返回错误格式"""
    logger.exception("未处理的异常: %s", exc)
    return ErrorResponse(
        code="INTERNAL_ERROR",
        message=f"服务器内部错误: {type(exc).__name__}",
        status=500,
    )


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "litchi-head-bridge", "timestamp": time.time()}


@app.get("/api/health/data-source")
async def data_source_health():
    """数据源健康统计

    返回 DataCollector 各 endpoint 的调用次数、失败率、延迟等指标。
    用于监控 akshare 数据源的实际运行状况。
    """
    from src.data.collector import get_health_stats  # noqa: PLC0415

    return {"status": "ok", "stats": get_health_stats().snapshot()}

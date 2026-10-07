"""FastAPI 桥接入口 —— litchi-head

将 Python 后端（akshare / LangGraph / TrustTracker）暴露为 HTTP API，
供 React 前端（localhost:3000）调用。

启动：
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded

from backend.limiter import limiter
from backend.routers import (
    company_research,
    debate,
    discovery,
    evidence,
    financials,
    market,
    news,
    news_archive,
    retro,
    sector_chain,
    stocks,
    trust,
    user_actions,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-24s  %(message)s")
logger = logging.getLogger("backend")


class DataSourceEndpointHealth(BaseModel):
    current_status: Literal["healthy", "failed", "empty"]
    total_calls: int = Field(ge=0)
    success: int = Field(ge=0)
    empty: int = Field(ge=0)
    failures: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0)
    avg_latency_ms: float | None = Field(default=None, ge=0.0)
    last_error: str | None = None
    last_error_code: str | None = None
    last_success_ago_s: float | None = Field(default=None, ge=0.0)


class DataSourceHealthSummary(BaseModel):
    total_calls: int = Field(ge=0)
    total_failures: int = Field(ge=0)
    total_empty: int = Field(ge=0)
    overall_failure_rate: float = Field(ge=0.0, le=1.0)
    healthy_endpoints: int = Field(ge=0)
    failing_endpoints: int = Field(ge=0)
    empty_endpoints: int = Field(ge=0)


class DataSourceHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    stats: dict[str, DataSourceEndpointHealth | DataSourceHealthSummary]


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

    from backend.routers.debate import _session_store  # noqa: PLC0415

    await _session_store.recover_interrupted()

    # ── 生产数据源配置 ──
    try:
        from backend.config import setup_production_source  # noqa: PLC0415
        source_name = setup_production_source()
        logger.info("数据源: %s", source_name)
    except Exception:
        logger.exception("数据源配置失败，使用默认 AKShareSource")

    from src.data.news_runtime import (  # noqa: PLC0415
        DEFAULT_POLL_SECONDS,
        get_news_evidence_runtime,
        run_news_ingestion_loop,
        validate_news_poll_seconds,
    )

    poll_seconds = validate_news_poll_seconds(
        int(os.getenv("LITCHI_NEWS_POLL_SECONDS", str(DEFAULT_POLL_SECONDS)))
    )
    from src.data.board_runtime import configure_board_store, warm_boards  # noqa: PLC0415

    configure_board_store(market.board_snapshots)
    board_task = asyncio.create_task(warm_boards(market.board_snapshots), name="board-warmup")
    app.state.board_warmup_task = board_task
    news_task = asyncio.create_task(
        run_news_ingestion_loop(
            get_news_evidence_runtime(),
            poll_seconds=poll_seconds,
        ),
        name="sina-rolling-news-ingestion",
    )
    app.state.news_ingestion_task = news_task
    from src.data.news_archive import run_archive_loop  # noqa: PLC0415

    archive_task = asyncio.create_task(run_archive_loop(), name="multi-channel-news-archive")
    try:
        yield
    finally:
        archive_task.cancel()
        with suppress(asyncio.CancelledError):
            await archive_task
        board_task.cancel()
        try:
            with suppress(asyncio.CancelledError):
                await board_task
        except Exception:
            logger.exception("Board warm-up task failed during shutdown")
        app.state.board_warmup_task = None
        news_task.cancel()
        with suppress(asyncio.CancelledError):
            await news_task
        app.state.news_ingestion_task = None
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
        "http://localhost:3001",        # Isolated preview frontend
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 速率限制 ──────────────────────────────────────────────────

app.state.limiter = limiter

# ── 路由注册 ──────────────────────────────────────────────────

app.include_router(market.router)
app.include_router(sector_chain.router)
app.include_router(stocks.router)
app.include_router(discovery.router)
app.include_router(company_research.router)
app.include_router(news.router)
app.include_router(news_archive.router)
app.include_router(financials.router)
app.include_router(debate.router)
app.include_router(trust.router)
app.include_router(retro.router)
app.include_router(evidence.router)
app.include_router(user_actions.router)


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


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """超过速率限制 → 429

    格式与现有 ErrorResponse 一致，前端可直接统一处理。
    """
    return ErrorResponse(
        code="RATE_LIMITED",
        message="请求过于频繁，请稍后再试",
        status=429,
    )


@app.get("/api/health")
async def health():
    """健康检查"""
    news_task = getattr(app.state, "news_ingestion_task", None)
    news_status = "not_started"
    status = "ok"
    if news_task is not None:
        news_status = "failed" if news_task.done() else "running"
        if news_task.done():
            status = "degraded"
    return {
        "status": status,
        "service": "litchi-head-bridge",
        "news_ingestion": news_status,
        "timestamp": time.time(),
    }


@app.get("/api/health/data-source", response_model=DataSourceHealthResponse)
async def data_source_health():
    """数据源健康统计

    返回 DataCollector 各 endpoint 的调用次数、失败率、延迟等指标。
    用于监控 akshare 数据源的实际运行状况。
    """
    from src.data.collector import get_health_stats  # noqa: PLC0415

    stats = get_health_stats().snapshot()
    summary = stats.get("__summary__", {})
    degraded = isinstance(summary, dict) and (
        int(summary.get("failing_endpoints", 0)) > 0
        or int(summary.get("empty_endpoints", 0)) > 0
    )
    return {"status": "degraded" if degraded else "ok", "stats": stats}

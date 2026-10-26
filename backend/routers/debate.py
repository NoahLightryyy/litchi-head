"""辩论路由 —— /api/debate/*

提供辩论触发、状态查询、结果获取等接口。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.async_utils import DATA_TIMEOUT, BoundedSyncRunner, run_sync
from backend.config import (
    RATE_LIMIT_DEBATE_RESULT,
    RATE_LIMIT_DEBATE_RUN,
    RATE_LIMIT_DEBATE_STATUS,
)
from backend.limiter import limiter
from backend.stock_identity import resolve_stock_name
from src.debate.models import DebateResult
from src.debate.session_store import DebateSessionRecord, SqliteDebateSessionStore

if TYPE_CHECKING:
    from src.debate.orchestrator import DebateOrchestrator

logger = logging.getLogger("backend.debate")
router = APIRouter(prefix="/api/debate")
_retro_quote_runner = BoundedSyncRunner(max_workers=2, thread_name_prefix="retro-quote")


async def _auto_create_retro_record(
    session_id: str,
    result: object,
    stock_code: str,
) -> None:
    """辩论完成后自动创建复盘记录，静默失败不影响主流程"""
    try:
        from uuid import uuid4 as _uuid4  # noqa: PLC0415

        from src.data.collector import DataCollector  # noqa: PLC0415
        from src.retro.models import RetroRecord  # noqa: PLC0415
        from src.retro.store import RetroStore  # noqa: PLC0415

        vs = getattr(result, "vote_summary", None)
        if vs is None:
            return

        stock_name = getattr(result, "stock_name", stock_code)
        consensus = getattr(vs, "consensus", "")
        weighted_score = getattr(vs, "weighted_score", 0.0)
        confidence = getattr(vs, "confidence", 0.0)
        direction_dist = getattr(vs, "direction_distribution", {})
        avg_score = getattr(vs, "average_score", 0.0)
        rating_dist = getattr(vs, "rating_distribution", {})
        total_latency = getattr(result, "total_latency_ms", 0.0)

        price_at_debate: float | None = None
        try:
            collector = DataCollector()
            quote = await asyncio.wait_for(
                _retro_quote_runner.run(collector.get_realtime_quote, stock_code),
                timeout=DATA_TIMEOUT,
            )
            if quote is not None:
                price_at_debate = float(quote.price)
            if price_at_debate is not None and price_at_debate <= 0:
                price_at_debate = None
        except Exception:
            logger.warning("Retro entry price unavailable: symbol=%s", stock_code)

        record = RetroRecord(
            record_id=f"retro_{_uuid4().hex[:12]}",
            session_id=session_id,
            stock_code=stock_code,
            stock_name=stock_name,
            debate_latency_ms=round(total_latency, 0),
            consensus=consensus,
            weighted_score=round(weighted_score, 2),
            confidence=round(confidence, 4),
            direction_distribution=dict(direction_dist) if direction_dist else {},
            avg_score=round(avg_score, 2),
            rating_distribution=dict(rating_dist) if rating_dist else {},
            price_at_debate=price_at_debate,
        )

        store = RetroStore()
        await store.put(record)
        logger.info(
            "✅ 自动创建复盘记录: %s | %s | 共识=%s 置信度=%.2f",
            record.record_id[-8:],
            stock_code,
            consensus,
            confidence,
        )
    except Exception:
        logger.exception("自动创建复盘记录失败（静默）: session=%s", session_id)


# ── 请求模型 ──────────────────────────────────────────────────


class DebateRequest(BaseModel):
    """辩论请求"""

    stock_code: str = Field(pattern=r"^[0-9]{6}$")
    instrument_type: Literal["stock", "etf"] = "stock"
    question: str = ""


class DebateUnavailableError(BaseModel):
    code: Literal[
        "ANALYSIS_NOT_CONFIGURED", "EVIDENCE_INCOMPLETE", "ETF_NOT_FOUND",
        "INSTRUMENT_TYPE_MISMATCH",
    ]
    message: str
    detail: dict[str, Any]


class DebateUnavailableResponse(BaseModel):
    error: DebateUnavailableError


class DebateRunData(BaseModel):
    session_id: str
    status: Literal["completed"]
    stock_code: str
    instrument_type: Literal["stock", "etf"]


class DebateRunResponse(BaseModel):
    data: DebateRunData
    meta: dict[str, int]


class DebateStatusData(BaseModel):
    status: Literal["queued", "running", "completed", "failed", "not_found", "unknown"]
    progress: int
    session_id: str | None = None
    stock_code: str | None = None
    instrument_type: Literal["stock", "etf"] | None = None
    error: str | None = None


class DebateStatusResponse(BaseModel):
    data: DebateStatusData


class DebateResultResponse(BaseModel):
    data: DebateResult | None


# ── 惰性导入 ──────────────────────────────────────────────────


def _get_orchestrator():
    """惰性导入 DebateOrchestrator，避免 Windows torch crash"""
    from backend.debate_research import supplement_research
    from src.data.news_runtime import get_news_evidence_runtime  # noqa: PLC0415
    from src.data.quote_runtime import (  # noqa: PLC0415
        get_realtime_quote_evidence_runtime,
    )
    from src.debate.orchestrator import DebateOrchestrator  # noqa: PLC0415

    return DebateOrchestrator(
        research_supplement=supplement_research,
        news_evidence_service=get_news_evidence_runtime().service,
        quote_evidence_service=get_realtime_quote_evidence_runtime().service,
    )


async def _get_etf_orchestrator(code: str) -> tuple[str, DebateOrchestrator]:
    """Resolve ETF identity and collect its own inputs before using the same debate graph."""
    from backend.etf_display import get_catalog
    from backend.etf_research import NoUsableEtfResearchError, collect_etf_research
    from src.debate.etf_analysts import get_etf_analysts
    from src.debate.orchestrator import DebateOrchestrator

    try:
        async with asyncio.timeout(30):
            catalog = await get_catalog()
            identity = next((item for item in catalog.items if item.code == code), None)
            if identity is None:
                raise HTTPException(404, "未在ETF目录中找到该代码，ETF辩论未启动。")
            context = await collect_etf_research(identity, catalog)
    except HTTPException:
        raise
    except NoUsableEtfResearchError as exc:
        raise HTTPException(
            503, "ETF行情、日线和相关资料均暂不可用，分析未启动，请稍后重试。"
        ) from exc
    except Exception as exc:
        logger.exception("ETF research preparation failed: code=%s", code)
        raise HTTPException(503, "ETF资料准备暂时失败，请稍后重试。") from exc
    return identity.name, DebateOrchestrator(
        analyst_personas=get_etf_analysts(),
        prepared_research=context,
        quote_evidence_service=None,
        news_evidence_service=None,
    )


# Local deployment uses one backend process; completed results survive restarts.
_session_store = SqliteDebateSessionStore("data/debate/sessions.db")


async def _save_session(session_id: str, req: DebateRequest, data: dict[str, Any]) -> None:
    previous = await _session_store.get(session_id)
    await _session_store.save(
        DebateSessionRecord(
            session_id=session_id,
            stock_code=req.stock_code,
            instrument_type=req.instrument_type,
            question=req.question or "",
            created_at=previous.created_at if previous else datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **{key: value for key, value in data.items() if key != "detail"},
        )
    )


class DebateHistoryItem(BaseModel):
    session_id: str
    stock_code: str
    instrument_type: Literal["stock", "etf"] = "stock"
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class DebateHistoryResponse(BaseModel):
    data: list[DebateHistoryItem]


@router.get("/history", response_model=DebateHistoryResponse)
@limiter.limit(RATE_LIMIT_DEBATE_STATUS)
async def debate_history(
    request: Request,
    stock_code: str = Query(pattern=r"^\d{6}$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    instrument_type: Literal["stock", "etf"] = "stock",
):
    records = await _session_store.list_records(
        stock_code, limit=limit, offset=offset, instrument_type=instrument_type
    )
    return {"data": [DebateHistoryItem.model_validate(record.model_dump()) for record in records]}


def _analysis_is_configured() -> bool:
    """Check presence only; never log or return credentials."""
    from src.utils.config import settings  # noqa: PLC0415

    return settings.llm_provider == "deepseek" and bool(settings.deepseek_api_key.strip())


@router.post(
    "/run",
    response_model=DebateRunResponse,
    responses={
        503: {"model": DebateUnavailableResponse},
        404: {"model": DebateUnavailableResponse},
        409: {"model": DebateUnavailableResponse},
    },
)
@limiter.limit(RATE_LIMIT_DEBATE_RUN)
async def run_debate(request: Request, req: DebateRequest):
    """触发一次辩论"""
    if not _analysis_is_configured():
        logger.warning("Analysis configuration unavailable; inference not started")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "ANALYSIS_NOT_CONFIGURED",
                    "message": "DeepSeek 分析服务尚未配置，AI 分析未启动",
                    "detail": {"capability": "analysis_service", "retryable": False},
                }
            },
        )
    t0 = time.time()
    session_id = f"deb_{uuid4().hex[:12]}"
    await _save_session(session_id, req, {"status": "running", "progress": 0})

    try:
        orch = None
        if req.instrument_type == "etf":
            stock_name, orch = await _get_etf_orchestrator(req.stock_code)
        else:
            try:
                stock_name = await run_sync(resolve_stock_name, req.stock_code)
            except TimeoutError:
                logger.warning("Stock identity lookup timed out: symbol=%s", req.stock_code)
                stock_name = ""
        if req.instrument_type == "stock" and "ETF" in stock_name.upper():
            message = "该行情属于ETF，请从ETF页面启动基金分析。"
            await _save_session(session_id, req, {
                "status": "failed", "progress": 0, "error": message,
            })
            return JSONResponse(status_code=409, content={"error": {
                "code": "INSTRUMENT_TYPE_MISMATCH", "message": message,
                "detail": {"retryable": False, "expected_instrument_type": "etf"},
            }})
        if not stock_name:
            detail = {
                "capability": "stock_identity",
                "missing_fields": ["stock_name"],
                "retry_after_seconds": 300,
            }
            await _save_session(
                session_id,
                req,
                {
                    "status": "failed",
                    "progress": 0,
                    "error": "EVIDENCE_INCOMPLETE",
                    "detail": detail,
                },
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "EVIDENCE_INCOMPLETE",
                        "message": "股票基础信息不可用，AI 分析未启动",
                        "detail": detail,
                    }
                },
                headers={"Retry-After": "300"},
            )
        orch = orch or _get_orchestrator()
        from src.debate.models import DebateInput  # noqa: PLC0415

        result = await orch.run(
            DebateInput(
                session_id=session_id,
                stock_code=req.stock_code,
                instrument_type=req.instrument_type,
                stock_name=stock_name,
                question=(
                    f"研究对象：{stock_name}（{req.stock_code}，场内ETF）。"
                    "分析基金主题、价格趋势、流动性和相关政策，不能将基金当成经营公司，"
                    "不能从名称推断完整持仓、净值、折溢价或跟踪误差。\n"
                    + (req.question or "请从各流派分析此ETF的研究价值与风险。")
                    if req.instrument_type == "etf"
                    else req.question or ""
                ),
            )
        )
        await _save_session(
            session_id,
            req,
            {
                "status": "completed",
                "progress": 100,
                "result": result.model_dump() if hasattr(result, "model_dump") else result,
            },
        )

        # ── 自动记录复盘 ──────────────────────────────
        if req.instrument_type == "stock":
            await _auto_create_retro_record(session_id, result, req.stock_code)
        return {
            "data": {
                "session_id": session_id,
                "status": "completed",
                "stock_code": req.stock_code,
                "instrument_type": req.instrument_type,
            },
            "meta": {"latency_ms": round((time.time() - t0) * 1000)},
        }
    except Exception as exc:
        from src.debate.evidence_gate import EvidenceIncompleteError  # noqa: PLC0415

        if isinstance(exc, HTTPException) and req.instrument_type == "etf":
            await _save_session(
                session_id,
                req,
                {
                    "status": "failed",
                    "progress": 0,
                    "error": str(exc.detail),
                },
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": "ETF_NOT_FOUND"
                        if exc.status_code == 404
                        else "EVIDENCE_INCOMPLETE",
                        "message": str(exc.detail),
                        "detail": {
                            "capability": "etf_research",
                            "retryable": exc.status_code != 404,
                        },
                    }
                },
            )
        if isinstance(exc, EvidenceIncompleteError):
            detail = exc.detail()
            logger.warning(
                "必要证据不完整，辩论未启动: stock_code=%s detail=%s",
                req.stock_code,
                detail,
            )
            await _save_session(
                session_id,
                req,
                {
                    "status": "failed",
                    "progress": 0,
                    "error": "EVIDENCE_INCOMPLETE",
                    "detail": detail,
                },
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "EVIDENCE_INCOMPLETE",
                        "message": "必要市场数据不完整或不一致，AI 分析未启动",
                        "detail": detail,
                    }
                },
                headers={"Retry-After": str(exc.retry_after_seconds)},
            )
        logger.exception("辩论执行失败: stock_code=%s", req.stock_code)
        await _save_session(
            session_id,
            req,
            {"status": "failed", "progress": 0, "error": "分析执行失败，请检查数据状态后重试。"},
        )
        raise HTTPException(status_code=500, detail=f"辩论执行失败: {req.stock_code}")


@router.get(
    "/status/{session_id:str}",
    response_model=DebateStatusResponse,
    response_model_exclude_unset=True,
)
@limiter.limit(RATE_LIMIT_DEBATE_STATUS)
async def get_debate_status(request: Request, session_id: str):
    """查询辩论状态"""
    record = await _session_store.get(session_id)
    session = record.model_dump(mode="json") if record else None
    if session is None:
        return {"data": {"status": "not_found", "progress": 0}}
    return {
        "data": {
            "session_id": session_id,
            "stock_code": session.get("stock_code"),
            "instrument_type": session.get("instrument_type", "stock"),
            "status": session.get("status", "unknown"),
            "progress": session.get("progress", 0),
            "error": session.get("error"),
        }
    }


@router.get("/result/{session_id:str}", response_model=DebateResultResponse)
@limiter.limit(RATE_LIMIT_DEBATE_RESULT)
async def get_debate_result(request: Request, session_id: str):
    """获取辩论结果"""
    record = await _session_store.get(session_id)
    session = record.model_dump(mode="json") if record else None
    if session is None:
        return {"data": None}
    return {
        "data": session.get("result"),
    }

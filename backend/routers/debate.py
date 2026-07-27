"""辩论路由 —— /api/debate/*

提供辩论触发、状态查询、结果获取等接口。
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import (
    RATE_LIMIT_DEBATE_RESULT,
    RATE_LIMIT_DEBATE_RUN,
    RATE_LIMIT_DEBATE_STATUS,
)
from backend.limiter import limiter

logger = logging.getLogger("backend.debate")
router = APIRouter(prefix="/api/debate")


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
            quote = collector.get_realtime_quote(stock_code)
            if quote is not None:
                price_at_debate = float(quote.price)
            if price_at_debate is not None and price_at_debate <= 0:
                price_at_debate = None
        except Exception:
            pass

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
    stock_code: str
    question: str = ""


# ── 惰性导入 ──────────────────────────────────────────────────


def _get_orchestrator():
    """惰性导入 DebateOrchestrator，避免 Windows torch crash"""
    from src.debate.orchestrator import DebateOrchestrator  # noqa: PLC0415

    return DebateOrchestrator()


# ── 内存状态存储（简化版，生产环境应换 Redis） ──────────────

_debate_sessions: dict[str, dict[str, Any]] = {}


@router.post("/run")
@limiter.limit(RATE_LIMIT_DEBATE_RUN)
async def run_debate(request: Request, req: DebateRequest):
    """触发一次辩论"""
    t0 = time.time()
    session_id = f"deb_{uuid4().hex[:12]}"
    _debate_sessions[session_id] = {"status": "running", "progress": 0}

    try:
        orch = _get_orchestrator()
        from src.debate.models import DebateInput  # noqa: PLC0415

        result = await orch.run(
            DebateInput(stock_code=req.stock_code, question=req.question or "")
        )
        _debate_sessions[session_id] = {
            "status": "completed",
            "progress": 100,
            "result": result.model_dump() if hasattr(result, "model_dump") else result,
        }

        # ── 自动记录复盘 ──────────────────────────────
        await _auto_create_retro_record(session_id, result, req.stock_code)
        return {
            "data": {"session_id": session_id, "status": "completed"},
            "meta": {"latency_ms": round((time.time() - t0) * 1000)},
        }
    except Exception:
        logger.exception("辩论执行失败: stock_code=%s", req.stock_code)
        _debate_sessions[session_id] = {"status": "failed", "progress": 0}
        raise HTTPException(status_code=500, detail=f"辩论执行失败: {req.stock_code}")


@router.get("/status/{session_id:str}")
@limiter.limit(RATE_LIMIT_DEBATE_STATUS)
async def get_debate_status(request: Request, session_id: str):
    """查询辩论状态"""
    session = _debate_sessions.get(session_id)
    if session is None:
        return {"data": {"status": "not_found", "progress": 0}}
    return {
        "data": {
            "session_id": session_id,
            "status": session.get("status", "unknown"),
            "progress": session.get("progress", 0),
        }
    }


@router.get("/result/{session_id:str}")
@limiter.limit(RATE_LIMIT_DEBATE_RESULT)
async def get_debate_result(request: Request, session_id: str):
    """获取辩论结果"""
    session = _debate_sessions.get(session_id)
    if session is None:
        return {"data": None}
    return {
        "data": session.get("result"),
    }

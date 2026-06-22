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

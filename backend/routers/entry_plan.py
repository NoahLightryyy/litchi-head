"""Read or explicitly generate a persisted conditional plan from an existing debate."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.entry_plan import (
    ENTRY_PLAN_PROMPT,
    EntryPlanDraft,
    EntryPlanError,
    EntryPlanRequest,
    EntryPlanResult,
    EntryPlanStore,
    build_entry_prompt,
    collect_entry_context,
    qualify_historical_conditions,
    research_time,
)
from backend.limiter import limiter
from backend.routers.debate import _session_store as sessions
from src.utils.llm import DEFAULT_MODEL, LLMConfig, llm_service

router = APIRouter(prefix="/api/debate", tags=["entry-plan"])
logger = logging.getLogger(__name__)
store = EntryPlanStore()
_busy: set[str] = set()
GENERATION_TIMEOUT = 120
SessionId = Annotated[str, Path(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


def failure(code: str, message: str, status: int, *, retryable: bool = True) -> JSONResponse:
    error = EntryPlanError.model_validate({"error": {
        "code": code, "message": message, "retryable": retryable,
    }})
    return JSONResponse(status_code=status, content=error.model_dump())


def configured() -> bool:
    from src.utils.config import settings

    return settings.llm_provider == "deepseek" and bool(settings.deepseek_api_key.strip())


@router.get("/{session_id}/entry-plan", response_model=EntryPlanResult | None,
            responses={503: {"model": EntryPlanError}})
async def read_entry_plan(session_id: SessionId) -> EntryPlanResult | None | JSONResponse:
    try:
        result = await asyncio.to_thread(store.get, session_id)
        return result.model_copy(update={"cached": True}) if result else None
    except Exception:
        logger.exception("Entry-plan read failed: session=%s", session_id)
        return failure("ENTRY_PLAN_READ_FAILED", "已保存的买入计划读取失败，请重试", 503)


@router.post("/{session_id}/entry-plan", response_model=EntryPlanResult,
             responses={status: {"model": EntryPlanError}
                        for status in (404, 409, 429, 502, 503, 504)})
@limiter.limit("6/minute")
async def generate_entry_plan(
    request: Request, session_id: SessionId, body: EntryPlanRequest,
) -> EntryPlanResult | JSONResponse:
    # Claim before the first await: no duplicate model calls for concurrent requests.
    if session_id in _busy or len(_busy) >= 2:
        return failure("ENTRY_PLAN_BUSY", "买入计划正在生成，请稍后读取结果或重试", 429)
    _busy.add(session_id)
    stage = "read"
    try:
        existing = await asyncio.to_thread(store.get, session_id)
        if existing is not None and not body.refresh:
            return existing.model_copy(update={"cached": True})
        record = await sessions.get(session_id)
        if record is None:
            return failure("ENTRY_PLAN_NOT_FOUND", "未找到这次辩论，请先完成标的分析", 404,
                           retryable=False)
        if record.status != "completed" or record.result is None:
            return failure("ENTRY_PLAN_SESSION_NOT_READY", "本次辩论尚未完成，完成后可生成买入计划",
                           409)
        if (record.session_id != session_id or record.result.session_id != session_id
                or record.result.stock_code != record.stock_code
                or record.result.instrument_type != record.instrument_type):
            raise ValueError("source debate identity mismatch")
        if not configured():
            return failure("ENTRY_PLAN_NOT_CONFIGURED", "DeepSeek分析服务尚未配置，买入计划未启动",
                           503, retryable=False)
        stage = "generation"
        async with asyncio.timeout(GENERATION_TIMEOUT):
            evidence, gaps = await collect_entry_context(record)
            prompt = build_entry_prompt(record, evidence, gaps)
            raw = await llm_service.invoke_structured(
                prompt=prompt, output_model=EntryPlanDraft, system_prompt=ENTRY_PLAN_PROMPT,
                provider="deepseek", agent_name="conditional_entry_plan", session_id=session_id,
                llm_config=LLMConfig(model=DEFAULT_MODEL, temperature=0.1, max_tokens=6500),
            )
            stage = "validation"
            draft = EntryPlanDraft.model_validate(raw.model_dump())
            result = EntryPlanResult(
                **draft.model_dump(), session_id=session_id, source_session_id=record.session_id,
                source_research_generated_at=research_time(record),
                stock_code=record.stock_code, instrument_type=record.instrument_type,
                stock_name=record.result.stock_name, generated_at=datetime.now(UTC),
                model=DEFAULT_MODEL, evidence=evidence, gaps=gaps,
            )
            result = qualify_historical_conditions(result)
        stage = "storage"
        await asyncio.to_thread(store.save, result)
        logger.info("Entry-plan persisted: session=%s instrument=%s code=%s",
                    session_id, result.instrument_type, result.stock_code)
        return result
    except TimeoutError:
        logger.warning("Entry-plan timeout: session=%s stage=%s", session_id, stage)
        return failure("ENTRY_PLAN_TIMEOUT",
                       "买入计划生成超时，已保存结果仍可查看，请稍后重试", 504)
    except Exception as exc:
        logger.exception("Entry-plan failed: session=%s stage=%s", session_id, stage)
        if stage == "read":
            return failure("ENTRY_PLAN_READ_FAILED", "辩论或买入计划读取失败，请重试", 503)
        if stage == "storage":
            return failure("ENTRY_PLAN_SAVE_FAILED", "买入计划已生成但保存失败，请重试", 503)
        if stage == "validation" or isinstance(exc, ValidationError):
            return failure("ENTRY_PLAN_INVALID_OUTPUT",
                           "买入计划未通过价格、条件或证据校验，请重新生成", 502)
        return failure("ENTRY_PLAN_FAILED", "买入计划生成失败，已保存结果仍可查看，请稍后重试", 502)
    finally:
        _busy.discard(session_id)

"""Read or explicitly generate an interpretation of server-retrieved related materials."""

import asyncio
import logging
import re

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse

from backend import related_interpretation as service
from backend.limiter import limiter
from backend.related_interpretation_contract import (
    RelatedInterpretationError,
    RelatedInterpretationErrorBody,
    RelatedInterpretationRequest,
    RelatedInterpretationResult,
)
from backend.related_keywords import extract_keywords
from backend.related_research_contract import SubjectKind

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research", tags=["related-interpretation"])


def failure(code: str, message: str, status: int) -> JSONResponse:
    result = RelatedInterpretationError(
        error=RelatedInterpretationErrorBody(
            code=code,
            message=message,
            retryable=status != 422,
        )
    )
    return JSONResponse(status_code=status, content=result.model_dump())


def validate_request(kind: SubjectKind, code: str, name: str, query: str) -> JSONResponse | None:
    pattern = r"(?:BK\d{4}|sina:[A-Za-z0-9_]+)" if kind == "sector" else r"\d{6}"
    if not re.fullmatch(pattern, code):
        return failure("RELATED_INTERPRETATION_INVALID_REQUEST", "标的代码格式无效", 422)
    if query.strip() and not extract_keywords(kind, code, name, query=query):
        return failure(
            "RELATED_INTERPRETATION_INVALID_REQUEST",
            "请填写中文关键词或至少两个字符的名称，多个词可用空格分隔",
            422,
        )
    return None


@router.get(
    "/related/interpretation",
    response_model=RelatedInterpretationResult | None,
    responses={503: {"model": RelatedInterpretationError}},
)
async def read_interpretation(
    kind: SubjectKind,
    code: str = Query(min_length=2, max_length=40),
    name: str = Query("", max_length=120),
    q: str = Query("", max_length=80),
) -> RelatedInterpretationResult | None | JSONResponse:
    invalid = validate_request(kind, code, name, q)
    if invalid is not None:
        return invalid
    try:
        return await asyncio.to_thread(service.get_saved, kind, code, q.strip())
    except Exception:
        logger.exception("Related interpretation read failed: kind=%s code=%s", kind, code)
        return failure(
            "RELATED_INTERPRETATION_READ_FAILED", "已保存的资料解读读取失败，请重试", 503
        )


@router.post(
    "/related/interpretation",
    response_model=RelatedInterpretationResult,
    responses={
        status: {"model": RelatedInterpretationError} for status in (422, 429, 502, 503, 504)
    },
)
@limiter.limit("6/minute")
async def write_interpretation(
    request: Request,
    kind: SubjectKind,
    code: str = Query(min_length=2, max_length=40),
    name: str = Query("", max_length=120),
    q: str = Query("", max_length=80),
    body: RelatedInterpretationRequest = Body(default=RelatedInterpretationRequest()),
) -> RelatedInterpretationResult | JSONResponse:
    invalid = validate_request(kind, code, name, q)
    if invalid is not None:
        return invalid
    try:
        return await service.generate_interpretation(
            kind, code, name.strip(), q.strip(), refresh=body.refresh
        )
    except service.RelatedInterpretationServiceError as exc:
        return failure(exc.code, exc.message, exc.status)

"""Automatic display-only policy and industry retrieval; never starts paid jobs."""

import logging
import re

from fastapi import APIRouter, HTTPException, Query

from backend.related_research import related_research
from backend.related_research_contract import RelatedResearchResult, SubjectKind

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research")


@router.get("/related", response_model=RelatedResearchResult)
async def related(
    kind: SubjectKind,
    code: str = Query(min_length=2, max_length=40),
    name: str = Query("", max_length=120),
    q: str = Query("", max_length=80),
) -> RelatedResearchResult:
    pattern = r"(?:BK\d{4}|sina:[A-Za-z0-9_]+)" if kind == "sector" else r"\d{6}"
    if not re.fullmatch(pattern, code):
        raise HTTPException(422, "标的代码格式无效")
    try:
        return await related_research(kind, code, name.strip(), q.strip())
    except Exception as exc:
        logger.exception("Related research request failed")
        raise HTTPException(503, "相关资料检索暂不可用，请重试。") from exc

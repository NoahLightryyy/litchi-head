"""Companion companies never replace or invalidate the saved structure."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse

from backend import chain_companies as service
from backend.chain_companies_contract import (
    ChainCompaniesError,
    ChainCompaniesRequest,
    ChainCompaniesResponse,
)
from backend.limiter import limiter
from backend.routers.chain_draft import load_draft

router = APIRouter(prefix="/api/market")
logger = logging.getLogger(__name__)
_busy: set[str] = set()
TIMEOUT = 120


def failure(code: str, message: str, status: int) -> JSONResponse:
    error = ChainCompaniesError.model_validate(
        {
            "error": {
                "code": code,
                "message": message,
                "retryable": status != 409,
            }
        }
    )
    return JSONResponse(status_code=status, content=error.model_dump())


@router.post(
    "/sector/{sector_id}/chain-companies",
    response_model=ChainCompaniesResponse,
    responses={code: {"model": ChainCompaniesError} for code in (409, 429, 502, 503, 504)},
)
@limiter.limit("6/minute")
async def representative_companies(
    request: Request,
    body: ChainCompaniesRequest,
    sector_id: Annotated[str, Path(pattern=r"^(BK\d{4}|sina:(new_|gn_)[A-Za-z0-9_]+)$")],
) -> ChainCompaniesResponse | JSONResponse:
    try:
        draft = load_draft(sector_id, body.sector_name)
        if draft is None:
            return failure("CHAIN_COMPANIES_NOT_READY", "产业结构尚未保存，请先完成绘图", 409)
        catalog = service.catalog_for(body.sector_name)
        key = service.cache_key(draft, catalog)
        if not body.refresh:
            existing = service.saved(draft, key)
            if existing:
                return existing
    except (ValueError, OSError):
        logger.exception("Company supplement storage read failed: %s", sector_id)
        return failure(
            "CHAIN_COMPANIES_STORAGE", "企业清单读取失败；可点击重新整理，原结构仍可查看", 503
        )
    if key in _busy or len(_busy) >= 2:
        return failure("CHAIN_COMPANIES_BUSY", "正在整理企业清单，请稍后读取", 429)
    _busy.add(key)
    try:
        async with asyncio.timeout(TIMEOUT):
            return await service.generate(draft, catalog, key)
    except TimeoutError:
        logger.warning("Company supplement timed out: %s", sector_id)
        return failure("CHAIN_COMPANIES_TIMEOUT", "企业清单整理超时，原结构仍可查看", 504)
    except OSError:
        logger.exception("Company supplement save failed: %s", sector_id)
        return failure("CHAIN_COMPANIES_STORAGE", "企业清单保存失败，原有记录未替换", 503)
    except Exception:
        logger.exception("Company supplement failed: %s", sector_id)
        return failure(
            "CHAIN_COMPANIES_FAILED", "企业清单暂未整理成功，可稍后重试；原结构仍可查看", 502
        )
    finally:
        _busy.discard(key)

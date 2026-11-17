"""ETF identity, quote and daily prices; analysis is served by the debate router."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse

from backend.etf_contract import EtfDetail, EtfKlineDisplay
from backend.etf_display import detail, get_catalog
from backend.etf_kline import get_etf_kline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/etfs", tags=["ETF"])


@router.get("/{code}", response_model=EtfDetail)
async def etf_detail(code: Annotated[str, Path(pattern=r"^\d{6}$")]) -> EtfDetail | JSONResponse:
    try:
        catalog = await get_catalog()
    except Exception:
        logger.exception("ETF catalog unavailable: code=%s", code)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "ETF_CATALOG_UNAVAILABLE",
                    "message": "ETF目录暂时不可用，请稍后重试",
                    "detail": {"retryable": True},
                }
            },
        )
    identity = next((item for item in catalog.items if item.code == code), None)
    if identity is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "ETF_NOT_FOUND",
                    "message": "未在当前ETF目录中找到此代码",
                    "detail": {"retryable": False},
                }
            },
        )
    return await detail(identity, catalog)


@router.get("/{code}/kline", response_model=EtfKlineDisplay)
async def etf_kline(
    code: Annotated[str, Path(pattern=r"^\d{6}$")],
    days: int = Query(90, ge=30, le=730),
) -> EtfKlineDisplay | JSONResponse:
    """Unadjusted ETF daily prices, with catalog-bound exchange and fund-unit volume."""
    try:
        catalog = await asyncio.wait_for(get_catalog(), timeout=8)
    except Exception:
        logger.exception("ETF catalog unavailable for daily chart: code=%s", code)
        return JSONResponse(status_code=503, content={"error": {
            "code": "ETF_CATALOG_UNAVAILABLE", "message": "ETF目录暂时不可用，请稍后重试",
            "detail": {"retryable": True},
        }})
    identity = next((item for item in catalog.items if item.code == code), None)
    if identity is None:
        return JSONResponse(status_code=404, content={"error": {
            "code": "ETF_NOT_FOUND", "message": "未在当前ETF目录中找到此代码",
            "detail": {"retryable": False},
        }})
    return await get_etf_kline(identity, days=days, include_today=True)

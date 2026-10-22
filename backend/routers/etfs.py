"""Display-only ETF routes; no stock research or trading semantics."""

import logging
from typing import Annotated

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse

from backend.etf_contract import EtfDetail
from backend.etf_display import detail, get_catalog

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

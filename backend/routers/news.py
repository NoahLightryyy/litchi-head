"""Company news display does not change the formal evidence API."""

from fastapi import APIRouter, HTTPException, Path, Query, Response

from backend.news_display import NewsDisplay, NewsDisplayService

router = APIRouter(prefix="/api/stocks")
service = NewsDisplayService()


@router.get(
    "/{code}/news-display",
    response_model=NewsDisplay,
    responses={503: {"model": NewsDisplay, "description": "Sources unavailable"}},
)
async def news_display(
    response: Response, code: str = Path(pattern=r"^\d{6}$"), days: int = Query(30, ge=7, le=90)
) -> NewsDisplay:
    if days not in {7, 30, 90}:
        raise HTTPException(status_code=422, detail="days must be 7, 30 or 90")
    try:
        result = await service.get(code, days)
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(
            status_code=503, detail="NEWS_BUSY", headers={"Retry-After": "5"}
        ) from exc
    if result.status == "failed":
        response.status_code = 503
    response.headers["Cache-Control"] = "no-store"
    return result

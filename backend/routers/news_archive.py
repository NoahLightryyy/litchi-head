"""Read-only archive browsing; collection runs independently in the application."""

from fastapi import APIRouter, Query

from backend.async_utils import run_sync
from src.data.news_archive import ArchivePage, archive

router = APIRouter(prefix="/api/news-archive")


@router.get("", response_model=ArchivePage)
async def archived_news(
    days: int = Query(7, ge=1, le=1095),
    channel: str = Query("", pattern=r"^(caixin|sina|eastmoney|cls|ths|futu)?$"),
    q: str = Query("", max_length=80),
    page: int = Query(1, ge=1, le=10000),
    as_of: str = Query(""),
) -> ArchivePage:
    from datetime import UTC, datetime

    from fastapi import HTTPException

    try:
        end = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
        if end.tzinfo is None or end > datetime.now(UTC):
            raise ValueError("Invalid archive as_of")
    except ValueError as exc:
        raise HTTPException(422, "as_of must be a past timezone-aware timestamp") from exc
    return await run_sync(
        archive.query, days=days, channel=channel, keyword=q.strip(), page=page, end=end
    )

"""Research-only reuse of last-session quotes and partially covered news."""

from datetime import datetime, time
from math import isfinite
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from src.data.evidence import EvidenceEnvelope, SourceStatus
from src.data.kline import market_code_for
from src.data.kline_calendar import CalendarCoverageError, official_a_share_calendar_2026
from src.data.models import NewsItem, StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")
_CALENDAR = official_a_share_calendar_2026()


class ResearchQuotes(BaseModel):
    quotes: list[StockQuote] = Field(default_factory=list)
    note: str = ""


def closing_research_quotes(envelope: EvidenceEnvelope, now: datetime) -> ResearchQuotes:
    """Reuse only the most recent completed session, never intraday/stale sessions."""
    local_now = now.astimezone(SHANGHAI)
    candidates: list[tuple[str, StockQuote]] = []
    for result in envelope.source_results:
        if result.status not in {SourceStatus.STALE, SourceStatus.SUCCESS_DATA}:
            continue
        if result.status is SourceStatus.STALE and result.error_code not in {
            "market_not_in_continuous_auction", "quote_stale",
        }:
            continue
        if len(result.items) != 1:
            continue
        quote = StockQuote.model_validate(result.items[0])
        stamp = quote.fetched_at
        if (
            quote.code != envelope.request.stock_code or not quote.name.strip()
            or not isfinite(quote.price) or quote.price <= 0
            or stamp is None or stamp.tzinfo is None
        ):
            continue
        stamp = stamp.astimezone(SHANGHAI)
        if stamp > local_now or stamp.time() < time(15):
            continue
        try:
            opened = _CALENDAR.open_dates(
                market_code_for(quote.code), stamp.date(), local_now.date(),
            )
        except CalendarCoverageError:
            continue
        if not opened:
            continue
        if opened[-1] == local_now.date() and local_now.time() < time(15):
            if local_now.time() >= time(9, 15):
                continue  # Includes auction and lunch; never relax intraday gates.
            opened = opened[:-1]
        if not opened or opened[-1] != stamp.date():
            continue
        candidates.append((result.upstream_id, quote))
    if not candidates:
        return ResearchQuotes()
    prices = [quote.price for _, quote in candidates]
    if max(prices) - min(prices) > 0.01 + 1e-9:
        return ResearchQuotes(note="最近收盘报价来源价格冲突，未用于研究。")
    chosen = max(candidates, key=lambda item: item[1].fetched_at or now)[1]
    sources = sorted({source for source, _ in candidates})
    count_note = "单源，未交叉验证" if len(sources) == 1 else f"{len(sources)} 源价格一致"
    assert chosen.fetched_at is not None
    return ResearchQuotes(
        quotes=[chosen],
        note=(f"休市研究：使用官方交易日历核验的最近交易日收盘报价，"
              f"数据时间 {chosen.fetched_at.astimezone(SHANGHAI).isoformat()}；"
              f"来源 {', '.join(sources)}（{count_note}），不是实时行情；不进入交易决策。"),
    )


class ResearchNews(BaseModel):
    items: list[NewsItem] = Field(default_factory=list)
    note: str = ""


def partial_research_news(envelope: EvidenceEnvelope) -> ResearchNews:
    """Carry only bounded, associated cached news while preserving incomplete status."""
    items: list[NewsItem] = []
    notes: list[str] = []
    request = envelope.request
    if request.start_at is None or request.end_at is None:
        return ResearchNews()
    for result in envelope.source_results:
        if result.error_code != "rolling_window_not_fully_covered":
            continue
        start, end = result.coverage_start_at, result.coverage_end_at
        if start is None or end is None:
            continue
        start, end = max(start, request.start_at), min(end, request.end_at)
        if start > end:
            continue
        selected = []
        for raw in result.items:
            item = NewsItem.model_validate(raw)
            if (item.code == request.stock_code and item.published_at is not None
                and start <= item.published_at <= end):
                selected.append(item)
        items.extend(selected)
        notes.append(
            f"{result.upstream_id} 新闻缓存实际覆盖 "
            f"{start.astimezone(SHANGHAI).isoformat()} 至 {end.astimezone(SHANGHAI).isoformat()}，"
            f"匹配 {len(selected)} 条；未覆盖完整近 3 天，不能据此认定该时段无新闻。"
        )
    return ResearchNews(items=items, note=" ".join(notes))

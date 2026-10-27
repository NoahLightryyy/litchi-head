"""Single-stock display quotes, independent of bulk market and trading evidence gates."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from threading import Lock
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import StockQuote
from src.data.providers.quotes import SHANGHAI, EastmoneyQuoteSource, SinaQuoteSource
from src.data.providers.tencent_display_quote import TencentDisplayQuoteSource

logger = logging.getLogger(__name__)


class DisplayQuote(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    change: float
    change_pct: float
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    prev_close: float = Field(ge=0)
    volume: int = Field(ge=0)
    amount: float = Field(ge=0)
    fetched_at: datetime
    open_: float = Field(default=0.0, serialization_alias="open")
    # Direct adapters do not provide these optional enrichment fields.
    market_cap: float | None = None
    turnover_rate: float | None = None
    fund_flow: float | None = None
    source: Literal["eastmoney", "sina", "tencent"]
    verification_status: Literal["single_source"] = "single_source"


class _QuoteSource(Protocol):
    descriptor: SourceDescriptor

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]: ...


# Bound both the response latency and actual outstanding work, across all callers.
# A timeout does not kill a thread; identical pending requests are reused, not respawned.
MAX_PENDING_QUOTES = 6
DISPLAY_QUOTE_BUDGET_SECONDS = 9.0
_pool = ThreadPoolExecutor(max_workers=MAX_PENDING_QUOTES, thread_name_prefix="display-quote")
_pending_lock = Lock()
_pending: dict[tuple[str, str], Future[DisplayQuote | None]] = {}


def _fetch_display_quote(source: _QuoteSource, request: EvidenceRequest) -> DisplayQuote | None:
    code = request.stock_code
    try:
        result = source.fetch(request)
        if result.status != SourceStatus.SUCCESS_DATA or len(result.items) != 1:
            logger.warning(
                "Display quote unavailable: code=%s source=%s status=%s error=%s",
                code,
                result.upstream_id,
                result.status,
                result.error_code,
            )
            return None
        quote = result.items[0]
        now = datetime.now(SHANGHAI)
        if (
            quote.code != code
            or not quote.name.strip()
            or quote.price <= 0
            or quote.fetched_at is None
            or quote.fetched_at.tzinfo is None
            or quote.fetched_at > now + timedelta(seconds=3)
        ):
            logger.warning(
                "Display quote identity/time invalid: code=%s source=%s", code, result.upstream_id
            )
            return None
        # Old quotes remain visibly dated; this response cannot authorize a debate.
        return DisplayQuote.model_validate(
            {
                **quote.model_dump(),
                "source": result.upstream_id,
                "market_cap": None,
            }
        )
    except Exception:
        logger.exception(
            "Display quote adapter failed: code=%s source=%s", code, source.descriptor.upstream_id
        )
        return None


def get_display_quote(code: str) -> DisplayQuote | None:
    request = EvidenceRequest(stock_code=code, capability=EvidenceCapability.REALTIME_QUOTE)
    sources: tuple[_QuoteSource, ...] = (
        EastmoneyQuoteSource(),
        SinaQuoteSource(),
        TencentDisplayQuoteSource(),
    )
    with _pending_lock:
        for key in list(_pending):
            if _pending[key].done():
                del _pending[key]
        futures: list[Future[DisplayQuote | None]] = []
        for source in sources:
            key = (code, source.descriptor.source_id)
            future = _pending.get(key)
            if future is None:
                if len(_pending) >= MAX_PENDING_QUOTES:
                    logger.warning(
                        "Display quote capacity busy: code=%s source=%s",
                        code,
                        source.descriptor.upstream_id,
                    )
                    continue
                future = _pool.submit(_fetch_display_quote, source, request)
                _pending[key] = future
            futures.append(future)
    try:
        for future in as_completed(futures, timeout=DISPLAY_QUOTE_BUDGET_SECONDS):
            quote = future.result()
            if quote is not None:
                return quote
    except TimeoutError:
        logger.warning("Display quote response budget exhausted: code=%s", code)
    return None

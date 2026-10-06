"""Single-stock display quotes, independent of bulk market and trading evidence gates."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.quotes import SHANGHAI, EastmoneyQuoteSource, SinaQuoteSource

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
    source: Literal["eastmoney", "sina"]
    verification_status: Literal["single_source"] = "single_source"


def get_display_quote(code: str) -> DisplayQuote | None:
    request = EvidenceRequest(stock_code=code, capability=EvidenceCapability.REALTIME_QUOTE)
    for source in (EastmoneyQuoteSource(), SinaQuoteSource()):
        result = source.fetch(request)
        if result.status != SourceStatus.SUCCESS_DATA or len(result.items) != 1:
            logger.warning("Display quote unavailable: code=%s source=%s status=%s error=%s",
                           code, result.upstream_id, result.status, result.error_code)
            continue
        quote = result.items[0]
        now = datetime.now(SHANGHAI)
        if (quote.code != code or not quote.name.strip() or quote.price <= 0
                or quote.fetched_at is None or quote.fetched_at.tzinfo is None
                or quote.fetched_at > now + timedelta(seconds=3)):
            logger.warning("Display quote identity/time invalid: code=%s source=%s",
                           code, result.upstream_id)
            continue
        # Old quotes remain visibly dated; this display response cannot authorize a debate.
        try:
            return DisplayQuote.model_validate({
                **quote.model_dump(), "source": result.upstream_id, "market_cap": None,
            })
        except ValueError:
            logger.exception("Display quote fields invalid: code=%s source=%s",
                             code, result.upstream_id)
    return None

"""Display-only A-share snapshots from the existing Tencent RAW daily service.

Only qt is quote evidence: daily bars and HTTP receipt time never stand in for it.
Research reuses this adapter with identity/time validation; execution registration is unchanged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import StockQuote
from src.data.providers.kline import (
    TencentDailyFetcher,
    _default_tencent_fetcher,
    _tencent_response,
)
from src.data.providers.quotes import SHANGHAI, _failed_result, _market_prefix
from src.data.providers.tencent_index_quotes import parse_tencent_snapshot

logger = logging.getLogger(__name__)


class TencentDisplayQuoteSource:
    descriptor = SourceDescriptor(
        source_id="direct-tencent-display-quote",
        upstream_id="tencent",
        display_name="腾讯个股展示报价",
        capabilities={EvidenceCapability.REALTIME_QUOTE},
    )

    def __init__(self, *, fetcher: TencentDailyFetcher | None = None) -> None:
        self._fetcher = fetcher or _default_tencent_fetcher

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]:
        code = request.stock_code
        try:
            if (
                request.capability != EvidenceCapability.REALTIME_QUOTE
                or not re.fullmatch(r"[0-9]{6}", code)
                or _market_prefix(code) not in {"sh", "sz"}
            ):
                raise ValueError("Tencent display snapshot supports SH/SZ stock quotes only")
        except ValueError as exc:
            return _failed_result(
                self.descriptor,
                capability=request.capability,
                error_code="invalid_request",
                exc=exc,
            )
        try:
            today = datetime.now(SHANGHAI).date()
            # Same endpoint/parameter semantics as existing RAW K-line; no new vendor or key.
            raw = self._fetcher(code, today - timedelta(days=7), today)
        except Exception as exc:
            logger.warning("Tencent display quote request failed: code=%s error=%s", code, exc)
            return _failed_result(
                self.descriptor,
                capability=request.capability,
                error_code="upstream_request_failed",
                exc=exc,
            )
        try:
            payload, _ = _tencent_response(raw)
            if not isinstance(payload, Mapping):
                raise ValueError("Tencent response must be a mapping")
            quote = parse_tencent_snapshot(
                payload, symbol=f"{_market_prefix(code)}{code}", code=code, instrument_type="GP-A"
            )
        except Exception as exc:
            logger.warning("Tencent display quote invalid: code=%s error=%s", code, exc)
            return _failed_result(
                self.descriptor,
                capability=request.capability,
                error_code="invalid_upstream_payload",
                exc=exc,
            )
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[quote],
        )

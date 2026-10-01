"""Bounded single-stock name lookup; never download the whole market for a name.

Only the name is reused. A successful lookup does not validate market prices or
relax the separate evidence gates used by the debate engine.
"""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from threading import BoundedSemaphore, Lock

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.quotes import EastmoneyQuoteSource, SinaQuoteSource

logger = logging.getLogger(__name__)
_slots = BoundedSemaphore(4)
_cache_lock = Lock()
_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
_CACHE_SECONDS = 300.0
_CACHE_SIZE = 256


def resolve_stock_name(stock_code: str) -> str:
    """Resolve identity through existing single-symbol adapters, without guessing."""
    if not re.fullmatch(r"[0-9]{6}", stock_code):
        return ""
    with _cache_lock:
        cached = _cache.get(stock_code)
        if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
            _cache.move_to_end(stock_code)
            return cached[1]
    # Timed-out threads cannot be killed. Contain residual upstream requests.
    if not _slots.acquire(blocking=False):
        logger.warning("Stock identity capacity exhausted: symbol=%s", stock_code)
        return ""
    try:
        request = EvidenceRequest(
            capability=EvidenceCapability.REALTIME_QUOTE, stock_code=stock_code,
        )
        for source in (SinaQuoteSource(), EastmoneyQuoteSource()):
            result = source.fetch(request)
            if result.status is not SourceStatus.SUCCESS_DATA or len(result.items) != 1:
                logger.warning(
                    "Stock identity unavailable: symbol=%s source=%s status=%s",
                    stock_code, result.source_id, result.status.value,
                )
                continue
            quote = result.items[0]
            name = quote.name.strip()
            if quote.code != stock_code or not name or name.lower() in {"nan", "none", "null"}:
                continue
            if name == stock_code or any(ord(char) < 32 for char in name):
                continue
            with _cache_lock:
                _cache[stock_code] = (time.monotonic(), name)
                _cache.move_to_end(stock_code)
                while len(_cache) > _CACHE_SIZE:
                    _cache.popitem(last=False)
            logger.info(
                "Stock identity resolved: symbol=%s source=%s", stock_code, result.source_id,
            )
            return name
        return ""
    finally:
        _slots.release()

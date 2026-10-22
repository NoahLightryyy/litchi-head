"""Tencent homepage index snapshots; minute endpoint's qt is the quote evidence.

The minute-series date and HTTP receipt time never replace qt[30]. This source
is restricted to the three indices and is not added to the trading quote gate.
"""
from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import StockQuote
from src.data.providers.intraday import TENCENT_INTRADAY_URL
from src.data.providers.quotes import (
    QUOTE_TIMEOUT_SECONDS,
    SHANGHAI,
    USER_AGENT,
    _failed_result,
    _integer,
    _number,
    _sina_index_symbol,
)

logger = logging.getLogger(__name__)


class TencentIndexFetcher(Protocol):
    def __call__(self, code: str) -> Mapping[str, Any]: ...


def _fetch_tencent_index(code: str) -> Mapping[str, Any]:
    import httpx

    response = httpx.get(
        TENCENT_INTRADAY_URL,
        params={"code": _sina_index_symbol(code)},
        headers={"User-Agent": USER_AGENT, "Referer": "https://gu.qq.com/"},
        timeout=QUOTE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def _finite(value: object, field: str) -> float:
    number = _number(value, field)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


class TencentIndexQuoteSource:
    descriptor = SourceDescriptor(
        source_id="direct-tencent-index",
        upstream_id="tencent",
        display_name="腾讯指数行情直连",
        capabilities={EvidenceCapability.MARKET_INDEX},
    )

    def __init__(self, *, fetcher: TencentIndexFetcher = _fetch_tencent_index) -> None:
        self._fetcher = fetcher

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]:
        try:
            if request.capability is not EvidenceCapability.MARKET_INDEX:
                raise ValueError("Tencent index source requires MARKET_INDEX")
            symbol = _sina_index_symbol(request.stock_code)
        except ValueError as exc:
            return _failed_result(self.descriptor, capability=request.capability,
                                  error_code="invalid_request", exc=exc)
        try:
            payload = self._fetcher(request.stock_code)
        except Exception as exc:
            logger.warning(
                "Tencent index request failed: code=%s error=%s", request.stock_code, exc,
            )
            return _failed_result(self.descriptor, capability=request.capability,
                                  error_code="upstream_request_failed", exc=exc)
        try:
            if not isinstance(payload, Mapping) or payload.get("code") != 0:
                raise ValueError("Tencent index response is not successful")
            data = payload.get("data")
            node = data.get(symbol) if isinstance(data, Mapping) else None
            qt = node.get("qt") if isinstance(node, Mapping) else None
            fields = qt.get(symbol) if isinstance(qt, Mapping) else None
            if not isinstance(fields, list) or len(fields) < 62:
                raise ValueError("Tencent index snapshot is missing or truncated")
            if (fields[2] != request.stock_code or fields[61] != "ZS"
                    or fields[0] != ("1" if symbol.startswith("sh") else "51")
                    or not isinstance(fields[1], str) or not fields[1].strip()):
                raise ValueError("Tencent index identity does not match request")
            stamp = fields[30]
            if not isinstance(stamp, str) or not re.fullmatch(r"[0-9]{14}", stamp):
                raise ValueError("Tencent index quote timestamp is invalid")
            quoted_at = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=SHANGHAI)
            price = _finite(fields[3], "price")
            prev_close = _finite(fields[4], "prev_close")
            opening = _finite(fields[5], "open")
            high = _finite(fields[33], "high")
            low = _finite(fields[34], "low")
            change = _finite(fields[31], "change")
            change_pct = _finite(fields[32], "change_pct")
            if min(price, prev_close, opening, high, low) <= 0 or not (
                low <= min(price, opening) <= max(price, opening) <= high
            ):
                raise ValueError("Tencent index OHLC values are invalid")
            if (abs(change - (price - prev_close)) > 0.02
                    or abs(change_pct - (price / prev_close - 1) * 100) > 0.02):
                raise ValueError("Tencent index change fields disagree with prices")
            # qt[35] is price / volume (hands) / amount (CNY), without qt[37]'s rounding.
            totals = str(fields[35]).split("/")
            if len(totals) != 3:
                raise ValueError("Tencent index turnover tuple is invalid")
            hands = _integer(fields[6], "volume")
            if (_finite(totals[0], "turnover_price") != price
                    or _integer(totals[1], "turnover_volume") != hands):
                raise ValueError("Tencent index turnover identity mismatch")
            quote = StockQuote(
                code=request.stock_code, name=fields[1].strip(), price=price,
                prev_close=prev_close, open_=opening, high=high, low=low,
                change=change, change_pct=change_pct, volume=hands * 100,
                amount=_finite(totals[2], "amount"), fetched_at=quoted_at,
            )
        except Exception as exc:
            logger.warning(
                "Tencent index payload invalid: code=%s error=%s", request.stock_code, exc,
            )
            return _failed_result(self.descriptor, capability=request.capability,
                                  error_code="invalid_upstream_payload", exc=exc)
        return SourceResult(
            source_id=self.descriptor.source_id, upstream_id=self.descriptor.upstream_id,
            capability=request.capability, status=SourceStatus.SUCCESS_DATA, items=[quote],
        )

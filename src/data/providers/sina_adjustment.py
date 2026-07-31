"""Direct Sina cumulative QFQ-divisor evidence adapter."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.kline import MarketCode, market_code_for
from src.data.kline_adjustment import (
    CumulativeQfqFactorPoint,
    QfqFactorSnapshot,
    is_supported_a_share_code,
)
from src.data.providers.quotes import USER_AGENT, _market_prefix

SINA_QFQ_FACTOR_URL = "https://finance.sina.com.cn/realstock/company/{symbol}/qfq.js"
SINA_QFQ_FACTOR_ADAPTER_VERSION = "sina-qfq-factor-v1"
SINA_QFQ_FACTOR_TIMEOUT_SECONDS = 8.0
SINA_QFQ_FACTOR_SENTINEL_DATE = date(1900, 1, 1)


class SinaQfqFactorFetcher(Protocol):
    def __call__(self, code: str) -> bytes:
        """Return the direct Sina qfq.js response."""
        ...


def _default_fetcher(code: str) -> bytes:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    response = httpx.get(
        SINA_QFQ_FACTOR_URL.format(symbol=symbol),
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://finance.sina.com.cn/",
        },
        timeout=SINA_QFQ_FACTOR_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _aware_utc(now_provider: Callable[[], datetime]) -> datetime:
    value = now_provider()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now_provider must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _response_bytes(response: bytes) -> bytes:
    if not isinstance(response, bytes):
        raise TypeError("Sina QFQ-factor evidence fetcher must return raw bytes")
    return response


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Sina QFQ-factor payload repeats key {key!r}")
        result[key] = value
    return result


def _payload(raw: bytes, *, expected_symbol: str) -> Mapping[str, Any]:
    text = raw.decode("utf-8")
    match = re.fullmatch(
        (
            rf"\s*var\s+{re.escape(expected_symbol)}qfq\s*=\s*"
            r"(\{.*\})\s*;?\s*(?:/\*.*\*/\s*)?"
        ),
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Sina QFQ-factor response wrapper is invalid")
    payload = json.loads(
        match.group(1),
        object_pairs_hook=_unique_json_object,
    )
    if not isinstance(payload, Mapping):
        raise ValueError("Sina QFQ-factor payload must be an object")
    return payload


def _point(row: object) -> CumulativeQfqFactorPoint:
    if not isinstance(row, Mapping):
        raise ValueError("Sina QFQ-factor row must be an object")
    raw_date = row.get("d")
    raw_factor = row.get("f")
    if not isinstance(raw_date, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        raw_date,
    ) is None:
        raise ValueError("Sina QFQ-factor date must be a YYYY-MM-DD string")
    if not isinstance(raw_factor, str) or re.fullmatch(
        r"\d+(?:\.\d+)?",
        raw_factor,
    ) is None:
        raise ValueError("Sina QFQ factor must be a decimal string")
    factor = Decimal(raw_factor)
    if not factor.is_finite():
        raise ValueError("Sina QFQ factor must be finite")
    exponent = factor.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("Sina QFQ factor precision is invalid")
    return CumulativeQfqFactorPoint(
        effective_date=datetime.strptime(
            raw_date,
            "%Y-%m-%d",
        ).date(),
        cumulative_divisor=factor,
        precision=Decimal(1).scaleb(exponent),
    )


class SinaQfqFactorSource:
    """Fetch a content-addressed cumulative QFQ-factor snapshot from Sina."""

    descriptor = SourceDescriptor(
        source_id="direct-sina-qfq-factor",
        upstream_id="sina",
        display_name="新浪累计 QFQ 除数直连",
        capabilities={EvidenceCapability.CUMULATIVE_QFQ_FACTOR},
    )

    def __init__(
        self,
        *,
        fetcher: SinaQfqFactorFetcher = _default_fetcher,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider

    def fetch(
        self,
        request: EvidenceRequest,
    ) -> SourceResult[QfqFactorSnapshot]:
        if request.capability is not EvidenceCapability.CUMULATIVE_QFQ_FACTOR:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
            )
        if not is_supported_a_share_code(request.stock_code):
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                fetched_at=_aware_utc(self._now_provider),
                error_code="invalid_request",
                error_message="stock_code must be an explicitly supported A-share code",
            )
        if market_code_for(request.stock_code) is MarketCode.BSE:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.UNSUPPORTED,
                error_code="official_verification_unavailable",
                error_message=(
                    "BSE cumulative QFQ factors remain disabled until an "
                    "independent official corporate-action source is verified"
                ),
            )
        try:
            fetched_response = self._fetcher(request.stock_code)
        except Exception as exc:
            fetched_at = _aware_utc(self._now_provider)
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                error_code="upstream_request_failed",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        fetched_at = _aware_utc(self._now_provider)
        try:
            raw = _response_bytes(fetched_response)
            symbol = f"{_market_prefix(request.stock_code)}{request.stock_code}"
            payload = _payload(raw, expected_symbol=symbol)
            rows = payload.get("data")
            if not isinstance(rows, list):
                raise ValueError("Sina QFQ-factor payload is missing data")
            raw_total = payload.get("total")
            if isinstance(raw_total, bool):
                raise ValueError("Sina QFQ-factor total must be a nonnegative integer")
            try:
                total = int(str(raw_total))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Sina QFQ-factor total must be a nonnegative integer"
                ) from exc
            if total < 0 or total != len(rows):
                raise ValueError("Sina QFQ-factor total does not match data rows")
            raw_points = tuple(_point(row) for row in rows)
            if (
                not raw_points
                or raw_points[-1].effective_date != SINA_QFQ_FACTOR_SENTINEL_DATE
                or any(
                    point.effective_date == SINA_QFQ_FACTOR_SENTINEL_DATE
                    for point in raw_points[:-1]
                )
            ):
                raise ValueError(
                    "Sina QFQ-factor requires one trailing 1900-01-01 sentinel"
                )
            base = raw_points[-1]
            event_points = raw_points[:-1]
            if any(
                point.effective_date <= SINA_QFQ_FACTOR_SENTINEL_DATE
                for point in event_points
            ):
                raise ValueError(
                    "Sina QFQ-factor event dates must be after the base sentinel"
                )
            if any(
                newer.effective_date <= older.effective_date
                for newer, older in zip(
                    event_points,
                    event_points[1:],
                    strict=False,
                )
            ):
                raise ValueError(
                    "Sina QFQ-factor dates must be unique and strictly descending"
                )
            if event_points:
                if event_points[0].cumulative_divisor != Decimal("1"):
                    raise ValueError("Sina QFQ-factor latest anchor must equal one")
                if (
                    base.cumulative_divisor
                    != event_points[-1].cumulative_divisor
                ):
                    raise ValueError(
                        "Sina QFQ-factor base anchor must equal the oldest divisor"
                    )
            elif base.cumulative_divisor != Decimal("1"):
                raise ValueError("Sina QFQ-factor empty-history anchor must equal one")
            points = tuple(reversed(event_points))
            digest = hashlib.sha256(raw).hexdigest()
            snapshot = QfqFactorSnapshot(
                code=request.stock_code,
                market=market_code_for(request.stock_code),
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                adapter_version=SINA_QFQ_FACTOR_ADAPTER_VERSION,
                collected_at=fetched_at,
                response_hash=digest,
                response_bytes=len(raw),
                factor_version=f"sha256:{digest}",
                base_divisor=base.cumulative_divisor,
                base_precision=base.precision,
                points=points,
            )
        except (UnicodeError, ValueError, TypeError, InvalidOperation) as exc:
            return SourceResult(
                source_id=self.descriptor.source_id,
                upstream_id=self.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                fetched_at=fetched_at,
                error_code="invalid_upstream_payload",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_DATA,
            items=[snapshot],
            fetched_at=fetched_at,
        )


__all__ = ["SinaQfqFactorSource"]

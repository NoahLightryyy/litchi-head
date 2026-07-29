"""Realtime quote evidence runtime and fail-closed reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceResult,
    SourceStatus,
)
from src.data.evidence_service import DataEvidenceService
from src.data.models import StockQuote
from src.data.providers.quotes import EastmoneyQuoteSource, SinaQuoteSource

SHANGHAI = ZoneInfo("Asia/Shanghai")
QUOTE_WARNING_SECONDS = 10.0
QUOTE_HARD_FAILURE_SECONDS = 30.0
QUOTE_PAIRING_SECONDS = 3.0
QUOTE_PRICE_TICK = 0.01

REALTIME_QUOTE_EVIDENCE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.REALTIME_QUOTE,
    min_independent_upstreams=2,
    required_upstream_ids={"eastmoney", "sina"},
)


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def _is_continuous_auction(now: datetime) -> bool:
    local = now.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return False
    clock = local.time().replace(tzinfo=None)
    return (
        time(9, 30) <= clock < time(11, 30)
        or time(13, 0) <= clock < time(14, 57)
    )


def _unusable(
    result: SourceResult[StockQuote],
    *,
    status: SourceStatus,
    error_code: str,
    error_message: str,
) -> SourceResult[StockQuote]:
    return result.model_copy(
        update={
            "status": status,
            "error_code": error_code,
            "error_message": error_message,
        }
    )


class RealtimeQuoteEvidenceService:
    """Collect two direct quote sources and validate their live agreement."""

    def __init__(
        self,
        registry: EvidenceSourceRegistry,
        *,
        now_provider: Callable[[], datetime] = _now_shanghai,
        max_workers: int = 2,
    ) -> None:
        self._registry = registry
        self._collector = DataEvidenceService(registry, max_workers=max_workers)
        self._now_provider = now_provider

    def collect(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
    ) -> EvidenceEnvelope:
        if request.capability is not EvidenceCapability.REALTIME_QUOTE:
            raise ValueError("RealtimeQuoteEvidenceService only supports realtime quotes")

        raw = self._collector.collect(request, policy)
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")

        results = [
            self._validate_source_result(result, request=request, now=now)
            for result in raw.source_results
        ]
        results = self._validate_pair(results)
        assessment = self._registry.assess(policy, results)
        successful_quotes = [
            result.items[0]
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        canonical = (
            [max(successful_quotes, key=lambda quote: quote.fetched_at or now)]
            if assessment.complete and successful_quotes
            else []
        )
        return EvidenceEnvelope(
            request=request,
            policy=policy,
            source_results=results,
            items=canonical,
            assessment=assessment,
            complete=assessment.complete,
        )

    @staticmethod
    def _validate_source_result(
        result: SourceResult[StockQuote],
        *,
        request: EvidenceRequest,
        now: datetime,
    ) -> SourceResult[StockQuote]:
        if result.status is not SourceStatus.SUCCESS_DATA:
            return result
        if len(result.items) != 1:
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="quote_cardinality_invalid",
                error_message="Realtime quote source must return exactly one item",
            )

        quote = result.items[0]
        if quote.code != request.stock_code:
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="quote_identity_conflict",
                error_message="Realtime quote code does not match the request",
            )
        if quote.fetched_at is None or quote.fetched_at.tzinfo is None:
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="quote_timestamp_missing",
                error_message="Realtime quote is missing an exchange timestamp",
            )
        if not _is_continuous_auction(now):
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="market_not_in_continuous_auction",
                error_message="New AI debate is disabled outside continuous auction",
            )

        age_seconds = (now - quote.fetched_at.astimezone(now.tzinfo)).total_seconds()
        if age_seconds < -QUOTE_PAIRING_SECONDS:
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="quote_timestamp_in_future",
                error_message="Realtime quote timestamp is unexpectedly in the future",
            )
        if age_seconds > QUOTE_HARD_FAILURE_SECONDS:
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="quote_stale",
                error_message="Realtime quote is older than 30 seconds",
            )
        if age_seconds > QUOTE_WARNING_SECONDS:
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="quote_suspect",
                error_message="Realtime quote is older than 10 seconds",
            )
        return result

    @staticmethod
    def _validate_pair(
        results: list[SourceResult[StockQuote]],
    ) -> list[SourceResult[StockQuote]]:
        successful = [
            result
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        if len(successful) != 2:
            return results

        first_quote = successful[0].items[0]
        second_quote = successful[1].items[0]
        assert first_quote.fetched_at is not None
        assert second_quote.fetched_at is not None
        skew = abs(
            (first_quote.fetched_at - second_quote.fetched_at).total_seconds()
        )
        if skew > QUOTE_PAIRING_SECONDS:
            return [
                _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="quote_timestamp_conflict",
                    error_message="Quote source timestamps differ by more than 3 seconds",
                )
                if result in successful
                else result
                for result in results
            ]

        price_delta = abs(first_quote.price - second_quote.price)
        if price_delta > QUOTE_PRICE_TICK + 1e-9:
            return [
                _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="quote_price_conflict",
                    error_message="Quote source prices differ by more than one tick",
                )
                if result in successful
                else result
                for result in results
            ]
        return results


class RealtimeQuoteEvidenceRuntime:
    """Own the process-wide direct quote sources and reconciliation service."""

    def __init__(self) -> None:
        registry = EvidenceSourceRegistry()
        registry.register(EastmoneyQuoteSource())
        registry.register(SinaQuoteSource())
        self.service = RealtimeQuoteEvidenceService(registry)


_runtime: RealtimeQuoteEvidenceRuntime | None = None


def get_realtime_quote_evidence_runtime() -> RealtimeQuoteEvidenceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RealtimeQuoteEvidenceRuntime()
    return _runtime


__all__ = [
    "QUOTE_HARD_FAILURE_SECONDS",
    "QUOTE_PAIRING_SECONDS",
    "QUOTE_PRICE_TICK",
    "QUOTE_WARNING_SECONDS",
    "REALTIME_QUOTE_EVIDENCE_POLICY",
    "RealtimeQuoteEvidenceRuntime",
    "RealtimeQuoteEvidenceService",
    "get_realtime_quote_evidence_runtime",
]

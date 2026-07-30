"""Completed RAW daily K-line dual-source reconciliation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

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
from src.data.kline import RawDailyBar, market_code_for
from src.data.providers.kline import (
    SinaRawDailyKlineSource,
    TencentRawDailyKlineSource,
)

KLINE_RAW_EVIDENCE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.KLINE,
    min_independent_upstreams=2,
    required_upstream_ids={"sina", "tencent"},
)


def _unusable(
    result: SourceResult[RawDailyBar],
    *,
    status: SourceStatus,
    error_code: str,
    error_message: str,
) -> SourceResult[RawDailyBar]:
    return result.model_copy(
        update={
            "status": status,
            "error_code": error_code,
            "error_message": error_message,
        }
    )


class RawDailyKlineEvidenceService:
    """Reconcile completed RAW daily facts before downstream consumption."""

    def __init__(
        self,
        registry: EvidenceSourceRegistry,
        *,
        max_workers: int = 2,
    ) -> None:
        self._registry = registry
        self._collector = DataEvidenceService(registry, max_workers=max_workers)

    def collect(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
    ) -> EvidenceEnvelope:
        self._validate_request(request)
        if policy.capability is not EvidenceCapability.KLINE:
            raise ValueError("RAW daily K-line policy must use KLINE capability")

        raw = self._collector.collect(request, policy)
        results = [
            self._validate_source(result, request=request)
            for result in raw.source_results
        ]
        results = self._validate_pair(results)
        assessment = self._registry.assess(policy, results)
        canonical: list[RawDailyBar] = []
        if assessment.complete:
            canonical = self._canonical_bars(results)
        return EvidenceEnvelope(
            request=request,
            policy=policy,
            source_results=results,
            items=canonical,
            assessment=assessment,
            complete=assessment.complete,
        )

    @staticmethod
    def _validate_request(request: EvidenceRequest) -> None:
        if request.capability is not EvidenceCapability.KLINE:
            raise ValueError(
                "RawDailyKlineEvidenceService only supports KLINE evidence"
            )
        if request.start_at is None or request.end_at is None:
            raise ValueError("RAW daily K-line request requires start_at and end_at")
        if (
            request.start_at.utcoffset() is None
            or request.end_at.utcoffset() is None
        ):
            raise ValueError(
                "RAW daily K-line request bounds must be timezone-aware"
            )

    @staticmethod
    def _validate_source(
        result: SourceResult[RawDailyBar],
        *,
        request: EvidenceRequest,
    ) -> SourceResult[RawDailyBar]:
        if result.status is SourceStatus.SUCCESS_EMPTY:
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="kline_window_empty",
                error_message="RAW daily K-line source returned no completed bars",
            )
        if result.status is not SourceStatus.SUCCESS_DATA:
            return result

        expected_market = market_code_for(request.stock_code)
        start = request.start_at.date() if request.start_at else date.min
        end = request.end_at.date() if request.end_at else date.max
        seen_dates: set[date] = set()
        for bar in result.items:
            if bar.trade_date in seen_dates:
                return _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="duplicate_trading_date",
                    error_message="RAW daily source returned duplicate trade dates",
                )
            seen_dates.add(bar.trade_date)
            if (
                bar.code != request.stock_code
                or bar.market is not expected_market
                or bar.period != "1d"
                or bar.currency != "CNY"
                or bar.price_basis != "raw"
            ):
                return _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="instrument_identity_conflict",
                    error_message="RAW daily identity does not match the request",
                )
            if not start <= bar.trade_date <= end:
                return _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="trading_date_out_of_range",
                    error_message="RAW daily source returned a date outside the request",
                )
        return result

    @staticmethod
    def _validate_pair(
        results: list[SourceResult[RawDailyBar]],
    ) -> list[SourceResult[RawDailyBar]]:
        successful = [
            result
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        if len(successful) < 2:
            return results

        by_source = [
            {bar.trade_date: bar for bar in result.items}
            for result in successful
        ]
        reference_dates = set(by_source[0])
        if any(set(series) != reference_dates for series in by_source[1:]):
            return RawDailyKlineEvidenceService._conflict(
                results,
                successful,
                error_code="trading_date_conflict",
                error_message="Completed RAW daily trade-date sets do not match",
            )

        for trade_date in sorted(reference_dates):
            bars = [series[trade_date] for series in by_source]
            reference = bars[0]
            for candidate in bars[1:]:
                if candidate.price_tick != reference.price_tick:
                    return RawDailyKlineEvidenceService._conflict(
                        results,
                        successful,
                        error_code="price_tick_conflict",
                        error_message="RAW daily price ticks do not match",
                    )
                if any(
                    getattr(candidate, field_name)
                    != getattr(reference, field_name)
                    for field_name in ("open", "high", "low", "close")
                ):
                    return RawDailyKlineEvidenceService._conflict(
                        results,
                        successful,
                        error_code="raw_ohlc_conflict",
                        error_message=(
                            "Completed RAW daily OHLC differs by at least one tick"
                        ),
                    )
                volume_precision = max(
                    reference.volume_precision,
                    candidate.volume_precision,
                )
                if abs(reference.volume - candidate.volume) >= volume_precision:
                    return RawDailyKlineEvidenceService._conflict(
                        results,
                        successful,
                        error_code="raw_volume_conflict",
                        error_message=(
                            "RAW daily volumes differ beyond declared source precision"
                        ),
                    )
                amount_error = RawDailyKlineEvidenceService._amount_error(
                    reference,
                    candidate,
                )
                if amount_error is not None:
                    return RawDailyKlineEvidenceService._conflict(
                        results,
                        successful,
                        error_code="raw_amount_conflict",
                        error_message=amount_error,
                    )
        return results

    @staticmethod
    def _amount_error(
        first: RawDailyBar,
        second: RawDailyBar,
    ) -> str | None:
        if first.amount is None or second.amount is None:
            return None
        first_precision = first.amount_precision or Decimal("0")
        second_precision = second.amount_precision or Decimal("0")
        precision = max(first_precision, second_precision)
        if abs(first.amount - second.amount) >= precision:
            return "RAW daily amounts differ beyond declared source precision"
        return None

    @staticmethod
    def _conflict(
        results: list[SourceResult[RawDailyBar]],
        successful: list[SourceResult[RawDailyBar]],
        *,
        error_code: str,
        error_message: str,
    ) -> list[SourceResult[RawDailyBar]]:
        return [
            _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code=error_code,
                error_message=error_message,
            )
            if result in successful
            else result
            for result in results
        ]

    @staticmethod
    def _canonical_bars(
        results: list[SourceResult[RawDailyBar]],
    ) -> list[RawDailyBar]:
        successful = [
            result
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        trade_dates = sorted(
            {bar.trade_date for result in successful for bar in result.items}
        )
        canonical: list[RawDailyBar] = []
        for trade_date in trade_dates:
            candidates = [
                bar
                for result in successful
                for bar in result.items
                if bar.trade_date == trade_date
            ]
            canonical.append(
                min(
                    candidates,
                    key=lambda bar: (
                        bar.volume_precision,
                        bar.amount_precision is None,
                    ),
                )
            )
        return canonical


class RawDailyKlineEvidenceRuntime:
    """Process-level RAW daily evidence sources."""

    def __init__(self) -> None:
        registry = EvidenceSourceRegistry()
        registry.register(SinaRawDailyKlineSource())
        registry.register(TencentRawDailyKlineSource())
        self.service = RawDailyKlineEvidenceService(registry)


_runtime: RawDailyKlineEvidenceRuntime | None = None


def get_raw_daily_kline_runtime() -> RawDailyKlineEvidenceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RawDailyKlineEvidenceRuntime()
    return _runtime


__all__ = [
    "KLINE_RAW_EVIDENCE_POLICY",
    "RawDailyKlineEvidenceRuntime",
    "RawDailyKlineEvidenceService",
    "get_raw_daily_kline_runtime",
]

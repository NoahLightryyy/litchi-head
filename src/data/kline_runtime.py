"""Completed RAW daily K-line dual-source reconciliation."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
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
from src.data.kline import RawDailyBar, market_code_for
from src.data.kline_calendar import (
    CalendarCoverageError,
    OfficialTradingCalendar,
    SecurityStatusCoverageError,
    StaticSecurityStatusCatalog,
    official_a_share_calendar_2026,
)
from src.data.kline_store import (
    KlineAuditStore,
    KlineEvidenceSnapshot,
    KlineSourceAudit,
)
from src.data.providers.kline import (
    SinaRawDailyKlineSource,
    TencentRawDailyKlineSource,
)
from src.utils.config import settings

KLINE_RAW_EVIDENCE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.KLINE,
    min_independent_upstreams=2,
    required_upstream_ids={"sina", "tencent"},
)
SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_KLINE_AUDIT_ROOT = Path(settings.data_dir).resolve() / "evidence" / "kline-audit"
DEFAULT_KLINE_CALENDAR = official_a_share_calendar_2026()
logger = logging.getLogger(__name__)


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def _kline_audit_root() -> Path:
    configured = os.getenv("LITCHI_KLINE_AUDIT_ROOT")
    if configured is None:
        return DEFAULT_KLINE_AUDIT_ROOT
    path = Path(configured).expanduser()
    if not path.is_absolute():
        raise ValueError("LITCHI_KLINE_AUDIT_ROOT must be an absolute path")
    return path.resolve()


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
        calendar: OfficialTradingCalendar | None = None,
        security_status_catalog: StaticSecurityStatusCatalog | None = None,
        now_provider: Callable[[], datetime] = _now_shanghai,
        audited_sources: tuple[
            SinaRawDailyKlineSource | TencentRawDailyKlineSource,
            ...,
        ] = (),
    ) -> None:
        self._registry = registry
        self._collector = DataEvidenceService(registry, max_workers=max_workers)
        self._max_workers = max_workers
        self._calendar = calendar
        self._security_status_catalog = security_status_catalog
        self._now_provider = now_provider
        self._audited_sources = audited_sources

    def collect(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
    ) -> EvidenceEnvelope:
        self._validate_request(request)
        if policy.capability is not EvidenceCapability.KLINE:
            raise ValueError("RAW daily K-line policy must use KLINE capability")

        raw = self._collector.collect(request, policy)
        return self._reconcile(
            request,
            policy,
            raw.source_results,
            collected_at=raw.collected_at,
        )

    def _reconcile(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
        source_results: list[SourceResult[RawDailyBar]],
        *,
        collected_at: datetime,
        require_authority: bool = False,
    ) -> EvidenceEnvelope:
        results = [self._validate_source(result, request=request) for result in source_results]
        results = self._validate_pair(results)
        results = self._validate_expected_dates(
            results,
            request=request,
            require_authority=require_authority,
        )
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
            collected_at=collected_at,
        )

    @staticmethod
    def _audit_result(
        audit: KlineSourceAudit,
    ) -> SourceResult[RawDailyBar]:
        return SourceResult(
            source_id=audit.source_id,
            upstream_id=audit.upstream_id,
            capability=EvidenceCapability.KLINE,
            status=audit.status,
            items=(list(audit.raw_bars) if audit.status is SourceStatus.SUCCESS_DATA else []),
            fetched_at=audit.fetched_at,
            error_code=audit.error_code,
            error_message=audit.error_message,
        )

    def _authority_hashes(
        self,
        request: EvidenceRequest,
    ) -> tuple[str, ...]:
        if request.start_at is None or request.end_at is None:
            return ()
        start = request.start_at.date()
        end = request.end_at.date()
        market = market_code_for(request.stock_code)
        hashes: list[str] = []
        if self._calendar is not None:
            hashes.extend(
                f"calendar:{version.content_hash}"
                for version in self._calendar.versions
                if version.market is market and start.year <= version.year <= end.year
            )
        if self._security_status_catalog is not None:
            try:
                window = self._security_status_catalog.resolve(
                    request.stock_code,
                    market,
                    start,
                    end,
                )
            except SecurityStatusCoverageError:
                pass
            else:
                hashes.append(f"status-window:{window.content_hash}")
        return tuple(sorted(set(hashes)))

    def _fetch_audit_safely(
        self,
        source: SinaRawDailyKlineSource | TencentRawDailyKlineSource,
        request: EvidenceRequest,
    ) -> KlineSourceAudit:
        try:
            return source.fetch_audited(request)
        except Exception as exc:
            logger.exception(
                "Unexpected audited K-line adapter failure: source=%s",
                source.descriptor.source_id,
            )
            failed_at = self._now_provider()
            if failed_at.tzinfo is None:
                failed_at = datetime.now(UTC)
            return KlineSourceAudit(
                source_id=source.descriptor.source_id,
                upstream_id=source.descriptor.upstream_id,
                adapter_version=source.adapter_version,
                status=SourceStatus.FAILED,
                fetched_at=failed_at.astimezone(UTC),
                error_code="unexpected_adapter_failure",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )

    def collect_and_persist(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
        store: KlineAuditStore,
    ) -> tuple[EvidenceEnvelope, str]:
        """Collect exact per-source proofs and persist one auditable outcome."""
        self._validate_request(request)
        if policy.capability is not EvidenceCapability.KLINE:
            raise ValueError("RAW daily K-line policy must use KLINE capability")
        if not self._audited_sources:
            raise ValueError("audited K-line sources are required for persistence")
        with ThreadPoolExecutor(
            max_workers=min(self._max_workers, len(self._audited_sources))
        ) as executor:
            audits = tuple(
                executor.map(
                    lambda source: self._fetch_audit_safely(
                        source,
                        request,
                    ),
                    self._audited_sources,
                )
            )
        collected_at = self._now_provider()
        if collected_at.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        collected_at = collected_at.astimezone(UTC)
        envelope = self._reconcile(
            request,
            policy,
            [self._audit_result(audit) for audit in audits],
            collected_at=collected_at,
            require_authority=True,
        )
        final_results = {result.source_id: result for result in envelope.source_results}
        final_audits = tuple(
            KlineSourceAudit.model_validate(
                {
                    **audit.model_dump(mode="python"),
                    "status": final_results[audit.source_id].status,
                    "error_code": final_results[audit.source_id].error_code,
                    "error_message": final_results[audit.source_id].error_message,
                }
            )
            for audit in audits
        )
        snapshot = KlineEvidenceSnapshot(
            schema_version=1,
            request=request,
            policy=policy,
            collected_at=collected_at,
            source_audits=final_audits,
            canonical_bars=(tuple(envelope.items) if envelope.complete else ()),
            assessment=envelope.assessment,
            authority_hashes=self._authority_hashes(request),
        )
        return envelope, store.persist(snapshot)

    @staticmethod
    def _validate_request(request: EvidenceRequest) -> None:
        if request.capability is not EvidenceCapability.KLINE:
            raise ValueError("RawDailyKlineEvidenceService only supports KLINE evidence")
        if request.start_at is None or request.end_at is None:
            raise ValueError("RAW daily K-line request requires start_at and end_at")
        if request.start_at.utcoffset() is None or request.end_at.utcoffset() is None:
            raise ValueError("RAW daily K-line request bounds must be timezone-aware")

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

        by_source = [{bar.trade_date: bar for bar in result.items} for result in successful]
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
                    getattr(candidate, field_name) != getattr(reference, field_name)
                    for field_name in ("open", "high", "low", "close")
                ):
                    return RawDailyKlineEvidenceService._conflict(
                        results,
                        successful,
                        error_code="raw_ohlc_conflict",
                        error_message=("Completed RAW daily OHLC differs by at least one tick"),
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
                        error_message=("RAW daily volumes differ beyond declared source precision"),
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

    def _validate_expected_dates(
        self,
        results: list[SourceResult[RawDailyBar]],
        *,
        request: EvidenceRequest,
        require_authority: bool = False,
    ) -> list[SourceResult[RawDailyBar]]:
        if self._calendar is None:
            if not require_authority:
                return results
            successful = [
                result
                for result in results
                if result.status is SourceStatus.SUCCESS_DATA and result.items
            ]
            return self._conflict(
                results,
                successful,
                status=SourceStatus.STALE,
                error_code="calendar_coverage_missing",
                error_message=(
                    "authoritative calendar is required for persisted K-line completeness"
                ),
            )
        successful = [
            result
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        if len(successful) < 2:
            return results

        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        start = request.start_at.date() if request.start_at else date.min
        requested_end = request.end_at.date() if request.end_at else date.max
        completed_end = min(
            requested_end,
            now.astimezone(SHANGHAI).date() - timedelta(days=1),
        )
        if start > completed_end:
            return results

        try:
            expected = set(
                self._calendar.open_dates(
                    market_code_for(request.stock_code),
                    start,
                    completed_end,
                )
            )
        except CalendarCoverageError as exc:
            return self._conflict(
                results,
                successful,
                status=SourceStatus.STALE,
                error_code="calendar_coverage_missing",
                error_message=str(exc),
            )

        if self._security_status_catalog is not None:
            try:
                status_window = self._security_status_catalog.resolve(
                    request.stock_code,
                    market_code_for(request.stock_code),
                    start,
                    completed_end,
                )
            except SecurityStatusCoverageError as exc:
                return self._conflict(
                    results,
                    successful,
                    status=SourceStatus.STALE,
                    error_code="security_status_coverage_missing",
                    error_message=str(exc),
                )
            expected = set(status_window.expected_dates(tuple(sorted(expected))))

        actual = {bar.trade_date for bar in successful[0].items}
        missing = sorted(expected - actual)
        if missing:
            dates = ", ".join(day.isoformat() for day in missing)
            return self._conflict(
                results,
                successful,
                error_code="expected_trading_date_missing",
                error_message=f"RAW daily sources jointly omit open dates: {dates}",
            )
        unexpected = sorted(actual - expected)
        if unexpected:
            dates = ", ".join(day.isoformat() for day in unexpected)
            return self._conflict(
                results,
                successful,
                error_code="unexpected_trading_date",
                error_message=f"RAW daily sources contain closed dates: {dates}",
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
        status: SourceStatus = SourceStatus.CONFLICTED,
        error_code: str,
        error_message: str,
    ) -> list[SourceResult[RawDailyBar]]:
        return [
            _unusable(
                result,
                status=status,
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
        trade_dates = sorted({bar.trade_date for result in successful for bar in result.items})
        canonical: list[RawDailyBar] = []
        for trade_date in trade_dates:
            candidates = [
                bar for result in successful for bar in result.items if bar.trade_date == trade_date
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
    """Process-level RAW daily sources plus immutable audit storage."""

    def __init__(
        self,
        store: KlineAuditStore | None = None,
        *,
        sina_source: SinaRawDailyKlineSource | None = None,
        tencent_source: TencentRawDailyKlineSource | None = None,
        calendar: OfficialTradingCalendar | None = DEFAULT_KLINE_CALENDAR,
        security_status_catalog: StaticSecurityStatusCatalog | None = None,
        now_provider: Callable[[], datetime] = _now_shanghai,
    ) -> None:
        self.store = store or KlineAuditStore(_kline_audit_root())
        sina = sina_source or SinaRawDailyKlineSource()
        tencent = tencent_source or TencentRawDailyKlineSource()
        registry = EvidenceSourceRegistry()
        registry.register(sina)
        registry.register(tencent)
        self.service = RawDailyKlineEvidenceService(
            registry,
            calendar=calendar,
            security_status_catalog=security_status_catalog,
            now_provider=now_provider,
            audited_sources=(sina, tencent),
        )

    def collect_and_persist(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy = KLINE_RAW_EVIDENCE_POLICY,
    ) -> tuple[EvidenceEnvelope, str]:
        """Collect, reconcile and durably publish complete or failed evidence."""
        return self.service.collect_and_persist(
            request,
            policy,
            self.store,
        )


_runtime: RawDailyKlineEvidenceRuntime | None = None


def get_raw_daily_kline_runtime() -> RawDailyKlineEvidenceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RawDailyKlineEvidenceRuntime()
    return _runtime


__all__ = [
    "DEFAULT_KLINE_AUDIT_ROOT",
    "KLINE_RAW_EVIDENCE_POLICY",
    "RawDailyKlineEvidenceRuntime",
    "RawDailyKlineEvidenceService",
    "get_raw_daily_kline_runtime",
]

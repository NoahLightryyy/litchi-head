"""一分钟分时双源运行时与失败关闭对账。"""

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
from src.data.intraday import IntradayBar, IntradayBarState, IntradaySourceSeries
from src.data.providers.intraday import (
    EastmoneyIntradaySource,
    TencentIntradaySource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
INTRADAY_PRICE_TICK = 0.01
INTRADAY_VOLUME_TOLERANCE_SHARES = 500

INTRADAY_EVIDENCE_POLICY = EvidencePolicy(
    capability=EvidenceCapability.INTRADAY,
    min_independent_upstreams=2,
    required_upstream_ids={"eastmoney", "tencent"},
)


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def _unusable(
    result: SourceResult[IntradaySourceSeries],
    *,
    status: SourceStatus,
    error_code: str,
    error_message: str,
) -> SourceResult[IntradaySourceSeries]:
    return result.model_copy(
        update={
            "status": status,
            "error_code": error_code,
            "error_message": error_message,
        }
    )


def _expected_latest_finalized(now: datetime) -> datetime | None:
    local = now.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return None
    clock = local.time().replace(tzinfo=None)
    minute = local.replace(second=0, microsecond=0)
    if time(9, 30) <= clock < time(11, 30):
        return minute
    if time(13, 0) <= clock < time(14, 57):
        return (
            minute
            if clock >= time(13, 1)
            else local.replace(hour=11, minute=30, second=0, microsecond=0)
        )
    return None


class IntradayEvidenceService:
    """并发采集两路分钟序列，并按已结束分钟逐点核验。"""

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
        if request.capability is not EvidenceCapability.INTRADAY:
            raise ValueError("IntradayEvidenceService only supports intraday evidence")
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")

        raw = self._collector.collect(request, policy)
        results = [
            self._validate_source(result, request=request, now=now)
            for result in raw.source_results
        ]
        results = self._validate_pair(results)
        assessment = self._registry.assess(policy, results)
        canonical: list[IntradayBar] = []
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
    def _validate_source(
        result: SourceResult[IntradaySourceSeries],
        *,
        request: EvidenceRequest,
        now: datetime,
    ) -> SourceResult[IntradaySourceSeries]:
        if result.status is not SourceStatus.SUCCESS_DATA:
            return result
        if len(result.items) != 1:
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="intraday_cardinality_invalid",
                error_message="Intraday source must return exactly one series",
            )
        series = result.items[0]
        if series.code != request.stock_code:
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="intraday_identity_conflict",
                error_message="Intraday series code does not match the request",
            )
        if result.upstream_id == "eastmoney" and (
            not series.ohlc_supported or not series.bars
        ):
            return _unusable(
                result,
                status=SourceStatus.CONFLICTED,
                error_code="intraday_ohlc_missing",
                error_message="Required Eastmoney OHLC minute bars are missing",
            )
        expected = _expected_latest_finalized(now)
        finalized_times = {
            point.timestamp
            for point in series.checkpoints
            if point.state is IntradayBarState.FINAL
        }
        if expected is not None and expected not in finalized_times:
            return _unusable(
                result,
                status=SourceStatus.STALE,
                error_code="intraday_coverage_lag",
                error_message="Intraday source is missing the latest finalized minute",
            )
        return result

    @staticmethod
    def _validate_pair(
        results: list[SourceResult[IntradaySourceSeries]],
    ) -> list[SourceResult[IntradaySourceSeries]]:
        successful = [
            result
            for result in results
            if result.status is SourceStatus.SUCCESS_DATA and result.items
        ]
        if len(successful) != 2:
            return results
        first = {
            point.timestamp: point
            for point in successful[0].items[0].checkpoints
            if point.state is IntradayBarState.FINAL
        }
        second = {
            point.timestamp: point
            for point in successful[1].items[0].checkpoints
            if point.state is IntradayBarState.FINAL
        }
        if first.keys() != second.keys():
            return IntradayEvidenceService._conflict(
                results,
                successful,
                error_code="intraday_minute_set_conflict",
                error_message="Finalized minute timestamp sets do not match",
            )
        common = sorted(first.keys() & second.keys())
        if not common:
            return [
                _unusable(
                    result,
                    status=SourceStatus.CONFLICTED,
                    error_code="intraday_no_common_finalized_minute",
                    error_message="Intraday sources have no common finalized minute",
                )
                if result in successful
                else result
                for result in results
            ]

        for timestamp in common:
            if abs(first[timestamp].close - second[timestamp].close) > (
                INTRADAY_PRICE_TICK + 1e-9
            ):
                return IntradayEvidenceService._conflict(
                    results,
                    successful,
                    error_code="intraday_price_conflict",
                    error_message="Finalized minute closes differ by more than one tick",
                )
            if abs(
                first[timestamp].cumulative_volume
                - second[timestamp].cumulative_volume
            ) > INTRADAY_VOLUME_TOLERANCE_SHARES:
                return IntradayEvidenceService._conflict(
                    results,
                    successful,
                    error_code="intraday_volume_conflict",
                    error_message=(
                        "Finalized cumulative volumes differ by more than 500 shares"
                    ),
                )
        return results

    @staticmethod
    def _conflict(
        results: list[SourceResult[IntradaySourceSeries]],
        successful: list[SourceResult[IntradaySourceSeries]],
        *,
        error_code: str,
        error_message: str,
    ) -> list[SourceResult[IntradaySourceSeries]]:
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
        results: list[SourceResult[IntradaySourceSeries]],
    ) -> list[IntradayBar]:
        for result in results:
            if result.upstream_id == "eastmoney" and result.items:
                return result.items[0].bars
        return []


class IntradayEvidenceRuntime:
    """持有进程级的两路分钟源。"""

    def __init__(self) -> None:
        registry = EvidenceSourceRegistry()
        registry.register(EastmoneyIntradaySource())
        registry.register(TencentIntradaySource())
        self.service = IntradayEvidenceService(registry)


_runtime: IntradayEvidenceRuntime | None = None


def get_intraday_evidence_runtime() -> IntradayEvidenceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = IntradayEvidenceRuntime()
    return _runtime


__all__ = [
    "INTRADAY_EVIDENCE_POLICY",
    "INTRADAY_PRICE_TICK",
    "INTRADAY_VOLUME_TOLERANCE_SHARES",
    "IntradayEvidenceRuntime",
    "IntradayEvidenceService",
    "get_intraday_evidence_runtime",
]

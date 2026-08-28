"""Two-source homepage market-index aggregation with explicit degradation."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from src.data.collector import HealthStats, get_health_stats
from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import StockQuote
from src.data.providers.quotes import (
    EastmoneyIndexQuoteSource,
    SinaIndexQuoteSource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
INDEX_PRICE_TOLERANCE = 0.01
INDEX_TIMESTAMP_TOLERANCE_SECONDS = 3.0
INDEX_STALE_CACHE_SECONDS = 30.0
INDEX_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("000001", "上证指数"),
    ("399001", "深证成指"),
    ("399006", "创业板指"),
)
IndexCollectionStatus = Literal["success", "partial", "empty", "stale", "failed"]


class IndexEvidenceSource(Protocol):
    descriptor: SourceDescriptor

    def fetch(self, request: EvidenceRequest) -> SourceResult[StockQuote]: ...


class IndexLimitation(BaseModel):
    code: str
    message: str
    index_code: str | None = None


class IndexSourceDiagnostic(BaseModel):
    index_code: str
    source_id: str
    upstream_id: str
    status: SourceStatus
    latency_ms: int = Field(ge=0)
    as_of: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class IndexConsensusQuote(BaseModel):
    code: str
    name: str
    price: float = Field(gt=0)
    change: float
    change_pct: float
    as_of: datetime
    source_count: int = Field(ge=1)
    cached: bool = False


class IndexQuoteCollection(BaseModel):
    status: IndexCollectionStatus
    quotes: list[IndexConsensusQuote] = Field(default_factory=list)
    missing_codes: list[str] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    limitations: list[IndexLimitation] = Field(default_factory=list)
    source_diagnostics: list[IndexSourceDiagnostic] = Field(default_factory=list)
    error_code: str | None = None


class _TimedSourceResult(BaseModel):
    result: SourceResult[StockQuote]
    latency_ms: int


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


class IndexQuoteService:
    """Collect Eastmoney and Sina concurrently and reconcile each index."""

    def __init__(
        self,
        *,
        sources: tuple[IndexEvidenceSource, ...] | None = None,
        now_provider: Callable[[], datetime] = _now_shanghai,
        health_stats: HealthStats | None = None,
        max_workers: int = 6,
    ) -> None:
        self._sources = sources or (
            EastmoneyIndexQuoteSource(),
            SinaIndexQuoteSource(),
        )
        if len({source.descriptor.upstream_id for source in self._sources}) < 2:
            raise ValueError("market indices require two independent upstreams")
        self._now_provider = now_provider
        self._health_stats = health_stats or get_health_stats()
        self._max_workers = max_workers
        self._cache: dict[str, tuple[IndexConsensusQuote, datetime]] = {}

    def collect(self) -> IndexQuoteCollection:
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")

        collected = self._collect_all()
        quotes: list[IndexConsensusQuote] = []
        missing_codes: list[str] = []
        limitations: list[IndexLimitation] = []
        diagnostics: list[IndexSourceDiagnostic] = []
        failed_upstreams: set[str] = set()
        any_conflict = False
        any_failure = False

        for code, name in INDEX_DEFINITIONS:
            timed = collected[code]
            reconciled, code_limitations, conflicted = self._reconcile_pair(
                code, name, timed,
            )
            limitations.extend(code_limitations)
            any_conflict = any_conflict or conflicted

            for item in timed:
                result = item.result
                if conflicted and result.status is SourceStatus.SUCCESS_DATA:
                    result = result.model_copy(update={
                        "status": SourceStatus.CONFLICTED,
                        "error_code": "index_quote_conflict",
                        "error_message": "指数来源价格或时间不一致",
                    })
                if result.status in {SourceStatus.FAILED, SourceStatus.CONFLICTED}:
                    failed_upstreams.add(result.upstream_id)
                    any_failure = True
                self._record_health(result, item.latency_ms)
                quote = result.items[0] if result.items else None
                diagnostics.append(IndexSourceDiagnostic(
                    index_code=code,
                    source_id=result.source_id,
                    upstream_id=result.upstream_id,
                    status=result.status,
                    latency_ms=item.latency_ms,
                    as_of=quote.fetched_at if quote is not None else None,
                    error_code=result.error_code,
                    error_message=self._safe_error_message(result),
                ))

            if reconciled is not None:
                quotes.append(reconciled)
                if reconciled.source_count >= 2:
                    self._cache[code] = (reconciled, now)
                continue

            cached = self._recent_cache(code, now) if not conflicted else None
            if cached is not None and self._all_failed(timed):
                quotes.append(cached)
                limitations.append(IndexLimitation(
                    code="INDEX_STALE_CACHE",
                    index_code=code,
                    message=f"{name} 当前双源失败，返回 30 秒内已核验缓存",
                ))
            else:
                missing_codes.append(code)

        if not quotes:
            if any_conflict:
                status: IndexCollectionStatus = "failed"
                error_code = "MARKET_INDICES_CONFLICTED"
            elif any_failure:
                status = "failed"
                error_code = "MARKET_INDICES_FAILED"
            else:
                status = "empty"
                error_code = None
        elif all(quote.cached for quote in quotes) and len(quotes) == len(INDEX_DEFINITIONS):
            status = "stale"
            error_code = None
        elif limitations or missing_codes or any_failure:
            status = "partial"
            error_code = None
        else:
            status = "success"
            error_code = None

        return IndexQuoteCollection(
            status=status,
            quotes=quotes,
            missing_codes=missing_codes,
            failed_sources=sorted(failed_upstreams),
            limitations=limitations,
            source_diagnostics=diagnostics,
            error_code=error_code,
        )

    def _collect_all(self) -> dict[str, list[_TimedSourceResult]]:
        jobs: list[tuple[str, IndexEvidenceSource]] = [
            (code, source)
            for code, _ in INDEX_DEFINITIONS
            for source in self._sources
        ]
        worker_count = min(self._max_workers, len(jobs))
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="market-index-source",
        ) as executor:
            futures = [
                executor.submit(self._fetch_one, code, source)
                for code, source in jobs
            ]
            collected = {code: [] for code, _ in INDEX_DEFINITIONS}
            for (code, _), future in zip(jobs, futures, strict=True):
                collected[code].append(future.result())
        return collected

    @staticmethod
    def _fetch_one(
        code: str,
        source: IndexEvidenceSource,
    ) -> _TimedSourceResult:
        started_at = time.perf_counter()
        request = EvidenceRequest(
            capability=EvidenceCapability.MARKET_INDEX,
            stock_code=code,
        )
        try:
            result = source.fetch(request)
        except Exception as exc:
            result = SourceResult[StockQuote](
                source_id=source.descriptor.source_id,
                upstream_id=source.descriptor.upstream_id,
                capability=EvidenceCapability.MARKET_INDEX,
                status=SourceStatus.FAILED,
                error_code="source_unhandled_exception",
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
        return _TimedSourceResult(
            result=result,
            latency_ms=round((time.perf_counter() - started_at) * 1000),
        )

    @staticmethod
    def _reconcile_pair(
        code: str,
        name: str,
        timed: list[_TimedSourceResult],
    ) -> tuple[IndexConsensusQuote | None, list[IndexLimitation], bool]:
        successful = [
            item.result for item in timed
            if item.result.status is SourceStatus.SUCCESS_DATA and item.result.items
        ]
        if len(successful) >= 2:
            quotes = [item.items[0] for item in successful]
            if any(item.code != code or item.price <= 0 for item in quotes):
                return None, [IndexLimitation(
                    code="INDEX_IDENTITY_CONFLICT",
                    index_code=code,
                    message=f"{name} 来源身份或价格无效",
                )], True
            timestamps = [item.fetched_at for item in quotes]
            if any(item is None or item.tzinfo is None for item in timestamps):
                return None, [IndexLimitation(
                    code="INDEX_TIMESTAMP_MISSING",
                    index_code=code,
                    message=f"{name} 来源缺少可核验时间",
                )], True
            aware_timestamps = [item for item in timestamps if item is not None]
            skew = max(aware_timestamps) - min(aware_timestamps)
            if skew.total_seconds() > INDEX_TIMESTAMP_TOLERANCE_SECONDS:
                return None, [IndexLimitation(
                    code="INDEX_TIMESTAMP_CONFLICT",
                    index_code=code,
                    message=f"{name} 双源时间差超过 3 秒",
                )], True
            prices = [item.price for item in quotes]
            if max(prices) - min(prices) > INDEX_PRICE_TOLERANCE + 1e-9:
                return None, [IndexLimitation(
                    code="INDEX_PRICE_CONFLICT",
                    index_code=code,
                    message=f"{name} 双源价格差超过 0.01 点",
                )], True
            canonical = max(
                quotes,
                key=lambda item: item.fetched_at or datetime.min.replace(tzinfo=SHANGHAI),
            )
            assert canonical.fetched_at is not None
            return IndexConsensusQuote(
                code=code,
                name=name,
                price=canonical.price,
                change=canonical.change,
                change_pct=canonical.change_pct,
                as_of=canonical.fetched_at,
                source_count=len(successful),
            ), [], False

        if len(successful) == 1:
            quote = successful[0].items[0]
            if (
                quote.code != code
                or quote.price <= 0
                or quote.fetched_at is None
                or quote.fetched_at.tzinfo is None
            ):
                return None, [IndexLimitation(
                    code="INDEX_IDENTITY_CONFLICT",
                    index_code=code,
                    message=f"{name} 唯一可用来源身份、价格或时间无效",
                )], True
            return IndexConsensusQuote(
                code=code,
                name=name,
                price=quote.price,
                change=quote.change,
                change_pct=quote.change_pct,
                as_of=quote.fetched_at,
                source_count=1,
            ), [IndexLimitation(
                code="INDEX_SINGLE_SOURCE",
                index_code=code,
                message=f"{name} 当前仅一个独立来源可用",
            )], False
        return None, [], False

    def _recent_cache(
        self,
        code: str,
        now: datetime,
    ) -> IndexConsensusQuote | None:
        cached = self._cache.get(code)
        if cached is None:
            return None
        quote, cached_at = cached
        if (now - cached_at).total_seconds() > INDEX_STALE_CACHE_SECONDS:
            return None
        return quote.model_copy(update={"cached": True})

    @staticmethod
    def _all_failed(timed: list[_TimedSourceResult]) -> bool:
        return bool(timed) and all(
            item.result.status is SourceStatus.FAILED for item in timed
        )

    def _record_health(self, result: SourceResult[StockQuote], latency_ms: int) -> None:
        endpoint = f"market_index:{result.upstream_id}"
        if result.status in {SourceStatus.FAILED, SourceStatus.CONFLICTED}:
            self._health_stats.record_call(
                endpoint,
                latency_ms,
                error=result.error_code or result.status.value,
                error_code=result.error_code or result.status.value,
            )
        else:
            self._health_stats.record_call(
                endpoint,
                latency_ms,
                empty=result.status is SourceStatus.SUCCESS_EMPTY,
            )

    @staticmethod
    def _safe_error_message(result: SourceResult[StockQuote]) -> str | None:
        if result.status not in {SourceStatus.FAILED, SourceStatus.CONFLICTED}:
            return None
        return "来源请求失败" if result.status is SourceStatus.FAILED else "来源数据冲突"


_runtime: IndexQuoteService | None = None


def get_index_quote_service() -> IndexQuoteService:
    global _runtime
    if _runtime is None:
        _runtime = IndexQuoteService()
    return _runtime


__all__ = [
    "INDEX_DEFINITIONS",
    "INDEX_PRICE_TOLERANCE",
    "INDEX_STALE_CACHE_SECONDS",
    "INDEX_TIMESTAMP_TOLERANCE_SECONDS",
    "IndexConsensusQuote",
    "IndexLimitation",
    "IndexQuoteCollection",
    "IndexQuoteService",
    "IndexSourceDiagnostic",
    "get_index_quote_service",
]

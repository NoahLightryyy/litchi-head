"""Homepage market-index multi-source aggregation contract."""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.data.collector import HealthStats
from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.index_quote_runtime import IndexQuoteService
from src.data.models import StockQuote
from src.data.providers.quotes import (
    EastmoneyIndexQuoteSource,
    SinaIndexQuoteSource,
    _eastmoney_index_secid,
    _sina_index_symbol,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 27, 14, 11, 23, tzinfo=SHANGHAI)
INDEX_CODES = ("000001", "399001", "399006")


def _quote(
    code: str,
    *,
    price: float = 3943.53,
    fetched_at: datetime = NOW,
) -> StockQuote:
    return StockQuote(
        code=code,
        name={
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
        }[code],
        price=price,
        change=31.01,
        change_pct=0.79,
        volume=100,
        fetched_at=fetched_at,
    )


def _result(
    source_id: str,
    upstream_id: str,
    code: str,
    *,
    status: SourceStatus = SourceStatus.SUCCESS_DATA,
    price: float = 3943.53,
    fetched_at: datetime = NOW,
) -> SourceResult[StockQuote]:
    return SourceResult(
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.MARKET_INDEX,
        status=status,
        items=[_quote(code, price=price, fetched_at=fetched_at)]
        if status is SourceStatus.SUCCESS_DATA
        else [],
        error_code="upstream_failed" if status is SourceStatus.FAILED else None,
        error_message="timeout" if status is SourceStatus.FAILED else None,
    )


class StubIndexSource:
    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        results: dict[str, SourceResult[StockQuote]],
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.MARKET_INDEX},
        )
        self._results = results

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        return self._results[request.stock_code]


def _source(
    source_id: str,
    upstream_id: str,
    *,
    status_by_code: dict[str, SourceStatus] | None = None,
    price_by_code: dict[str, float] | None = None,
) -> StubIndexSource:
    statuses = status_by_code or {}
    prices = price_by_code or {}
    return StubIndexSource(
        source_id,
        upstream_id,
        {
            code: _result(
                source_id,
                upstream_id,
                code,
                status=statuses.get(code, SourceStatus.SUCCESS_DATA),
                price=prices.get(code, 3943.53),
            )
            for code in INDEX_CODES
        },
    )


def _service(
    eastmoney: StubIndexSource,
    sina: StubIndexSource,
    *,
    health_stats: HealthStats | None = None,
) -> IndexQuoteService:
    return IndexQuoteService(
        sources=(eastmoney, sina),
        now_provider=lambda: NOW,
        health_stats=health_stats or HealthStats(),
    )


def test_index_symbol_mapping_does_not_treat_shanghai_index_as_sz_stock() -> None:
    assert _eastmoney_index_secid("000001") == "1.000001"
    assert _eastmoney_index_secid("399001") == "0.399001"
    assert _eastmoney_index_secid("399006") == "0.399006"
    assert _sina_index_symbol("000001") == "sh000001"
    assert _sina_index_symbol("399001") == "sz399001"
    assert _sina_index_symbol("399006") == "sz399006"


def test_eastmoney_index_source_parses_exchange_timestamp() -> None:
    source = EastmoneyIndexQuoteSource(fetcher=lambda code: {"data": {
        "f57": code,
        "f58": "上证指数",
        "f43": 394353,
        "f44": 394623,
        "f45": 390931,
        "f46": 391189,
        "f47": 4304003,
        "f48": 841856038642,
        "f60": 391252,
        "f86": int(NOW.timestamp()),
        "f169": 3101,
        "f170": 79,
    }})

    result = source.fetch(EvidenceRequest(
        capability=EvidenceCapability.MARKET_INDEX,
        stock_code="000001",
    ))

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 3943.53
    assert result.items[0].fetched_at == NOW


def test_sina_index_source_validates_index_symbol() -> None:
    fields = [
        "上证指数", "3911.8908", "3912.5235", "3943.5296", "3946.2303",
        "3909.3122", "0", "0", "430400333", "841856038642",
        *("0" for _ in range(20)), "2026-08-27", "14:11:23", "00",
    ]
    source = SinaIndexQuoteSource(
        fetcher=lambda code: f'var hq_str_sh{code}="{",".join(fields)}";',
    )

    result = source.fetch(EvidenceRequest(
        capability=EvidenceCapability.MARKET_INDEX,
        stock_code="000001",
    ))

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 3943.5296
    assert result.items[0].fetched_at == NOW


def test_two_aligned_sources_produce_complete_indices() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina"),
    ).collect()

    assert result.status == "success"
    assert [item.code for item in result.quotes] == list(INDEX_CODES)
    assert all(item.source_count == 2 for item in result.quotes)
    assert len(result.source_diagnostics) == 6


def test_one_failed_source_returns_partial_with_usable_quotes() -> None:
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina", status_by_code=failed),
    ).collect()

    assert result.status == "partial"
    assert len(result.quotes) == 3
    assert all(item.source_count == 1 for item in result.quotes)
    assert result.failed_sources == ["sina"]
    assert {item.code for item in result.limitations} == {"INDEX_SINGLE_SOURCE"}


def test_one_index_conflict_is_omitted_while_other_indices_remain_partial() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source(
            "sina-index",
            "sina",
            price_by_code={"399001": 3943.55},
        ),
    ).collect()

    assert result.status == "partial"
    assert [item.code for item in result.quotes] == ["000001", "399006"]
    assert result.missing_codes == ["399001"]
    assert any(item.code == "INDEX_PRICE_CONFLICT" for item in result.limitations)
    conflicted = [
        item for item in result.source_diagnostics
        if item.index_code == "399001"
    ]
    assert {item.status for item in conflicted} == {SourceStatus.CONFLICTED}


def test_all_indices_conflicted_fail_closed() -> None:
    result = _service(
        _source("eastmoney-index", "eastmoney"),
        _source(
            "sina-index",
            "sina",
            price_by_code={code: 3943.55 for code in INDEX_CODES},
        ),
    ).collect()

    assert result.status == "failed"
    assert result.error_code == "MARKET_INDICES_CONFLICTED"
    assert result.quotes == []


def test_recent_accepted_cache_is_stale_when_both_sources_fail() -> None:
    eastmoney = _source("eastmoney-index", "eastmoney")
    sina = _source("sina-index", "sina")
    service = _service(eastmoney, sina)
    assert service.collect().status == "success"

    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    eastmoney._results = _source(
        "eastmoney-index", "eastmoney", status_by_code=failed,
    )._results
    sina._results = _source(
        "sina-index", "sina", status_by_code=failed,
    )._results
    service._now_provider = lambda: NOW + timedelta(seconds=20)

    result = service.collect()

    assert result.status == "stale"
    assert len(result.quotes) == 3
    assert all(item.cached for item in result.quotes)


def test_all_sources_failed_without_cache_returns_failed() -> None:
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney", status_by_code=failed),
        _source("sina-index", "sina", status_by_code=failed),
    ).collect()

    assert result.status == "failed"
    assert result.error_code == "MARKET_INDICES_FAILED"
    assert result.quotes == []


def test_successful_empty_sources_return_empty_not_failed() -> None:
    empty = {code: SourceStatus.SUCCESS_EMPTY for code in INDEX_CODES}
    result = _service(
        _source("eastmoney-index", "eastmoney", status_by_code=empty),
        _source("sina-index", "sina", status_by_code=empty),
    ).collect()

    assert result.status == "empty"
    assert result.quotes == []


def test_source_health_records_failure_separately_from_success() -> None:
    stats = HealthStats()
    failed = {code: SourceStatus.FAILED for code in INDEX_CODES}

    _service(
        _source("eastmoney-index", "eastmoney"),
        _source("sina-index", "sina", status_by_code=failed),
        health_stats=stats,
    ).collect()

    snapshot = stats.snapshot()
    assert snapshot["market_index:eastmoney"]["success"] == 3
    assert snapshot["market_index:sina"]["failures"] == 3

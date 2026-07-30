"""KR-1 completed RAW daily K-line evidence contracts.

User journeys:
- As an investor, I receive one auditable RAW daily series only when two
  independent upstreams agree on every completed bar.
- As an investor, I see an explicit failure instead of a single-source green
  light when BSE has no verified second upstream.
- As a downstream consumer, I never receive today's changing daily bar inside
  the completed historical series.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from src.data.evidence import (
    EvidenceCapability,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.kline import MarketCode, RawDailyBar, market_code_for
from src.data.kline_runtime import (
    KLINE_RAW_EVIDENCE_POLICY,
    RawDailyKlineEvidenceService,
)
from src.data.providers.kline import (
    SinaRawDailyKlineSource,
    TencentRawDailyKlineSource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=SHANGHAI)
REQUEST = EvidenceRequest(
    capability=EvidenceCapability.KLINE,
    stock_code="000001",
    start_at=datetime(2026, 7, 28, tzinfo=SHANGHAI),
    end_at=datetime(2026, 7, 30, 23, 59, tzinfo=SHANGHAI),
)


def _sina_payload(
    *,
    code: str = "000001",
    first_close: str = "11.200",
    first_volume: str = "106101129",
    include_first: bool = True,
    include_today: bool = True,
) -> str:
    rows: list[str] = []
    if include_first:
        rows.append(
            '{"day":"2026-07-28","open":"11.100","high":"11.210",'
            f'"low":"11.090","close":"{first_close}",'
            f'"volume":"{first_volume}"}}'
        )
    rows.append(
        '{"day":"2026-07-29","open":"11.190","high":"11.360",'
        '"low":"11.180","close":"11.280","volume":"151105407"}'
    )
    if include_today:
        rows.append(
            '{"day":"2026-07-30","open":"11.280","high":"11.520",'
            '"low":"11.180","close":"11.510","volume":"133636700"}'
        )
    symbol = f"sz{code}"
    return (
        "/*<script>location.href='//sina.com';</script>*/\n"
        f"var _{symbol}_240_20=([{','.join(rows)}]);"
    )


def _tencent_payload(
    *,
    first_close: str = "11.200",
    first_volume_lots: str = "1061011.000",
    include_first: bool = True,
    include_today: bool = True,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    if include_first:
        rows.append(
            [
                "2026-07-28",
                "11.100",
                first_close,
                "11.210",
                "11.090",
                first_volume_lots,
            ]
        )
    rows.append(
        ["2026-07-29", "11.190", "11.280", "11.360", "11.180", "1511054.000"]
    )
    if include_today:
        rows.append(
            ["2026-07-30", "11.280", "11.510", "11.520", "11.180", "1336367"]
        )
    return {
        "code": 0,
        "msg": "",
        "data": {"sz000001": {"day": rows}},
    }


def _bar(
    trade_date: date,
    *,
    code: str = "000001",
    market: MarketCode = MarketCode.SZSE,
    close: str = "11.20",
    volume: int = 106_101_129,
    volume_precision: int = 1,
) -> RawDailyBar:
    return RawDailyBar(
        code=code,
        market=market,
        trade_date=trade_date,
        open=Decimal("11.10"),
        high=Decimal("11.21"),
        low=Decimal("11.09"),
        close=Decimal(close),
        volume=volume,
        volume_precision=volume_precision,
        price_tick=Decimal("0.01"),
    )


class StubKlineSource:
    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        result: SourceResult[RawDailyBar],
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.KLINE},
        )
        self._result = result

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        return self._result


def _result(
    source_id: str,
    upstream_id: str,
    bars: list[RawDailyBar],
    *,
    status: SourceStatus = SourceStatus.SUCCESS_DATA,
    error_code: str | None = None,
) -> SourceResult[RawDailyBar]:
    return SourceResult(
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.KLINE,
        status=status,
        items=bars if status is SourceStatus.SUCCESS_DATA else [],
        error_code=error_code,
    )


def _service(
    sina: SourceResult[RawDailyBar],
    tencent: SourceResult[RawDailyBar],
) -> RawDailyKlineEvidenceService:
    registry = EvidenceSourceRegistry()
    registry.register(StubKlineSource("direct-sina-raw-daily", "sina", sina))
    registry.register(StubKlineSource("direct-tencent-raw-daily", "tencent", tencent))
    return RawDailyKlineEvidenceService(registry)


def test_raw_bar_rejects_prices_that_are_not_aligned_to_price_tick() -> None:
    with pytest.raises(ValueError, match="price_tick"):
        _bar(date(2026, 7, 28), close="11.205")


@pytest.mark.parametrize(
    ("code", "market"),
    [
        ("600000", MarketCode.SSE),
        ("000001", MarketCode.SZSE),
        ("920002", MarketCode.BSE),
    ],
)
def test_market_routing_covers_all_a_share_exchanges(
    code: str,
    market: MarketCode,
) -> None:
    assert market_code_for(code) is market


def test_sina_source_parses_share_precision_and_excludes_current_day() -> None:
    result = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: _sina_payload(),
        now_provider=lambda: NOW,
    ).fetch(REQUEST)

    assert result.status is SourceStatus.SUCCESS_DATA
    assert [bar.trade_date for bar in result.items] == [
        date(2026, 7, 28),
        date(2026, 7, 29),
    ]
    assert result.items[0].market is MarketCode.SZSE
    assert result.items[0].volume == 106_101_129
    assert result.items[0].volume_precision == 1
    assert result.items[0].price_basis == "raw"


def test_tencent_source_normalizes_lots_and_excludes_current_day() -> None:
    result = TencentRawDailyKlineSource(
        fetcher=lambda code, start, end: _tencent_payload(),
        now_provider=lambda: NOW,
    ).fetch(REQUEST)

    assert result.status is SourceStatus.SUCCESS_DATA
    assert [bar.trade_date for bar in result.items] == [
        date(2026, 7, 28),
        date(2026, 7, 29),
    ]
    assert result.items[0].volume == 106_101_100
    assert result.items[0].volume_precision == 100


def test_tencent_bse_is_explicitly_unsupported_not_empty() -> None:
    request = REQUEST.model_copy(update={"stock_code": "920002"})
    called = False

    def fetcher(code: str, start: date, end: date) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    result = TencentRawDailyKlineSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    ).fetch(request)

    assert called is False
    assert result.status is SourceStatus.UNSUPPORTED
    assert result.error_code == "independent_upstream_missing"


@pytest.mark.parametrize(
    "source",
    [
        SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: (_ for _ in ()).throw(
                TimeoutError("timeout")
            ),
            now_provider=lambda: NOW,
        ),
        TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: (_ for _ in ()).throw(
                TimeoutError("timeout")
            ),
            now_provider=lambda: NOW,
        ),
    ],
)
def test_transport_failure_is_failed_not_empty(
    source: SinaRawDailyKlineSource | TencentRawDailyKlineSource,
) -> None:
    result = source.fetch(REQUEST)

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "upstream_request_failed"
    assert result.error_message == "timeout"


@pytest.mark.parametrize(
    "source",
    [
        SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: "broken",
            now_provider=lambda: NOW,
        ),
        TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: {"code": 0, "data": {}},
            now_provider=lambda: NOW,
        ),
    ],
)
def test_malformed_payload_is_failed_not_empty(
    source: SinaRawDailyKlineSource | TencentRawDailyKlineSource,
) -> None:
    result = source.fetch(REQUEST)

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert result.error_message


@pytest.mark.parametrize(
    "source",
    [
        SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: _sina_payload(),
            now_provider=lambda: NOW,
        ),
        TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: _tencent_payload(),
            now_provider=lambda: NOW,
        ),
    ],
)
def test_non_kline_capability_is_explicitly_unsupported(
    source: SinaRawDailyKlineSource | TencentRawDailyKlineSource,
) -> None:
    request = EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code="000001",
    )

    result = source.fetch(request)

    assert result.status is SourceStatus.UNSUPPORTED


def test_aligned_raw_sources_publish_precise_canonical_bars() -> None:
    sina_bars = [
        _bar(date(2026, 7, 28)),
        _bar(date(2026, 7, 29), volume=151_105_407),
    ]
    tencent_bars = [
        _bar(
            date(2026, 7, 28),
            volume=106_101_100,
            volume_precision=100,
        ),
        _bar(
            date(2026, 7, 29),
            volume=151_105_400,
            volume_precision=100,
        ),
    ]

    envelope = _service(
        _result("direct-sina-raw-daily", "sina", sina_bars),
        _result("direct-tencent-raw-daily", "tencent", tencent_bars),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is True
    assert envelope.assessment.successful_upstream_ids == {"sina", "tencent"}
    assert [bar.volume for bar in envelope.items] == [106_101_129, 151_105_407]
    assert all(bar.volume_precision == 1 for bar in envelope.items)


def test_one_price_tick_difference_is_conflicted() -> None:
    sina = [_bar(date(2026, 7, 28), close="11.20")]
    tencent = [
        _bar(
            date(2026, 7, 28),
            close="11.21",
            volume=106_101_100,
            volume_precision=100,
        )
    ]

    envelope = _service(
        _result("direct-sina-raw-daily", "sina", sina),
        _result("direct-tencent-raw-daily", "tencent", tencent),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.status for result in envelope.source_results
    } == {SourceStatus.CONFLICTED}
    assert {
        result.error_code for result in envelope.source_results
    } == {"raw_ohlc_conflict"}


@pytest.mark.parametrize(
    ("volume_difference", "complete"),
    [(99, True), (100, False)],
)
def test_volume_difference_uses_declared_source_precision(
    volume_difference: int,
    complete: bool,
) -> None:
    precise_volume = 106_101_199
    sina = [_bar(date(2026, 7, 28), volume=precise_volume)]
    tencent = [
        _bar(
            date(2026, 7, 28),
            volume=precise_volume - volume_difference,
            volume_precision=100,
        )
    ]

    envelope = _service(
        _result("direct-sina-raw-daily", "sina", sina),
        _result("direct-tencent-raw-daily", "tencent", tencent),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is complete
    if not complete:
        assert {
            result.error_code for result in envelope.source_results
        } == {"raw_volume_conflict"}


def test_completed_trade_date_set_mismatch_is_conflicted() -> None:
    envelope = _service(
        _result(
            "direct-sina-raw-daily",
            "sina",
            [_bar(date(2026, 7, 28)), _bar(date(2026, 7, 29))],
        ),
        _result(
            "direct-tencent-raw-daily",
            "tencent",
            [_bar(date(2026, 7, 29), volume_precision=100)],
        ),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"trading_date_conflict"}


def test_duplicate_trade_date_from_one_source_is_conflicted() -> None:
    duplicate = _bar(date(2026, 7, 28))
    envelope = _service(
        _result("direct-sina-raw-daily", "sina", [duplicate, duplicate]),
        _result(
            "direct-tencent-raw-daily",
            "tencent",
            [
                _bar(
                    date(2026, 7, 28),
                    volume=106_101_100,
                    volume_precision=100,
                )
            ],
        ),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert envelope.source_results[0].error_code == "duplicate_trading_date"


def test_price_tick_mismatch_is_conflicted_before_price_comparison() -> None:
    sina = [_bar(date(2026, 7, 28))]
    tencent = [
        _bar(
            date(2026, 7, 28),
            volume=106_101_100,
            volume_precision=100,
        ).model_copy(update={"price_tick": Decimal("0.001")})
    ]

    envelope = _service(
        _result("direct-sina-raw-daily", "sina", sina),
        _result("direct-tencent-raw-daily", "tencent", tencent),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"price_tick_conflict"}


def test_amount_difference_uses_declared_precision_when_both_sources_supply_it() -> None:
    base = _bar(date(2026, 7, 28))
    sina = base.model_copy(
        update={
            "amount": Decimal("1000.00"),
            "amount_precision": Decimal("0.01"),
        }
    )
    tencent = base.model_copy(
        update={
            "volume": 106_101_100,
            "volume_precision": 100,
            "amount": Decimal("1000.01"),
            "amount_precision": Decimal("0.01"),
        }
    )

    envelope = _service(
        _result("direct-sina-raw-daily", "sina", [sina]),
        _result("direct-tencent-raw-daily", "tencent", [tencent]),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"raw_amount_conflict"}


def test_two_empty_windows_do_not_count_as_complete_kline_evidence() -> None:
    envelope = _service(
        _result(
            "direct-sina-raw-daily",
            "sina",
            [],
            status=SourceStatus.SUCCESS_EMPTY,
        ),
        _result(
            "direct-tencent-raw-daily",
            "tencent",
            [],
            status=SourceStatus.SUCCESS_EMPTY,
        ),
    ).collect(REQUEST, KLINE_RAW_EVIDENCE_POLICY)

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"kline_window_empty"}


def test_kline_service_requires_an_explicit_time_window() -> None:
    request = EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code="000001",
    )
    service = _service(
        _result(
            "direct-sina-raw-daily",
            "sina",
            [_bar(date(2026, 7, 28))],
        ),
        _result(
            "direct-tencent-raw-daily",
            "tencent",
            [
                _bar(
                    date(2026, 7, 28),
                    volume=106_101_100,
                    volume_precision=100,
                )
            ],
        ),
    )

    with pytest.raises(ValueError, match="start_at and end_at"):
        service.collect(request, KLINE_RAW_EVIDENCE_POLICY)


def test_kline_service_requires_timezone_aware_time_bounds() -> None:
    request = REQUEST.model_copy(
        update={
            "start_at": datetime(2026, 7, 28),
            "end_at": datetime(2026, 7, 30, 23, 59),
        }
    )
    service = _service(
        _result(
            "direct-sina-raw-daily",
            "sina",
            [_bar(date(2026, 7, 28))],
        ),
        _result(
            "direct-tencent-raw-daily",
            "tencent",
            [
                _bar(
                    date(2026, 7, 28),
                    volume=106_101_100,
                    volume_precision=100,
                )
            ],
        ),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        service.collect(request, KLINE_RAW_EVIDENCE_POLICY)


def test_bse_single_source_never_gets_dual_source_green_light() -> None:
    request = REQUEST.model_copy(update={"stock_code": "920002"})
    registry = EvidenceSourceRegistry()
    registry.register(
        StubKlineSource(
            "direct-sina-raw-daily",
            "sina",
            _result(
                "direct-sina-raw-daily",
                "sina",
                [
                    _bar(
                        date(2026, 7, 29),
                        code="920002",
                        market=MarketCode.BSE,
                    )
                ],
            ),
        )
    )
    registry.register(
        StubKlineSource(
            "direct-tencent-raw-daily",
            "tencent",
            _result(
                "direct-tencent-raw-daily",
                "tencent",
                [],
                status=SourceStatus.UNSUPPORTED,
                error_code="independent_upstream_missing",
            ),
        )
    )

    envelope = RawDailyKlineEvidenceService(registry).collect(
        request,
        KLINE_RAW_EVIDENCE_POLICY,
    )

    assert envelope.complete is False
    assert envelope.assessment.successful_upstream_ids == {"sina"}
    assert envelope.assessment.missing_required_upstream_ids == {"tencent"}
    assert envelope.source_results[1].error_code == "independent_upstream_missing"

"""KR-1B official market-calendar and expected-date contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
from src.data.kline import MarketCode, RawDailyBar
from src.data.kline_calendar import (
    CalendarCoverageError,
    OfficialSecurityStatusWindow,
    SecurityStatusCoverageError,
    StaticSecurityStatusCatalog,
    official_a_share_calendar_2026,
)
from src.data.kline_runtime import (
    KLINE_RAW_EVIDENCE_POLICY,
    RawDailyKlineEvidenceService,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _bar(trade_date: date, *, volume_precision: int = 1) -> RawDailyBar:
    return RawDailyBar(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=trade_date,
        open=Decimal("11.10"),
        high=Decimal("11.30"),
        low=Decimal("11.00"),
        close=Decimal("11.20"),
        volume=100_000,
        volume_precision=volume_precision,
    )


class _StaticKlineSource:
    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        bars: list[RawDailyBar],
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.KLINE},
        )
        self._bars = bars

    def fetch(self, request: EvidenceRequest) -> SourceResult[RawDailyBar]:
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=EvidenceCapability.KLINE,
            status=SourceStatus.SUCCESS_DATA,
            items=self._bars,
        )


def _service(bars: list[RawDailyBar]) -> RawDailyKlineEvidenceService:
    registry = EvidenceSourceRegistry()
    registry.register(_StaticKlineSource("sina", "sina", bars))
    registry.register(
        _StaticKlineSource(
            "tencent",
            "tencent",
            [
                bar.model_copy(update={"volume_precision": 100})
                for bar in bars
            ],
        )
    )
    return RawDailyKlineEvidenceService(
        registry,
        calendar=official_a_share_calendar_2026(),
        now_provider=lambda: datetime(2026, 7, 30, 16, 0, tzinfo=SHANGHAI),
    )


def _request(start: date, end: date) -> EvidenceRequest:
    return EvidenceRequest(
        capability=EvidenceCapability.KLINE,
        stock_code="000001",
        start_at=datetime.combine(start, datetime.min.time(), SHANGHAI),
        end_at=datetime.combine(end, datetime.max.time(), SHANGHAI),
    )


def test_official_calendar_excludes_weekends_and_announced_closures() -> None:
    calendar = official_a_share_calendar_2026()

    assert calendar.open_dates(
        MarketCode.SSE,
        date(2026, 1, 1),
        date(2026, 1, 6),
    ) == (date(2026, 1, 5), date(2026, 1, 6))


def test_calendar_keeps_separate_authority_versions_per_exchange() -> None:
    calendar = official_a_share_calendar_2026()

    versions = calendar.versions
    assert {version.market for version in versions} == {
        MarketCode.SSE,
        MarketCode.SZSE,
        MarketCode.BSE,
    }
    assert len({version.source_url for version in versions}) == 3
    assert all(len(version.content_hash) == 64 for version in versions)


def test_calendar_fails_closed_outside_versioned_years() -> None:
    calendar = official_a_share_calendar_2026()

    with pytest.raises(CalendarCoverageError, match="2025"):
        calendar.open_dates(
            MarketCode.SZSE,
            date(2025, 12, 31),
            date(2026, 1, 5),
        )


def test_two_sources_cannot_jointly_omit_an_expected_open_date() -> None:
    envelope = _service([_bar(date(2026, 7, 29))]).collect(
        _request(date(2026, 7, 28), date(2026, 7, 29)),
        KLINE_RAW_EVIDENCE_POLICY,
    )

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"expected_trading_date_missing"}


def test_two_sources_pass_when_all_expected_open_dates_are_present() -> None:
    bars = [_bar(date(2026, 7, 28)), _bar(date(2026, 7, 29))]

    envelope = _service(bars).collect(
        _request(date(2026, 7, 28), date(2026, 7, 29)),
        KLINE_RAW_EVIDENCE_POLICY,
    )

    assert envelope.complete is True
    assert [bar.trade_date for bar in envelope.items] == [
        date(2026, 7, 28),
        date(2026, 7, 29),
    ]


def test_calendar_coverage_gap_is_visible_and_fails_closed() -> None:
    envelope = _service([_bar(date(2026, 1, 5))]).collect(
        _request(date(2025, 12, 31), date(2026, 1, 5)),
        KLINE_RAW_EVIDENCE_POLICY,
    )

    assert envelope.complete is False
    assert {
        result.error_code for result in envelope.source_results
    } == {"calendar_coverage_missing"}


def test_only_official_full_day_suspension_excludes_an_open_date() -> None:
    status = OfficialSecurityStatusWindow(
        code="300996",
        market=MarketCode.SZSE,
        coverage_start=date(2026, 7, 27),
        coverage_end=date(2026, 7, 29),
        listed_on=date(2021, 6, 3),
        full_day_suspensions=(
            date(2026, 7, 27),
            date(2026, 7, 28),
            date(2026, 7, 29),
        ),
        intraday_suspensions=(),
        source_urls=("https://disc.static.szse.cn/official.pdf",),
    )

    assert status.expected_dates(
        (date(2026, 7, 27), date(2026, 7, 28), date(2026, 7, 29))
    ) == ()


def test_intraday_suspension_does_not_remove_the_daily_bar() -> None:
    status = OfficialSecurityStatusWindow(
        code="920176",
        market=MarketCode.BSE,
        coverage_start=date(2026, 7, 27),
        coverage_end=date(2026, 7, 27),
        listed_on=date(2026, 7, 27),
        full_day_suspensions=(),
        intraday_suspensions=(date(2026, 7, 27),),
        source_urls=(
            "https://www.bse.cn/disclosure/select_stop/200028788.html",
        ),
    )

    assert status.expected_dates((date(2026, 7, 27),)) == (
        date(2026, 7, 27),
    )


def test_security_lifecycle_excludes_dates_before_listing_and_after_delisting() -> None:
    status = OfficialSecurityStatusWindow(
        code="301513",
        market=MarketCode.SZSE,
        coverage_start=date(2026, 4, 16),
        coverage_end=date(2026, 4, 20),
        listed_on=date(2026, 4, 17),
        delisted_on=date(2026, 4, 20),
        full_day_suspensions=(),
        intraday_suspensions=(),
        source_urls=("https://www.szse.cn/official-listing.html",),
    )

    assert status.expected_dates(
        (date(2026, 4, 16), date(2026, 4, 17), date(2026, 4, 20))
    ) == (date(2026, 4, 17),)


def test_security_status_catalog_fails_when_window_is_not_covered() -> None:
    status = OfficialSecurityStatusWindow(
        code="000001",
        market=MarketCode.SZSE,
        coverage_start=date(2026, 7, 28),
        coverage_end=date(2026, 7, 29),
        listed_on=date(1991, 4, 3),
        full_day_suspensions=(),
        intraday_suspensions=(),
        source_urls=("https://www.szse.cn/official-status.html",),
    )
    catalog = StaticSecurityStatusCatalog((status,))

    with pytest.raises(SecurityStatusCoverageError, match="2026-07-27"):
        catalog.resolve(
            "000001",
            MarketCode.SZSE,
            date(2026, 7, 27),
            date(2026, 7, 29),
        )

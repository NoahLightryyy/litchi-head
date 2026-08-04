"""KR-3B runtime assembly from the three verified market-data layers."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    SourceResult,
    SourceStatus,
)
from src.data.intraday import (
    IntradayBar,
    IntradayBarState,
    IntradayCheckpoint,
    IntradaySourceSeries,
)
from src.data.kline import MarketCode, RawDailyBar
from src.data.kline_adjustment import AdjustedDailyBar, AdjustedKlineSeries
from src.data.kline_business import TradingPhase
from src.data.kline_business_runtime import assemble_complete_kline_business
from src.data.models import StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")
AS_OF = datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI)
DAILY_SNAPSHOT_ID = "raw:000001:2026-08-03"


def _assessment(
    capability: EvidenceCapability,
    upstream_ids: tuple[str, str],
) -> EvidenceAssessment:
    return EvidenceAssessment(
        capability=capability,
        complete=True,
        successful_upstream_ids=set(upstream_ids),
        successful_source_ids={f"direct-{item}" for item in upstream_ids},
        missing_independent_upstreams=0,
    )


def _daily_evidence() -> EvidenceEnvelope:
    raw = RawDailyBar(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=date(2026, 8, 3),
        open=Decimal("10.00"),
        high=Decimal("10.30"),
        low=Decimal("9.90"),
        close=Decimal("10.20"),
        volume=1_000_000,
        amount=Decimal("10100000.00"),
        amount_precision=Decimal("0.01"),
    )
    capability = EvidenceCapability.KLINE
    upstream_ids = ("sina", "tencent")
    return EvidenceEnvelope(
        request=EvidenceRequest(
            capability=capability,
            stock_code="000001",
            start_at=datetime(2026, 8, 3, tzinfo=SHANGHAI),
            end_at=datetime(2026, 8, 3, 23, 59, tzinfo=SHANGHAI),
        ),
        policy=EvidencePolicy(
            capability=capability,
            min_independent_upstreams=2,
            required_upstream_ids=set(upstream_ids),
        ),
        source_results=[
            SourceResult(
                source_id=f"direct-{upstream_id}-kline",
                upstream_id=upstream_id,
                capability=capability,
                status=SourceStatus.SUCCESS_DATA,
                items=[raw],
                fetched_at=AS_OF.astimezone(UTC),
            )
            for upstream_id in upstream_ids
        ],
        items=[raw],
        assessment=_assessment(capability, upstream_ids),
        complete=True,
        collected_at=AS_OF.astimezone(UTC),
    )


def _final_daily_series() -> AdjustedKlineSeries:
    evidence_at = datetime(2026, 8, 4, 9, 1, tzinfo=SHANGHAI)
    return AdjustedKlineSeries(
        raw_snapshot_id=DAILY_SNAPSHOT_ID,
        factor_source_ids=(),
        factor_version="none",
        reference_date=date(2026, 8, 3),
        raw_snapshot_as_of=evidence_at,
        raw_completed_through=date(2026, 8, 3),
        as_of=evidence_at,
        bars=(
            AdjustedDailyBar(
                code="000001",
                market=MarketCode.SZSE,
                trade_date=date(2026, 8, 3),
                open=Decimal("10.00"),
                high=Decimal("10.30"),
                low=Decimal("9.90"),
                close=Decimal("10.20"),
                volume=Decimal("1000000"),
                amount=Decimal("10100000.00"),
            ),
        ),
    )


def _intraday_evidence() -> EvidenceEnvelope:
    final_bar = IntradayBar(
        code="000001",
        timestamp=datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI),
        open=10.20,
        high=10.25,
        low=10.19,
        close=10.24,
        volume=20_000,
        amount=204_500.0,
        state=IntradayBarState.FINAL,
    )
    provisional_bar = final_bar.model_copy(
        update={
            "timestamp": AS_OF,
            "close": 10.25,
            "high": 10.26,
            "state": IntradayBarState.PROVISIONAL,
        }
    )
    series = IntradaySourceSeries(
        code="000001",
        name="平安银行",
        checkpoints=[
            IntradayCheckpoint(
                code="000001",
                timestamp=final_bar.timestamp,
                close=final_bar.close,
                cumulative_volume=20_000,
                cumulative_amount=204_500.0,
                state=IntradayBarState.FINAL,
            )
        ],
        bars=[final_bar, provisional_bar],
        ohlc_supported=True,
    )
    capability = EvidenceCapability.INTRADAY
    upstream_ids = ("eastmoney", "tencent")
    return EvidenceEnvelope(
        request=EvidenceRequest(capability=capability, stock_code="000001"),
        policy=EvidencePolicy(
            capability=capability,
            min_independent_upstreams=2,
            required_upstream_ids=set(upstream_ids),
        ),
        source_results=[
            SourceResult(
                source_id=f"direct-{upstream_id}-intraday",
                upstream_id=upstream_id,
                capability=capability,
                status=SourceStatus.SUCCESS_DATA,
                items=[series],
                fetched_at=AS_OF.astimezone(UTC),
            )
            for upstream_id in upstream_ids
        ],
        items=[final_bar, provisional_bar],
        assessment=_assessment(capability, upstream_ids),
        complete=True,
        collected_at=AS_OF.astimezone(UTC),
    )


def _quote_evidence() -> EvidenceEnvelope:
    quote = StockQuote(
        code="000001",
        name="平安银行",
        price=10.25,
        change=0.05,
        change_pct=0.49,
        volume=1_200_000,
        amount=12_250_000.0,
        high=10.30,
        low=10.10,
        open_=10.20,
        prev_close=10.20,
        fetched_at=AS_OF,
    )
    capability = EvidenceCapability.REALTIME_QUOTE
    upstream_ids = ("eastmoney", "sina")
    return EvidenceEnvelope(
        request=EvidenceRequest(capability=capability, stock_code="000001"),
        policy=EvidencePolicy(
            capability=capability,
            min_independent_upstreams=2,
            required_upstream_ids=set(upstream_ids),
        ),
        source_results=[
            SourceResult(
                source_id=f"direct-{upstream_id}-quote",
                upstream_id=upstream_id,
                capability=capability,
                status=SourceStatus.SUCCESS_DATA,
                items=[quote],
                fetched_at=AS_OF.astimezone(UTC),
            )
            for upstream_id in upstream_ids
        ],
        items=[quote],
        assessment=_assessment(capability, upstream_ids),
        complete=True,
        collected_at=AS_OF.astimezone(UTC),
    )


def test_assembles_complete_runtime_evidence_without_promoting_open_minute() -> None:
    final_daily = _final_daily_series()

    result = assemble_complete_kline_business(
        symbol="000001",
        market=MarketCode.SZSE,
        as_of=AS_OF,
        trading_phase=TradingPhase.CONTINUOUS_AUCTION,
        final_daily_bars=final_daily,
        daily_snapshot_id=DAILY_SNAPSHOT_ID,
        daily_evidence=_daily_evidence(),
        intraday_evidence=_intraday_evidence(),
        quote_evidence=_quote_evidence(),
    )

    assert result.final_daily_bars == final_daily
    assert result.daily_upstream_ids == ("sina", "tencent")
    assert len(result.final_minute_bars) == 1
    assert result.final_minute_bars[0].timestamp == datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI)
    assert result.intraday_upstream_ids == ("eastmoney", "tencent")
    assert result.live_quote.price_basis == "raw"
    assert result.quote_upstream_ids == ("eastmoney", "sina")
    assert result.provisional_session_bar.state == "PROVISIONAL"
    assert result.provisional_session_bar.open == Decimal("10.2")
    assert result.provisional_session_bar.close == Decimal("10.25")
    assert result.provisional_session_bar.cumulative_volume == 1_200_000
    assert result.provisional_session_bar.upstream_ids == ("eastmoney", "sina")


@pytest.mark.parametrize("layer", ["daily", "intraday", "quote"])
def test_rejects_incomplete_layer_even_when_cached_items_remain(layer: str) -> None:
    evidence = {
        "daily": _daily_evidence(),
        "intraday": _intraday_evidence(),
        "quote": _quote_evidence(),
    }
    stale = evidence[layer]
    evidence[layer] = stale.model_copy(
        update={
            "complete": False,
            "assessment": stale.assessment.model_copy(update={"complete": False}),
        }
    )

    with pytest.raises(ValueError, match="complete runtime evidence"):
        assemble_complete_kline_business(
            symbol="000001",
            market=MarketCode.SZSE,
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            final_daily_bars=_final_daily_series(),
            daily_snapshot_id=DAILY_SNAPSHOT_ID,
            daily_evidence=evidence["daily"],
            intraday_evidence=evidence["intraday"],
            quote_evidence=evidence["quote"],
        )


@pytest.mark.parametrize("layer", ["daily", "intraday", "quote"])
def test_rejects_runtime_evidence_wired_to_wrong_capability(layer: str) -> None:
    evidence = {
        "daily": _daily_evidence(),
        "intraday": _intraday_evidence(),
        "quote": _quote_evidence(),
    }
    evidence[layer] = {
        "daily": _quote_evidence(),
        "intraday": _quote_evidence(),
        "quote": _intraday_evidence(),
    }[layer]

    with pytest.raises(ValueError, match="runtime evidence capability"):
        assemble_complete_kline_business(
            symbol="000001",
            market=MarketCode.SZSE,
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            final_daily_bars=_final_daily_series(),
            daily_snapshot_id=DAILY_SNAPSHOT_ID,
            daily_evidence=evidence["daily"],
            intraday_evidence=evidence["intraday"],
            quote_evidence=evidence["quote"],
        )


@pytest.mark.parametrize("layer", ["daily", "intraday", "quote"])
def test_rejects_evidence_requested_for_another_symbol(layer: str) -> None:
    evidence = {
        "daily": _daily_evidence(),
        "intraday": _intraday_evidence(),
        "quote": _quote_evidence(),
    }
    original = evidence[layer]
    evidence[layer] = original.model_copy(
        update={"request": original.request.model_copy(update={"stock_code": "600000"})}
    )

    with pytest.raises(ValueError, match="runtime evidence symbol"):
        assemble_complete_kline_business(
            symbol="000001",
            market=MarketCode.SZSE,
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            final_daily_bars=_final_daily_series(),
            daily_snapshot_id=DAILY_SNAPSHOT_ID,
            daily_evidence=evidence["daily"],
            intraday_evidence=evidence["intraday"],
            quote_evidence=evidence["quote"],
        )


def test_data_package_exports_complete_runtime_assembler() -> None:
    from src import data

    assert data.assemble_complete_kline_business is assemble_complete_kline_business


@pytest.mark.parametrize("cardinality", [0, 2])
def test_rejects_invalid_canonical_quote_cardinality(cardinality: int) -> None:
    quote_evidence = _quote_evidence()
    quote = quote_evidence.items[0]
    quote_evidence = quote_evidence.model_copy(update={"items": [quote] * cardinality})

    with pytest.raises(ValueError, match="exactly one canonical realtime quote"):
        assemble_complete_kline_business(
            symbol="000001",
            market=MarketCode.SZSE,
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            final_daily_bars=_final_daily_series(),
            daily_snapshot_id=DAILY_SNAPSHOT_ID,
            daily_evidence=_daily_evidence(),
            intraday_evidence=_intraday_evidence(),
            quote_evidence=quote_evidence,
        )


def test_rejects_adjusted_series_from_another_daily_snapshot() -> None:
    with pytest.raises(ValueError, match="daily snapshot lineage"):
        assemble_complete_kline_business(
            symbol="000001",
            market=MarketCode.SZSE,
            as_of=AS_OF,
            trading_phase=TradingPhase.CONTINUOUS_AUCTION,
            final_daily_bars=_final_daily_series(),
            daily_snapshot_id="raw:000001:other-snapshot",
            daily_evidence=_daily_evidence(),
            intraday_evidence=_intraday_evidence(),
            quote_evidence=_quote_evidence(),
        )

"""KR-3 four-layer market-data business envelope contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import TypeAdapter, ValidationError

from src.data import kline_business
from src.data.intraday import IntradayBar, IntradayBarState
from src.data.kline import MarketCode
from src.data.kline_adjustment import AdjustedDailyBar, AdjustedKlineSeries
from src.data.kline_business import KlineBusinessEnvelope
from src.data.models import StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")
AS_OF = datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI)


def _daily_series(trade_date: date = date(2026, 8, 3)) -> AdjustedKlineSeries:
    series_as_of = datetime(
        trade_date.year,
        trade_date.month,
        trade_date.day,
        10,
        0,
        tzinfo=SHANGHAI,
    )
    return AdjustedKlineSeries(
        raw_snapshot_id=f"raw:000001:{trade_date.isoformat()}",
        factor_source_ids=(),
        factor_version="none",
        reference_date=trade_date,
        raw_snapshot_as_of=series_as_of,
        raw_completed_through=trade_date,
        as_of=series_as_of,
        bars=(
            AdjustedDailyBar(
                code="000001",
                market=MarketCode.SZSE,
                trade_date=trade_date,
                open=Decimal("10.00"),
                high=Decimal("10.30"),
                low=Decimal("9.90"),
                close=Decimal("10.20"),
                volume=Decimal("1000000"),
                amount=Decimal("10100000.00"),
            ),
        ),
    )


def _closing_daily_series() -> AdjustedKlineSeries:
    closing_at = datetime(2026, 8, 4, 15, 5, tzinfo=SHANGHAI)
    return _daily_series(date(2026, 8, 4)).model_copy(
        update={"raw_snapshot_as_of": closing_at, "as_of": closing_at}
    )


def _final_minute(
    *,
    timestamp: datetime = datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI),
) -> IntradayBar:
    return IntradayBar(
        code="000001",
        timestamp=timestamp,
        open=10.20,
        high=10.25,
        low=10.19,
        close=10.24,
        volume=20_000,
        amount=204_500.0,
        state=IntradayBarState.FINAL,
    )


def _live_quote() -> StockQuote:
    return StockQuote(
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


def _envelope_kwargs() -> dict[str, Any]:
    return {
        "symbol": "000001",
        "market": MarketCode.SZSE,
        "as_of": AS_OF,
        "trading_phase": "continuous_auction",
        "final_daily_bars": _daily_series(),
        "daily_upstream_ids": ("sina", "tencent"),
        "final_minute_bars": (_final_minute(),),
        "intraday_upstream_ids": ("eastmoney", "tencent"),
        "live_quote": _live_quote(),
        "quote_upstream_ids": ("eastmoney", "sina"),
        "provisional_session_bar": {
            "code": "000001",
            "market": MarketCode.SZSE,
            "trading_date": date(2026, 8, 4),
            "as_of": AS_OF,
            "trading_phase": "continuous_auction",
            "open": Decimal("10.20"),
            "high": Decimal("10.30"),
            "low": Decimal("10.10"),
            "close": Decimal("10.25"),
            "cumulative_volume": 1_200_000,
            "cumulative_amount": Decimal("12250000.00"),
            "upstream_ids": ("eastmoney", "tencent"),
        },
    }


def _failure_kwargs() -> dict[str, Any]:
    return {
        "symbol": "000001",
        "market": MarketCode.SZSE,
        "as_of": AS_OF,
        "trading_phase": "continuous_auction",
        "error_codes": ("quote_stale",),
        "layer_diagnostics": (
            {
                "layer": "FINAL_DAILY",
                "complete": True,
                "upstream_ids": ("sina", "tencent"),
            },
            {
                "layer": "FINAL_MINUTE",
                "complete": True,
                "upstream_ids": ("eastmoney", "tencent"),
            },
            {
                "layer": "LIVE_QUOTE",
                "complete": False,
                "upstream_ids": ("eastmoney", "sina"),
                "error_code": "quote_stale",
                "error_message": "Realtime quote exceeded the freshness boundary",
            },
            {
                "layer": "PROVISIONAL",
                "complete": True,
                "upstream_ids": ("eastmoney", "tencent"),
            },
        ),
    }


def test_builds_complete_four_layer_envelope_without_merging_dynamic_daily_bar() -> None:
    envelope = KlineBusinessEnvelope(**_envelope_kwargs())

    assert envelope.complete is True
    assert envelope.final_daily_bars.reference_date == date(2026, 8, 3)
    assert envelope.final_minute_bars[0].state is IntradayBarState.FINAL
    assert envelope.live_quote.price == 10.25
    assert envelope.live_quote_price_basis == "raw"
    assert envelope.live_quote.price_basis == "raw"
    assert envelope.provisional_session_bar.state == "PROVISIONAL"
    assert envelope.provisional_session_bar.trading_date == date(2026, 8, 4)


@pytest.mark.parametrize("layer", ["minute", "quote"])
def test_business_market_facts_are_deeply_immutable(layer: str) -> None:
    envelope = KlineBusinessEnvelope(**_envelope_kwargs())

    with pytest.raises(ValidationError, match="frozen"):
        if layer == "minute":
            envelope.final_minute_bars[0].close = 99.99
        else:
            envelope.live_quote.price = 99.99


def test_success_envelope_rejects_unknown_or_misspelled_layers() -> None:
    payload = _envelope_kwargs()
    payload["final_daily_bar"] = payload["final_daily_bars"]

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        KlineBusinessEnvelope(**payload)


def test_rejects_provisional_session_date_inside_final_daily_series() -> None:
    payload = _envelope_kwargs()
    payload["final_daily_bars"] = _daily_series(date(2026, 8, 4))

    with pytest.raises(ValidationError, match="FINAL_DAILY must end before PROVISIONAL"):
        KlineBusinessEnvelope(**payload)


def test_rejects_provisional_minute_inside_final_minute_layer() -> None:
    payload = _envelope_kwargs()
    payload["final_minute_bars"] = (
        _final_minute().model_copy(update={"state": IntradayBarState.PROVISIONAL}),
    )

    with pytest.raises(ValidationError):
        KlineBusinessEnvelope(**payload)


def test_rejects_live_quote_for_another_instrument() -> None:
    payload = _envelope_kwargs()
    payload["live_quote"] = _live_quote().model_copy(update={"code": "600000"})

    with pytest.raises(ValidationError, match="live quote identity must match envelope"):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("layer", ["daily", "minute", "provisional"])
def test_rejects_market_layer_identity_mismatch(layer: str) -> None:
    payload = _envelope_kwargs()
    if layer == "daily":
        series = _daily_series()
        wrong_bar = series.bars[0].model_copy(update={"market": MarketCode.SSE})
        payload["final_daily_bars"] = series.model_copy(update={"bars": (wrong_bar,)})
    elif layer == "minute":
        payload["final_minute_bars"] = (_final_minute().model_copy(update={"code": "600000"}),)
    else:
        provisional = dict(payload["provisional_session_bar"])
        provisional["market"] = MarketCode.SSE
        payload["provisional_session_bar"] = provisional

    with pytest.raises(ValidationError, match="layer identity must match envelope"):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("target", ["envelope", "quote", "provisional"])
def test_rejects_missing_timezone_from_business_timestamps(target: str) -> None:
    payload = _envelope_kwargs()
    naive = datetime(2026, 8, 4, 10, 1)
    if target == "envelope":
        payload["as_of"] = naive
    elif target == "quote":
        payload["live_quote"] = _live_quote().model_copy(update={"fetched_at": naive})
    else:
        provisional = dict(payload["provisional_session_bar"])
        provisional["as_of"] = naive
        payload["provisional_session_bar"] = provisional

    with pytest.raises(ValidationError, match="timestamps must be timezone-aware"):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("target", ["daily", "minute", "quote", "provisional"])
def test_rejects_market_layer_newer_than_envelope_as_of(target: str) -> None:
    payload = _envelope_kwargs()
    future = datetime(2026, 8, 4, 10, 2, tzinfo=SHANGHAI)
    if target == "daily":
        payload["final_daily_bars"] = _daily_series().model_copy(update={"as_of": future})
    elif target == "minute":
        payload["final_minute_bars"] = (_final_minute().model_copy(update={"timestamp": future}),)
    elif target == "quote":
        payload["live_quote"] = _live_quote().model_copy(update={"fetched_at": future})
    else:
        provisional = dict(payload["provisional_session_bar"])
        provisional["as_of"] = future
        payload["provisional_session_bar"] = provisional

    with pytest.raises(ValidationError, match="layer timestamp cannot exceed envelope as_of"):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("violation", ["wrong_session", "duplicate", "unordered"])
def test_rejects_invalid_final_minute_timeline(violation: str) -> None:
    payload = _envelope_kwargs()
    earlier = _final_minute(timestamp=datetime(2026, 8, 4, 9, 59, tzinfo=SHANGHAI))
    latest = _final_minute()
    if violation == "wrong_session":
        payload["final_minute_bars"] = (
            _final_minute(timestamp=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI)),
        )
    elif violation == "duplicate":
        payload["final_minute_bars"] = (latest, latest)
    else:
        payload["final_minute_bars"] = (latest, earlier)

    with pytest.raises(
        ValidationError,
        match="FINAL_MINUTE timestamps must be unique, ordered, and in PROVISIONAL session",
    ):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("layer", ["daily", "minute", "quote", "provisional"])
def test_rejects_duplicate_upstream_identity_in_verified_layer(layer: str) -> None:
    payload = _envelope_kwargs()
    if layer == "provisional":
        provisional = dict(payload["provisional_session_bar"])
        provisional["upstream_ids"] = ("tencent", "tencent")
        payload["provisional_session_bar"] = provisional
    else:
        field = {
            "daily": "daily_upstream_ids",
            "minute": "intraday_upstream_ids",
            "quote": "quote_upstream_ids",
        }[layer]
        payload[field] = ("same-upstream", "same-upstream")

    with pytest.raises(ValidationError, match="requires two distinct upstreams"):
        KlineBusinessEnvelope(**payload)


def test_rejects_invalid_provisional_session_ohlc() -> None:
    payload = _envelope_kwargs()
    provisional = dict(payload["provisional_session_bar"])
    provisional["high"] = Decimal("10.20")
    provisional["close"] = Decimal("10.25")
    payload["provisional_session_bar"] = provisional

    with pytest.raises(ValidationError, match="provisional OHLC must stay within low/high"):
        KlineBusinessEnvelope(**payload)


@pytest.mark.parametrize("violation", ["trading_date", "trading_phase"])
def test_rejects_provisional_session_metadata_mismatch(violation: str) -> None:
    payload = _envelope_kwargs()
    provisional = dict(payload["provisional_session_bar"])
    if violation == "trading_date":
        provisional["trading_date"] = date(2026, 8, 3)
    else:
        provisional["trading_phase"] = "midday_break"
    payload["provisional_session_bar"] = provisional

    with pytest.raises(ValidationError, match="PROVISIONAL metadata must match envelope session"):
        KlineBusinessEnvelope(**payload)


def test_failure_result_exposes_diagnostics_without_partial_business_layers() -> None:
    failure = kline_business.KlineBusinessFailure(**_failure_kwargs())

    assert failure.complete is False
    assert failure.error_codes == ("quote_stale",)
    assert failure.layer_diagnostics[2].layer == "LIVE_QUOTE"
    assert not hasattr(failure, "live_quote")
    assert not hasattr(failure, "final_daily_bars")


def test_failure_result_requires_each_layer_diagnostic_exactly_once() -> None:
    payload = _failure_kwargs()
    payload["layer_diagnostics"] = (
        {
            "layer": "LIVE_QUOTE",
            "complete": False,
            "error_code": "quote_stale",
            "error_message": "Realtime quote exceeded the freshness boundary",
        },
    )

    with pytest.raises(ValidationError, match="failure must diagnose all four layers exactly once"):
        kline_business.KlineBusinessFailure(**payload)


@pytest.mark.parametrize("violation", ["wrong_error_codes", "missing_message", "all_complete"])
def test_failure_result_requires_consistent_incomplete_diagnostics(violation: str) -> None:
    payload = _failure_kwargs()
    diagnostics = [dict(item) for item in payload["layer_diagnostics"]]
    if violation == "wrong_error_codes":
        payload["error_codes"] = ("another_error",)
    elif violation == "missing_message":
        diagnostics[2]["error_message"] = None
    else:
        diagnostics[2]["complete"] = True
    payload["layer_diagnostics"] = tuple(diagnostics)

    with pytest.raises(
        ValidationError,
        match="failure diagnostics and error_codes must agree",
    ):
        kline_business.KlineBusinessFailure(**payload)


def test_complete_failure_diagnostic_requires_two_distinct_upstreams() -> None:
    payload = _failure_kwargs()
    diagnostics = [dict(item) for item in payload["layer_diagnostics"]]
    diagnostics[0]["upstream_ids"] = ("sina",)
    payload["layer_diagnostics"] = tuple(diagnostics)

    with pytest.raises(
        ValidationError,
        match="complete layer diagnostic requires two distinct upstreams",
    ):
        kline_business.KlineBusinessFailure(**payload)


def test_failure_result_rejects_naive_as_of() -> None:
    payload = _failure_kwargs()
    payload["as_of"] = datetime(2026, 8, 4, 10, 1)

    with pytest.raises(ValidationError, match="business timestamps must be timezone-aware"):
        kline_business.KlineBusinessFailure(**payload)


def test_result_discriminator_keeps_success_and_failure_shapes_separate() -> None:
    adapter = TypeAdapter(kline_business.KlineBusinessResult)

    success = adapter.validate_python(_envelope_kwargs() | {"complete": True})
    failure = adapter.validate_python(_failure_kwargs() | {"complete": False})

    assert isinstance(success, KlineBusinessEnvelope)
    assert isinstance(failure, kline_business.KlineBusinessFailure)


def test_promotes_verified_completed_daily_series_with_audit_lineage() -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    final_series = _closing_daily_series()
    promoted_at = datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI)

    promotion = kline_business.promote_provisional_session(
        provisional=provisional,
        final_daily_series=final_series,
        daily_upstream_ids=("sina", "tencent"),
        promoted_at=promoted_at,
    )

    assert promotion.state == "PROMOTED"
    assert promotion.trading_date == date(2026, 8, 4)
    assert promotion.promoted_at == promoted_at
    assert promotion.raw_snapshot_id == "raw:000001:2026-08-04"
    assert promotion.factor_version == "none"
    assert promotion.final_bar == final_series.bars[-1]
    assert len(promotion.promotion_id) == 64


@pytest.mark.parametrize("violation", ["date", "code", "market"])
def test_promotion_rejects_final_daily_for_another_session(violation: str) -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    final_series = (
        _daily_series(date(2026, 8, 3)) if violation == "date" else _closing_daily_series()
    )
    if violation in {"code", "market"}:
        update = {"code": "600000"} if violation == "code" else {"market": MarketCode.SSE}
        final_bar = final_series.bars[-1].model_copy(update=update)
        final_series = final_series.model_copy(update={"bars": (final_bar,)})

    with pytest.raises(ValueError, match="final daily series must close promoted session"):
        kline_business.promote_provisional_session(
            provisional=provisional,
            final_daily_series=final_series,
            daily_upstream_ids=("sina", "tencent"),
            promoted_at=datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI),
        )


@pytest.mark.parametrize(
    "violation",
    [
        "naive",
        "before_provisional",
        "before_final",
        "final_before_provisional",
        "raw_before_provisional",
    ],
)
def test_promotion_rejects_invalid_evidence_timeline(violation: str) -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    final_series = _closing_daily_series()
    promoted_at = datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI)
    if violation == "naive":
        promoted_at = datetime(2026, 8, 4, 15, 10)
    elif violation == "before_provisional":
        promoted_at = datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI)
    elif violation == "raw_before_provisional":
        final_series = final_series.model_copy(
            update={
                "raw_snapshot_as_of": datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI)
            }
        )
    else:
        final_series = (
            _daily_series(date(2026, 8, 4))
            if violation == "final_before_provisional"
            else final_series.model_copy(
                update={"as_of": datetime(2026, 8, 4, 15, 11, tzinfo=SHANGHAI)}
            )
        )

    with pytest.raises(
        ValueError,
        match="promotion requires timezone-aware evidence no newer than promoted_at",
    ):
        kline_business.promote_provisional_session(
            provisional=provisional,
            final_daily_series=final_series,
            daily_upstream_ids=("sina", "tencent"),
            promoted_at=promoted_at,
        )


def test_promotion_retry_returns_existing_audit_record_idempotently() -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    final_series = _closing_daily_series()
    first = kline_business.promote_provisional_session(
        provisional=provisional,
        final_daily_series=final_series,
        daily_upstream_ids=("sina", "tencent"),
        promoted_at=datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI),
    )

    retry = kline_business.promote_provisional_session(
        provisional=provisional,
        final_daily_series=final_series,
        daily_upstream_ids=("tencent", "sina"),
        promoted_at=datetime(2026, 8, 4, 15, 20, tzinfo=SHANGHAI),
        existing=first,
    )

    assert retry is first
    assert retry.promoted_at == datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI)


def test_promotion_conflict_never_overwrites_existing_audit_record() -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    first_series = _closing_daily_series()
    existing = kline_business.promote_provisional_session(
        provisional=provisional,
        final_daily_series=first_series,
        daily_upstream_ids=("sina", "tencent"),
        promoted_at=datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI),
    )
    conflicting_series = first_series.model_copy(
        update={"raw_snapshot_id": "raw:000001:2026-08-04:revised"}
    )

    with pytest.raises(
        kline_business.DailyPromotionConflictError,
        match="existing daily promotion conflicts with retry evidence",
    ):
        kline_business.promote_provisional_session(
            provisional=provisional,
            final_daily_series=conflicting_series,
            daily_upstream_ids=("sina", "tencent"),
            promoted_at=datetime(2026, 8, 4, 15, 20, tzinfo=SHANGHAI),
            existing=existing,
        )

    assert existing.raw_snapshot_id == "raw:000001:2026-08-04"


@pytest.mark.parametrize(
    "violation",
    ["upstreams", "timestamp", "identity", "content_hash"],
)
def test_promotion_record_rejects_invalid_direct_replay(violation: str) -> None:
    provisional = kline_business.ProvisionalSessionBar.model_validate(
        _envelope_kwargs()["provisional_session_bar"]
    )
    record = kline_business.promote_provisional_session(
        provisional=provisional,
        final_daily_series=_closing_daily_series(),
        daily_upstream_ids=("sina", "tencent"),
        promoted_at=datetime(2026, 8, 4, 15, 10, tzinfo=SHANGHAI),
    )
    payload = record.model_dump()
    if violation == "upstreams":
        payload["daily_upstream_ids"] = ("sina", "sina")
    elif violation == "timestamp":
        payload["promoted_at"] = datetime(2026, 8, 4, 15, 10)
    elif violation == "identity":
        final_bar = dict(payload["final_bar"])
        final_bar["code"] = "600000"
        payload["final_bar"] = final_bar
    else:
        final_bar = dict(payload["final_bar"])
        final_bar["close"] = Decimal("10.21")
        payload["final_bar"] = final_bar

    with pytest.raises(ValidationError):
        kline_business.DailyPromotionRecord.model_validate(payload)


def test_data_package_exposes_stable_kr3_business_contract() -> None:
    from src import data

    envelope = data.KlineBusinessEnvelope(**_envelope_kwargs())

    assert envelope.complete is True
    assert data.TradingPhase.CONTINUOUS_AUCTION == "continuous_auction"
    assert data.FinalMinuteBar is kline_business.FinalMinuteBar
    assert data.LiveRawQuote is kline_business.LiveRawQuote

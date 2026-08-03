"""KR-2B-2C verified corporate-action factor conversion tests."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

import src.data.kline_adjustment as adjustment
from src.data.kline import MarketCode, RawDailyBar
from src.data.kline_adjustment import (
    CumulativeQfqFactorPoint,
    OfficialCorporateActionDocument,
    OfficialCorporateActionEvent,
    QfqFactorSnapshot,
)


def _snapshot(
    *,
    older_divisor: str = "1.2500",
    newer_divisor: str = "1.0000",
    precision: str = "0.0001",
) -> QfqFactorSnapshot:
    return QfqFactorSnapshot(
        code="000001",
        market=MarketCode.SZSE,
        source_id="direct-sina-qfq-factor",
        upstream_id="sina",
        adapter_version="sina-qfq-factor-v1",
        collected_at=datetime(2026, 6, 12, 3, 0, tzinfo=UTC),
        response_hash="a" * 64,
        response_bytes=128,
        factor_version=f"sha256:{'a' * 64}",
        base_divisor=Decimal(older_divisor),
        base_precision=Decimal(precision),
        points=(
            CumulativeQfqFactorPoint(
                effective_date=date(2025, 1, 1),
                cumulative_divisor=Decimal(older_divisor),
                precision=Decimal(precision),
            ),
            CumulativeQfqFactorPoint(
                effective_date=date(2026, 6, 12),
                cumulative_divisor=Decimal(newer_divisor),
                precision=Decimal(precision),
            ),
        ),
    )


def _cash_event() -> OfficialCorporateActionEvent:
    return OfficialCorporateActionEvent(
        action_id="cninfo:000001:cash-2026",
        revision=1,
        code="000001",
        market=MarketCode.SZSE,
        record_date=date(2026, 6, 11),
        ex_date=date(2026, 6, 12),
        action_kind="cash_dividend",
        collected_at=datetime(2026, 6, 12, 2, 0, tzinfo=UTC),
        source_id="cninfo-corporate-action",
        upstream_id="cninfo",
        parser_version="cninfo-corporate-action-v3",
        documents=(
            OfficialCorporateActionDocument(
                external_id="cash-2026",
                title="2025年年度权益分派实施公告",
                published_at=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
                source_url="https://www.cninfo.com.cn/detail/cash-2026",
                attachment_url="https://static.cninfo.com.cn/cash-2026.pdf",
                content_hash="b" * 64,
            ),
        ),
        distribution_cash_per_share=Decimal("2.00"),
        adjustment_cash_per_share=Decimal("2.00"),
    )


def _share_event() -> OfficialCorporateActionEvent:
    values = _cash_event().model_dump()
    values.update(
        {
            "action_id": "cninfo:000001:share-2026",
            "action_kind": "share_change",
            "cash_dividend_per_share": None,
            "distribution_cash_per_share": None,
            "adjustment_cash_per_share": None,
            "share_ratio_numerator": 3,
            "share_ratio_denominator": 2,
        }
    )
    return OfficialCorporateActionEvent.model_validate(values)


def _rights_event() -> OfficialCorporateActionEvent:
    values = _cash_event().model_dump()
    values.update(
        {
            "action_id": "cninfo:000001:rights-2026",
            "action_kind": "rights_issue",
            "cash_dividend_per_share": None,
            "distribution_cash_per_share": None,
            "adjustment_cash_per_share": None,
            "rights_ratio_numerator": 1,
            "rights_ratio_denominator": 4,
            "rights_subscription_price": Decimal("5.00"),
        }
    )
    return OfficialCorporateActionEvent.model_validate(values)


def _record_date_bar() -> RawDailyBar:
    return RawDailyBar(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=date(2026, 6, 11),
        open=Decimal("10.00"),
        high=Decimal("10.00"),
        low=Decimal("10.00"),
        close=Decimal("10.00"),
        volume=1000,
        amount=Decimal("10000.00"),
        amount_precision=Decimal("0.01"),
    )


def test_cash_event_converts_exact_sina_transition_with_independent_lineage() -> None:
    converter = getattr(adjustment, "convert_verified_corporate_action_factors", None)
    assert callable(converter), "verified corporate-action conversion API is missing"

    factors = converter(
        _snapshot(),
        (_cash_event(),),
        (_record_date_bar(),),
    )

    assert len(factors) == 1
    factor = factors[0]
    assert factor.action_id == "cninfo:000001:cash-2026"
    assert factor.price_factor == Decimal("0.8")
    assert factor.volume_factor == Decimal("1")
    assert factor.known_at == datetime(2026, 6, 12, 3, 0, tzinfo=UTC)
    assert factor.factor_source_ids == ("direct-sina-qfq-factor",)
    assert factor.factor_upstream_ids == ("sina",)
    assert factor.verification_source_ids == ("cninfo-corporate-action",)
    assert factor.verification_upstream_ids == ("cninfo",)
    assert factor.revision == 1


def test_cash_event_rejects_sina_transition_that_conflicts_with_exchange_formula() -> None:
    event = _cash_event().model_copy(
        update={
            "cash_dividend_per_share": Decimal("1.00"),
            "distribution_cash_per_share": Decimal("1.00"),
            "adjustment_cash_per_share": Decimal("1.00"),
        }
    )

    with pytest.raises(ValueError, match="formula|conflict"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(),
            (event,),
            (_record_date_bar(),),
        )


def test_formula_match_respects_declared_cumulative_divisor_precision() -> None:
    factors = adjustment.convert_verified_corporate_action_factors(
        _snapshot(older_divisor="1.2501"),
        (_cash_event(),),
        (_record_date_bar(),),
    )

    assert factors[0].price_factor == Decimal(
        "0.79993600511959043276537876969842412606991440684745"
    )
    assert factors[0].price_factor_precision >= Decimal("0.0001")


def test_real_transition_tail_noise_is_verified_at_twelve_decimal_places() -> None:
    event = _cash_event().model_copy(
        update={
            "cash_dividend_per_share": Decimal("0.362"),
            "distribution_cash_per_share": Decimal("0.362"),
            "adjustment_cash_per_share": Decimal("0.362"),
        }
    )
    record_bar = _record_date_bar().model_copy(
        update={
            "open": Decimal("11.850"),
            "high": Decimal("11.850"),
            "low": Decimal("11.850"),
            "close": Decimal("11.850"),
        }
    )

    factors = adjustment.convert_verified_corporate_action_factors(
        _snapshot(
            older_divisor="1.0315111420613028",
            newer_divisor="1.0000000000000000",
            precision="0.0000000000000001",
        ),
        (event,),
        (record_bar,),
    )

    assert factors[0].price_factor == Decimal(
        "0.96945147679322877348855632152210502204443924489825"
    )
    assert factors[0].price_factor_precision == Decimal("0.000000000001")


def test_formula_difference_visible_at_twelve_decimal_places_is_rejected() -> None:
    event = _cash_event().model_copy(
        update={
            "cash_dividend_per_share": Decimal("0.362"),
            "distribution_cash_per_share": Decimal("0.362"),
            "adjustment_cash_per_share": Decimal("0.362"),
        }
    )
    record_bar = _record_date_bar().model_copy(
        update={
            "open": Decimal("11.850"),
            "high": Decimal("11.850"),
            "low": Decimal("11.850"),
            "close": Decimal("11.850"),
        }
    )

    with pytest.raises(ValueError, match="formula|conflict"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(
                older_divisor="1.0315111420626102",
                newer_divisor="1.0000000000000000",
                precision="0.0000000000000001",
            ),
            (event,),
            (record_bar,),
        )


def test_share_change_uses_exact_official_ratio_for_price_and_volume() -> None:
    factors = adjustment.convert_verified_corporate_action_factors(
        _snapshot(older_divisor="1.5000"),
        (_share_event(),),
        (_record_date_bar(),),
    )

    factor = factors[0]
    assert factor.price_factor == Decimal("0.66666666666666666666666666666666666666666666666667")
    assert factor.volume_factor == Decimal("1.5")
    assert (factor.share_ratio_numerator, factor.share_ratio_denominator) == (3, 2)


def test_rights_issue_adds_subscription_value_and_post_issue_share_ratio() -> None:
    factors = adjustment.convert_verified_corporate_action_factors(
        _snapshot(older_divisor="1.1111"),
        (_rights_event(),),
        (_record_date_bar(),),
    )

    factor = factors[0]
    assert factor.price_factor == Decimal("0.90000900009000090000900009000090000900009000090001")
    assert factor.volume_factor == Decimal("1.25")
    assert (factor.share_ratio_numerator, factor.share_ratio_denominator) == (5, 4)


def test_factor_version_changes_when_official_event_revision_changes() -> None:
    first = adjustment.convert_verified_corporate_action_factors(
        _snapshot(),
        (_cash_event(),),
        (_record_date_bar(),),
    )[0]
    corrected_event = _cash_event().model_copy(update={"revision": 2})
    corrected = adjustment.convert_verified_corporate_action_factors(
        _snapshot(),
        (corrected_event,),
        (_record_date_bar(),),
    )[0]

    assert first.factor_version != corrected.factor_version
    assert first.factor_version.startswith("sha256:")
    assert corrected.factor_version.startswith("sha256:")


def test_historical_snapshot_transitions_outside_requested_events_do_not_block() -> None:
    snapshot = QfqFactorSnapshot(
        code="000001",
        market=MarketCode.SZSE,
        source_id="direct-sina-qfq-factor",
        upstream_id="sina",
        adapter_version="sina-qfq-factor-v1",
        collected_at=datetime(2026, 6, 12, 3, 0, tzinfo=UTC),
        response_hash="c" * 64,
        response_bytes=192,
        factor_version=f"sha256:{'c' * 64}",
        base_divisor=Decimal("2.0000"),
        base_precision=Decimal("0.0001"),
        points=(
            CumulativeQfqFactorPoint(
                effective_date=date(2025, 1, 1),
                cumulative_divisor=Decimal("2.0000"),
                precision=Decimal("0.0001"),
            ),
            CumulativeQfqFactorPoint(
                effective_date=date(2025, 6, 1),
                cumulative_divisor=Decimal("1.2500"),
                precision=Decimal("0.0001"),
            ),
            CumulativeQfqFactorPoint(
                effective_date=date(2026, 6, 12),
                cumulative_divisor=Decimal("1.0000"),
                precision=Decimal("0.0001"),
            ),
        ),
    )

    factors = adjustment.convert_verified_corporate_action_factors(
        snapshot,
        (_cash_event(),),
        (_record_date_bar(),),
    )

    assert [factor.ex_date for factor in factors] == [date(2026, 6, 12)]


@pytest.mark.parametrize("mismatched_input", ["event", "raw"])
def test_factor_conversion_rejects_instrument_mismatch(mismatched_input: str) -> None:
    event = _cash_event()
    raw_bar = _record_date_bar()
    if mismatched_input == "event":
        event = OfficialCorporateActionEvent.model_validate(
            {
                **event.model_dump(),
                "action_id": "cninfo:600000:cash-2026",
                "code": "600000",
                "market": MarketCode.SSE,
            }
        )
    else:
        raw_bar = RawDailyBar.model_validate(
            {
                **raw_bar.model_dump(),
                "code": "600000",
                "market": MarketCode.SSE,
            }
        )

    with pytest.raises(ValueError, match="instrument|code|market"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(),
            (event,),
            (raw_bar,),
        )


def test_factor_conversion_requires_record_date_raw_close() -> None:
    with pytest.raises(ValueError, match="record.date|RAW|close"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(),
            (_cash_event(),),
            (),
        )


def test_factor_conversion_rejects_duplicate_raw_trade_date() -> None:
    conflicting_bar = RawDailyBar.model_validate(
        {
            **_record_date_bar().model_dump(),
            "open": Decimal("11.00"),
            "high": Decimal("11.00"),
            "low": Decimal("11.00"),
            "close": Decimal("11.00"),
        }
    )

    with pytest.raises(ValueError, match="duplicate.*RAW|RAW.*duplicate"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(),
            (_cash_event(),),
            (_record_date_bar(), conflicting_bar),
        )


def test_factor_conversion_rejects_zero_record_date_close() -> None:
    zero_bar = RawDailyBar.model_validate(
        {
            **_record_date_bar().model_dump(),
            "open": Decimal("0.00"),
            "high": Decimal("0.00"),
            "low": Decimal("0.00"),
            "close": Decimal("0.00"),
        }
    )

    with pytest.raises(ValueError, match="positive|zero|close"):
        adjustment.convert_verified_corporate_action_factors(
            _snapshot(),
            (_cash_event(),),
            (zero_bar,),
        )

"""KR-2 versioned corporate-action factors and point-in-time adjustment."""

from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from src.data.kline import MarketCode, RawDailyBar
from src.data.kline_adjustment import (
    ActionKind,
    AdjustedDailyBar,
    AdjustedKlineSeries,
    CorporateActionFactor,
)
from src.data.kline_adjustment import (
    adjust_qfq_as_of as _adjust_qfq_as_of,
)

AS_OF = datetime(2026, 7, 30, 8, 0, tzinfo=UTC)


def _raw_bar(
    trade_date: date,
    *,
    close: str,
    volume: int,
    amount: str = "10000.00",
) -> RawDailyBar:
    close_price = Decimal(close)
    return RawDailyBar(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=trade_date,
        open=close_price,
        high=close_price,
        low=close_price,
        close=close_price,
        volume=volume,
        amount=Decimal(amount),
        amount_precision=Decimal("0.01"),
    )


def _factor(
    *,
    action_id: str,
    ex_date: date,
    action_kind: ActionKind,
    price_factor: str,
    volume_factor: str,
    known_at: datetime = datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
    factor_version: str = "v1",
    revision: int = 1,
    share_ratio_numerator: int | None = None,
    share_ratio_denominator: int | None = None,
) -> CorporateActionFactor:
    return CorporateActionFactor(
        action_id=action_id,
        code="000001",
        market=MarketCode.SZSE,
        ex_date=ex_date,
        action_kind=action_kind,
        known_at=known_at,
        price_factor=Decimal(price_factor),
        volume_factor=Decimal(volume_factor),
        price_factor_precision=Decimal("0.00000001"),
        volume_factor_precision=Decimal("0.00000001"),
        share_ratio_numerator=share_ratio_numerator,
        share_ratio_denominator=share_ratio_denominator,
        factor_source_ids=("factor-adapter",),
        factor_upstream_ids=("factor-upstream",),
        verification_source_ids=("official-event-adapter",),
        verification_upstream_ids=("official-event-upstream",),
        factor_version=factor_version,
        revision=revision,
    )


def adjust_qfq_as_of(
    raw_bars: tuple[RawDailyBar, ...],
    factors: tuple[CorporateActionFactor, ...],
    *,
    raw_snapshot_as_of: datetime,
    as_of: datetime,
    raw_completed_through: date | None = None,
) -> AdjustedKlineSeries:
    return _adjust_qfq_as_of(
        raw_bars,
        factors,
        raw_snapshot_id="snapshot:test",
        raw_snapshot_as_of=raw_snapshot_as_of,
        raw_completed_through=raw_completed_through or max(
            bar.trade_date for bar in raw_bars
        ),
        as_of=as_of,
    )


def test_qfq_without_actions_preserves_raw_values_but_marks_derived_basis() -> None:
    raw = _raw_bar(date(2026, 7, 29), close="10.00", volume=1000)

    result = adjust_qfq_as_of(
        (raw,),
        (),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert result.adjustment_mode == "qfq"
    assert result.reference_date == date(2026, 7, 29)
    assert result.as_of == AS_OF
    assert result.factor_source_ids == ()
    assert result.factor_version == "none"
    assert len(result.bars) == 1
    adjusted = result.bars[0]
    assert adjusted.price_basis == "adjusted_qfq_asof"
    assert adjusted.volume_basis == "adjusted_qfq_asof"
    assert adjusted.amount_basis == "raw"
    assert adjusted.open == Decimal("10.00")
    assert adjusted.high == Decimal("10.00")
    assert adjusted.low == Decimal("10.00")
    assert adjusted.close == Decimal("10.00")
    assert adjusted.volume == Decimal("1000")
    assert adjusted.amount == Decimal("10000.00")


def test_cash_dividend_adjusts_only_pre_ex_prices_and_keeps_raw_amount() -> None:
    factor = CorporateActionFactor(
        action_id="000001-20260729-cash",
        code="000001",
        market=MarketCode.SZSE,
        ex_date=date(2026, 7, 29),
        action_kind="cash_dividend",
        known_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
        price_factor=Decimal("0.95"),
        volume_factor=Decimal("1"),
        price_factor_precision=Decimal("0.00000001"),
        volume_factor_precision=Decimal("0.00000001"),
        factor_source_ids=("factor-adapter",),
        factor_upstream_ids=("factor-upstream",),
        verification_source_ids=("official-event-adapter",),
        verification_upstream_ids=("official-event-upstream",),
        factor_version="cash-v1",
        revision=1,
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="9.50", volume=1100),
    )

    result = adjust_qfq_as_of(
        raw,
        (factor,),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert result.factor_source_ids == ("factor-adapter",)
    assert result.factor_version != "none"
    assert result.bars[0].close == Decimal("9.5000")
    assert result.bars[0].volume == Decimal("1000")
    assert result.bars[0].amount == Decimal("10000.00")
    assert result.bars[1].close == Decimal("9.50")
    assert result.bars[1].volume == Decimal("1100")


def test_share_change_adjusts_pre_ex_volume_in_the_opposite_direction() -> None:
    factor = _factor(
        action_id="000001-20260729-share-change",
        ex_date=date(2026, 7, 29),
        action_kind="share_change",
        price_factor="0.5",
        volume_factor="2",
        share_ratio_numerator=2,
        share_ratio_denominator=1,
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="5.00", volume=2200),
    )

    result = adjust_qfq_as_of(
        raw,
        (factor,),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert result.bars[0].close == Decimal("5.000")
    assert result.bars[0].volume == Decimal("2000")
    assert result.bars[0].amount == Decimal("10000.00")
    assert result.bars[1].volume == Decimal("2200")


def test_as_of_uses_latest_factor_revision_known_at_that_time() -> None:
    original = _factor(
        action_id="000001-20260729-revised",
        ex_date=date(2026, 7, 29),
        action_kind="composite",
        price_factor="0.9",
        volume_factor="1.1",
        factor_version="v1",
        revision=1,
        share_ratio_numerator=11,
        share_ratio_denominator=10,
    )
    revision = _factor(
        action_id="000001-20260729-revised",
        ex_date=date(2026, 7, 29),
        action_kind="composite",
        price_factor="0.8",
        volume_factor="1.2",
        known_at=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
        factor_version="v2",
        revision=2,
        share_ratio_numerator=6,
        share_ratio_denominator=5,
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="9.00", volume=1100),
    )

    before_revision = adjust_qfq_as_of(
        raw,
        (revision, original),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )
    after_revision = adjust_qfq_as_of(
        raw,
        (original, revision),
        raw_snapshot_as_of=AS_OF,
        as_of=datetime(2026, 8, 2, 8, 0, tzinfo=UTC),
    )

    assert before_revision.bars[0].close == Decimal("9.000")
    assert before_revision.bars[0].volume == Decimal("1100.0")
    assert after_revision.bars[0].close == Decimal("8.000")
    assert after_revision.bars[0].volume == Decimal("1200.0")
    assert before_revision.factor_version != after_revision.factor_version


def test_factor_and_event_verification_must_use_independent_upstreams() -> None:
    with pytest.raises(ValueError, match="independent upstreams"):
        CorporateActionFactor(
            action_id="000001-20260729-conflicted-source",
            code="000001",
            market=MarketCode.SZSE,
            ex_date=date(2026, 7, 29),
            action_kind="cash_dividend",
            known_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            price_factor=Decimal("0.95"),
            volume_factor=Decimal("1"),
            price_factor_precision=Decimal("0.00000001"),
            volume_factor_precision=Decimal("0.00000001"),
            factor_source_ids=("factor-adapter",),
            factor_upstream_ids=("same-upstream",),
            verification_source_ids=("event-adapter",),
            verification_upstream_ids=("same-upstream",),
            factor_version="v1",
            revision=1,
        )


def test_cash_dividend_factor_cannot_change_volume() -> None:
    with pytest.raises(ValueError, match="cash dividend must preserve RAW volume"):
        _factor(
            action_id="000001-20260729-invalid-cash-volume",
            ex_date=date(2026, 7, 29),
            action_kind="cash_dividend",
            price_factor="0.95",
            volume_factor="1.05",
        )


@pytest.mark.parametrize("action_kind", ["share_change", "split", "reverse_split"])
def test_share_count_factor_must_match_exact_share_ratio(
    action_kind: ActionKind,
) -> None:
    with pytest.raises(ValueError, match="volume factor conflicts"):
        _factor(
            action_id=f"000001-20260729-invalid-{action_kind}",
            ex_date=date(2026, 7, 29),
            action_kind=action_kind,
            price_factor="0.5",
            volume_factor="0.5",
            share_ratio_numerator=2,
            share_ratio_denominator=1,
        )


def test_three_for_one_split_accepts_rounded_price_factor() -> None:
    factor = _factor(
        action_id="000001-20260729-three-for-one",
        ex_date=date(2026, 7, 29),
        action_kind="split",
        price_factor="0.33333333",
        volume_factor="3",
        share_ratio_numerator=3,
        share_ratio_denominator=1,
    )

    assert factor.price_factor == Decimal("0.33333333")
    assert factor.volume_factor == Decimal("3")


def test_share_count_factor_rejects_grossly_wrong_opposite_volume() -> None:
    with pytest.raises(ValueError, match="volume factor conflicts"):
        _factor(
            action_id="000001-20260729-wrong-volume",
            ex_date=date(2026, 7, 29),
            action_kind="share_change",
            price_factor="0.5",
            volume_factor="1.01",
            share_ratio_numerator=2,
            share_ratio_denominator=1,
        )


def test_factor_provenance_rejects_blank_identifiers() -> None:
    with pytest.raises(ValueError, match="non-blank"):
        CorporateActionFactor(
            action_id="000001-20260729-blank-source",
            code="000001",
            market=MarketCode.SZSE,
            ex_date=date(2026, 7, 29),
            action_kind="cash_dividend",
            known_at=datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
            price_factor=Decimal("0.95"),
            volume_factor=Decimal("1"),
            price_factor_precision=Decimal("0.00000001"),
            volume_factor_precision=Decimal("0.00000001"),
            factor_source_ids=(" ",),
            factor_upstream_ids=("factor-upstream",),
            verification_source_ids=("event-adapter",),
            verification_upstream_ids=("event-upstream",),
            factor_version="v1",
            revision=1,
        )


def test_factor_identity_is_normalized_and_evidence_is_immutable() -> None:
    factor = _factor(
        action_id=" 000001-20260729-normalized ",
        ex_date=date(2026, 7, 29),
        action_kind="cash_dividend",
        price_factor="0.95",
        volume_factor="1",
        factor_version=" provider-v1 ",
    )

    assert factor.action_id == "000001-20260729-normalized"
    assert factor.factor_version == "provider-v1"
    with pytest.raises(ValidationError, match="frozen"):
        factor.volume_factor = Decimal("0.5")


def test_conflicting_values_for_the_same_factor_revision_fail_closed() -> None:
    first = _factor(
        action_id="000001-20260729-conflict",
        ex_date=date(2026, 7, 29),
        action_kind="composite",
        price_factor="0.9",
        volume_factor="1.1",
        factor_version="same-revision-a",
        share_ratio_numerator=11,
        share_ratio_denominator=10,
    )
    second = _factor(
        action_id="000001-20260729-conflict",
        ex_date=date(2026, 7, 29),
        action_kind="composite",
        price_factor="0.8",
        volume_factor="1.2",
        factor_version="same-revision-b",
        share_ratio_numerator=6,
        share_ratio_denominator=5,
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="9.00", volume=1100),
    )

    with pytest.raises(ValueError, match="conflicting factor revision"):
        adjust_qfq_as_of(
            raw,
            (first, second),
            raw_snapshot_as_of=AS_OF,
            as_of=AS_OF,
        )


def test_same_factor_revision_with_different_lineage_fails_independent_of_order() -> None:
    first = _factor(
        action_id="000001-20260729-lineage-conflict",
        ex_date=date(2026, 7, 29),
        action_kind="cash_dividend",
        price_factor="0.95",
        volume_factor="1",
    )
    changed_lineage = CorporateActionFactor.model_validate(
        {
            **first.model_dump(),
            "factor_source_ids": ("other-adapter",),
            "factor_upstream_ids": ("other-upstream",),
        }
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="9.50", volume=1100),
    )

    for factors in ((first, changed_lineage), (changed_lineage, first)):
        with pytest.raises(ValueError, match="conflicting factor revision"):
            adjust_qfq_as_of(
                raw,
                factors,
                raw_snapshot_as_of=AS_OF,
                as_of=AS_OF,
            )


def test_rights_issue_crossing_suspension_gap_does_not_fabricate_a_bar() -> None:
    factor = _factor(
        action_id="000001-20260729-rights",
        ex_date=date(2026, 7, 29),
        action_kind="rights_issue",
        price_factor="0.92",
        volume_factor="1.08",
        share_ratio_numerator=27,
        share_ratio_denominator=25,
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 30), close="9.20", volume=1200),
    )

    result = adjust_qfq_as_of(
        raw,
        (factor,),
        raw_snapshot_as_of=datetime(2026, 7, 31, 8, 0, tzinfo=UTC),
        as_of=datetime(2026, 7, 31, 8, 0, tzinfo=UTC),
    )

    assert [bar.trade_date for bar in result.bars] == [
        date(2026, 7, 28),
        date(2026, 7, 30),
    ]
    assert result.bars[0].close == Decimal("9.2000")
    assert result.bars[0].volume == Decimal("1080.00")
    assert result.bars[1].close == Decimal("9.20")


def test_rights_issue_volume_must_match_exact_post_issue_share_ratio() -> None:
    with pytest.raises(ValueError, match="volume factor conflicts"):
        _factor(
            action_id="000001-20260729-rights-wrong-volume",
            ex_date=date(2026, 7, 29),
            action_kind="rights_issue",
            price_factor="0.92",
            volume_factor="99",
            share_ratio_numerator=27,
            share_ratio_denominator=25,
        )


def test_factor_order_does_not_change_series_or_combined_version() -> None:
    first = _factor(
        action_id="000001-20260728-cash",
        ex_date=date(2026, 7, 28),
        action_kind="cash_dividend",
        price_factor="0.98",
        volume_factor="1",
        factor_version="cash-v1",
    )
    second = _factor(
        action_id="000001-20260729-share",
        ex_date=date(2026, 7, 29),
        action_kind="share_change",
        price_factor="0.5",
        volume_factor="2",
        factor_version="share-v1",
        share_ratio_numerator=2,
        share_ratio_denominator=1,
    )
    raw = (
        _raw_bar(date(2026, 7, 27), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="4.90", volume=2100),
    )

    forward = adjust_qfq_as_of(
        raw,
        (first, second),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )
    reversed_order = adjust_qfq_as_of(
        raw,
        (second, first),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert forward == reversed_order
    assert forward.factor_version.startswith("sha256:")


def test_combined_version_hashes_factor_content_not_only_provider_version() -> None:
    first = _factor(
        action_id="000001-20260729-content-hash",
        ex_date=date(2026, 7, 29),
        action_kind="composite",
        price_factor="0.9",
        volume_factor="1.1",
        factor_version="provider-v1",
        share_ratio_numerator=11,
        share_ratio_denominator=10,
    )
    changed_value = first.model_copy(
        update={
            "price_factor": Decimal("0.8"),
        }
    )
    raw = (
        _raw_bar(date(2026, 7, 28), close="10.00", volume=1000),
        _raw_bar(date(2026, 7, 29), close="9.00", volume=1100),
    )

    original = adjust_qfq_as_of(
        raw,
        (first,),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )
    changed = adjust_qfq_as_of(
        raw,
        (changed_value,),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert original.factor_version != changed.factor_version


def test_adjusted_values_do_not_depend_on_callers_decimal_context() -> None:
    factors = tuple(
        _factor(
            action_id=f"000001-202607{day}-decimal-{day}",
            ex_date=date(2026, 7, day),
            action_kind="composite",
            price_factor=f"0.{day}123456789",
            volume_factor="1",
        )
        for day in (27, 28, 29)
    )
    raw = (
        _raw_bar(date(2026, 7, 26), close="10.12", volume=123456789),
        _raw_bar(date(2026, 7, 29), close="9.00", volume=1100),
    )

    with localcontext() as context:
        context.prec = 10
        low_context = adjust_qfq_as_of(
            raw,
            factors,
            raw_snapshot_as_of=AS_OF,
            as_of=AS_OF,
        )
    with localcontext() as context:
        context.prec = 50
        high_context = adjust_qfq_as_of(
            raw,
            factors,
            raw_snapshot_as_of=AS_OF,
            as_of=AS_OF,
        )

    assert low_context == high_context


def test_factor_json_round_trip_preserves_versioned_provenance() -> None:
    factor = _factor(
        action_id="000001-20260729-round-trip",
        ex_date=date(2026, 7, 29),
        action_kind="split",
        price_factor="0.5",
        volume_factor="2",
        share_ratio_numerator=2,
        share_ratio_denominator=1,
    )

    restored = CorporateActionFactor.model_validate_json(factor.model_dump_json())

    assert restored == factor
    assert restored.factor_upstream_ids == ("factor-upstream",)
    assert restored.verification_upstream_ids == ("official-event-upstream",)


def test_adjustment_rejects_naive_as_of_and_future_raw_bars() -> None:
    raw = _raw_bar(date(2026, 7, 30), close="10.00", volume=1000)

    with pytest.raises(ValueError, match="timezone-aware"):
        adjust_qfq_as_of(
            (raw,),
            (),
            raw_snapshot_as_of=AS_OF,
            as_of=datetime(2026, 7, 30, 8, 0),
        )
    with pytest.raises(ValueError, match="newer than as_of"):
        adjust_qfq_as_of(
            (raw,),
            (),
            raw_snapshot_as_of=AS_OF,
            as_of=datetime(2026, 7, 29, 8, 0, tzinfo=UTC),
        )


def test_adjustment_rejects_future_snapshot_and_intraday_final_bar() -> None:
    previous_day = _raw_bar(date(2026, 7, 29), close="10.00", volume=1000)
    same_day = _raw_bar(date(2026, 7, 30), close="10.00", volume=1000)

    with pytest.raises(ValueError, match="snapshot newer than as_of"):
        adjust_qfq_as_of(
            (previous_day,),
            (),
            raw_snapshot_as_of=datetime(2026, 7, 31, 8, 0, tzinfo=UTC),
            as_of=AS_OF,
        )
    with pytest.raises(ValueError, match="exceed the snapshot completion proof"):
        adjust_qfq_as_of(
            (same_day,),
            (),
            raw_snapshot_as_of=datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
            raw_completed_through=date(2026, 7, 29),
            as_of=datetime(2026, 7, 30, 6, 0, tzinfo=UTC),
        )


def test_adjustment_allows_same_day_bar_with_explicit_completion_proof() -> None:
    same_day = _raw_bar(date(2026, 7, 30), close="10.00", volume=1000)

    result = adjust_qfq_as_of(
        (same_day,),
        (),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )

    assert result.reference_date == date(2026, 7, 30)


def test_adjustment_rejects_bar_that_postdates_raw_snapshot() -> None:
    bar = _raw_bar(date(2026, 7, 29), close="10.00", volume=1000)

    with pytest.raises(ValueError, match="exceed the snapshot completion proof"):
        adjust_qfq_as_of(
            (bar,),
            (),
            raw_snapshot_as_of=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
            raw_completed_through=date(2026, 7, 1),
            as_of=AS_OF,
        )


def test_adjusted_models_reject_invalid_ohlc_and_series_shape() -> None:
    with pytest.raises(ValueError, match="high must be greater"):
        AdjustedDailyBar(
            code="000001",
            market=MarketCode.SZSE,
            trade_date=date(2026, 7, 29),
            open=Decimal("9"),
            high=Decimal("8"),
            low=Decimal("9"),
            close=Decimal("9"),
            volume=Decimal("1000"),
        )

    raw = _raw_bar(date(2026, 7, 29), close="10.00", volume=1000)
    valid = adjust_qfq_as_of(
        (raw,),
        (),
        raw_snapshot_as_of=AS_OF,
        as_of=AS_OF,
    )
    with pytest.raises(ValueError, match="requires bars"):
        AdjustedKlineSeries.model_validate(
            {
                **valid.model_dump(),
                "bars": (),
            }
        )
    with pytest.raises(ValueError, match="completion proof postdates"):
        AdjustedKlineSeries.model_validate(
            {
                **valid.model_dump(),
                "raw_completed_through": date(2026, 7, 31),
            }
        )
    with pytest.raises(ValueError, match="identities must be non-blank"):
        AdjustedKlineSeries.model_validate(
            {
                **valid.model_dump(),
                "factor_version": " ",
            }
        )
    with pytest.raises(ValueError, match="must appear together"):
        AdjustedKlineSeries.model_validate(
            {
                **valid.model_dump(),
                "factor_version": "sha256:orphaned",
            }
        )

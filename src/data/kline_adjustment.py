"""KR-2 source-agnostic corporate-action factors and point-in-time QFQ."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
from math import prod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.data.kline import MarketCode, RawDailyBar, market_code_for

ActionKind = Literal[
    "cash_dividend",
    "share_change",
    "rights_issue",
    "split",
    "reverse_split",
    "composite",
]

A_SHARE_SECURITY_CODE_PATTERN = re.compile(
    r"(?:00[0-3]\d{3}|30[01]\d{3}|60[0135]\d{3}|68[89]\d{3}|[48]\d{5}|92\d{4})"
)


def is_supported_a_share_code(code: str) -> bool:
    """Return whether a code belongs to an explicitly supported A-share board."""

    return A_SHARE_SECURITY_CODE_PATTERN.fullmatch(code) is not None


def _decimal_precision(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("decimal precision requires a finite value")
    return Decimal(1).scaleb(exponent)


class AdjustedDailyBar(BaseModel):
    """One derived qfq daily bar that must never masquerade as a RAW price."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    trade_date: date
    period: Literal["1d"] = "1d"
    currency: Literal["CNY"] = "CNY"
    price_basis: Literal["adjusted_qfq_asof"] = "adjusted_qfq_asof"
    volume_basis: Literal["adjusted_qfq_asof"] = "adjusted_qfq_asof"
    amount_basis: Literal["raw"] = "raw"
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    amount: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "AdjustedDailyBar":
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within the daily low/high range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within the daily low/high range")
        return self


class CorporateActionFactor(BaseModel):
    """One versioned factor backed by an independent corporate-action source."""

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    ex_date: date
    action_kind: ActionKind
    known_at: datetime
    price_factor: Decimal = Field(gt=0)
    volume_factor: Decimal = Field(gt=0)
    price_factor_precision: Decimal = Field(gt=0)
    volume_factor_precision: Decimal = Field(gt=0)
    share_ratio_numerator: int | None = Field(default=None, gt=0)
    share_ratio_denominator: int | None = Field(default=None, gt=0)
    factor_source_ids: tuple[str, ...] = Field(min_length=1)
    factor_upstream_ids: tuple[str, ...] = Field(min_length=1)
    verification_source_ids: tuple[str, ...] = Field(min_length=1)
    verification_upstream_ids: tuple[str, ...] = Field(min_length=1)
    factor_version: str = Field(min_length=1)
    revision: int = Field(ge=1)

    @field_validator("action_id", "factor_version")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("factor identities must be non-blank")
        return normalized

    @field_validator("known_at")
    @classmethod
    def validate_known_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("known_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator(
        "factor_source_ids",
        "factor_upstream_ids",
        "verification_source_ids",
        "verification_upstream_ids",
    )
    @classmethod
    def validate_provenance(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("factor provenance identifiers must be non-blank")
        return tuple(sorted({value.strip() for value in values}))

    @model_validator(mode="after")
    def validate_factor(self) -> "CorporateActionFactor":
        if set(self.factor_upstream_ids) & set(self.verification_upstream_ids):
            raise ValueError(
                "factor and corporate-action verification require independent upstreams"
            )
        if self.action_kind == "cash_dividend" and self.volume_factor != Decimal("1"):
            raise ValueError("cash dividend must preserve RAW volume")
        has_share_ratio = (
            self.share_ratio_numerator is not None
            and self.share_ratio_denominator is not None
        )
        if (self.share_ratio_numerator is None) != (
            self.share_ratio_denominator is None
        ):
            raise ValueError("share ratio numerator and denominator must appear together")
        requires_share_ratio = self.action_kind in {
            "share_change",
            "split",
            "reverse_split",
            "rights_issue",
        } or (self.action_kind == "composite" and self.volume_factor != Decimal("1"))
        if requires_share_ratio and not has_share_ratio:
            raise ValueError("share-count actions require an exact share ratio")
        if self.action_kind == "cash_dividend" and has_share_ratio:
            raise ValueError("cash dividend cannot carry a share ratio")
        if has_share_ratio:
            assert self.share_ratio_numerator is not None
            assert self.share_ratio_denominator is not None
            expected_volume = Fraction(
                self.share_ratio_numerator,
                self.share_ratio_denominator,
            )
            volume_error = abs(Fraction(self.volume_factor) - expected_volume)
            if volume_error > Fraction(self.volume_factor_precision) / 2:
                raise ValueError(
                    "volume factor conflicts with the exact share ratio"
                )
            if self.action_kind in {"share_change", "split", "reverse_split"}:
                expected_price = 1 / expected_volume
                price_error = abs(Fraction(self.price_factor) - expected_price)
                if price_error > Fraction(self.price_factor_precision) / 2:
                    raise ValueError(
                        "price factor conflicts with the exact share ratio"
                    )
        return self


class CumulativeQfqFactorPoint(BaseModel):
    """One dated divisor from a versioned upstream QFQ-factor snapshot."""

    model_config = ConfigDict(frozen=True)

    effective_date: date
    cumulative_divisor: Decimal = Field(gt=0)
    precision: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_precision(self) -> "CumulativeQfqFactorPoint":
        if self.precision != _decimal_precision(self.cumulative_divisor):
            raise ValueError(
                "precision must match the cumulative divisor decimal exponent"
            )
        return self


class QfqFactorSnapshot(BaseModel):
    """An immutable, content-addressed cumulative QFQ-factor response."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    collected_at: datetime
    response_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_bytes: int = Field(gt=0)
    factor_version: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    base_divisor: Decimal = Field(gt=0)
    base_precision: Decimal = Field(gt=0)
    points: tuple[CumulativeQfqFactorPoint, ...]

    @field_validator("source_id", "upstream_id", "adapter_version")
    @classmethod
    def validate_snapshot_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("QFQ snapshot identities must be non-blank")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not is_supported_a_share_code(value):
            raise ValueError("code must be an explicitly supported A-share code")
        return value

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_snapshot_consistency(self) -> "QfqFactorSnapshot":
        if self.market is not market_code_for(self.code):
            raise ValueError("QFQ snapshot code and market do not match")
        if self.factor_version != f"sha256:{self.response_hash}":
            raise ValueError("factor_version must identify the response hash")
        if self.base_precision != _decimal_precision(self.base_divisor):
            raise ValueError(
                "base_precision must match the base divisor decimal exponent"
            )
        dates = tuple(point.effective_date for point in self.points)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("QFQ factor points must be unique and ordered")
        if not self.points:
            if self.base_divisor != Decimal("1"):
                raise ValueError("empty QFQ history requires a unit base divisor")
            return self
        if self.points[0].cumulative_divisor != self.base_divisor:
            raise ValueError("QFQ base divisor must equal the oldest factor point")
        if self.points[0].precision != self.base_precision:
            raise ValueError("QFQ base precision must equal the oldest point precision")
        if self.points[-1].cumulative_divisor != Decimal("1"):
            raise ValueError("latest QFQ factor point must be anchored at one")
        return self


class AdjustedKlineSeries(BaseModel):
    """A deterministic qfq series plus the factor lineage used to derive it."""

    model_config = ConfigDict(frozen=True)

    adjustment_mode: Literal["qfq"] = "qfq"
    raw_snapshot_id: str = Field(min_length=1)
    factor_source_ids: tuple[str, ...]
    factor_version: str = Field(min_length=1)
    reference_date: date
    raw_snapshot_as_of: datetime
    raw_completed_through: date
    as_of: datetime
    bars: tuple[AdjustedDailyBar, ...]

    @field_validator("raw_snapshot_id", "factor_version")
    @classmethod
    def validate_series_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("adjustment series identities must be non-blank")
        return normalized

    @field_validator("factor_source_ids")
    @classmethod
    def validate_factor_sources(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("factor source identifiers must be non-blank")
        return tuple(sorted({value.strip() for value in values}))

    @field_validator("raw_snapshot_as_of", "as_of")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("adjustment timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> "AdjustedKlineSeries":
        if self.raw_snapshot_as_of > self.as_of:
            raise ValueError("RAW snapshot newer than as_of is not allowed")
        if self.raw_completed_through > self.raw_snapshot_as_of.date():
            raise ValueError("RAW completion proof postdates the snapshot")
        if (self.factor_version == "none") != (not self.factor_source_ids):
            raise ValueError(
                "factor_version none and empty factor sources must appear together"
            )
        if not self.bars:
            raise ValueError("adjusted series requires bars")
        identity = {(bar.code, bar.market) for bar in self.bars}
        if len(identity) != 1:
            raise ValueError("adjusted series requires one instrument")
        dates = tuple(bar.trade_date for bar in self.bars)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("adjusted series dates must be unique and ordered")
        if self.reference_date != dates[-1]:
            raise ValueError("reference_date must equal the last adjusted bar date")
        if dates[-1] > self.raw_completed_through:
            raise ValueError("adjusted bars exceed the snapshot completion proof")
        return self


def _selected_factor_revisions(
    factors: tuple[CorporateActionFactor, ...],
    *,
    as_of: datetime,
    code: str,
    market: MarketCode,
    reference_date: date,
) -> tuple[CorporateActionFactor, ...]:
    eligible = [
        factor
        for factor in factors
        if factor.known_at <= as_of and factor.ex_date <= reference_date
    ]
    selected: dict[str, CorporateActionFactor] = {}
    for factor in eligible:
        if factor.code != code or factor.market != market:
            raise ValueError("corporate-action factor instrument does not match RAW bars")
        current = selected.get(factor.action_id)
        if current is not None and factor.revision == current.revision and factor != current:
            raise ValueError("conflicting factor revision for corporate action")
        if current is None or (factor.revision, factor.known_at, factor.factor_version) > (
            current.revision,
            current.known_at,
            current.factor_version,
        ):
            selected[factor.action_id] = factor
    return tuple(
        sorted(
            selected.values(),
            key=lambda factor: (
                factor.ex_date,
                factor.action_id,
                factor.revision,
                factor.factor_version,
            ),
        )
    )


def _factor_set_version(factors: tuple[CorporateActionFactor, ...]) -> str:
    if not factors:
        return "none"
    canonical_content = json.dumps(
        [factor.model_dump(mode="json") for factor in factors],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"sha256:{sha256(canonical_content.encode('utf-8')).hexdigest()}"


def adjust_qfq_as_of(
    raw_bars: Iterable[RawDailyBar],
    factors: Iterable[CorporateActionFactor],
    *,
    raw_snapshot_id: str,
    raw_snapshot_as_of: datetime,
    raw_completed_through: date,
    as_of: datetime,
) -> AdjustedKlineSeries:
    """Derive a qfq series using only factor evidence known by ``as_of``."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if (
        raw_snapshot_as_of.tzinfo is None
        or raw_snapshot_as_of.utcoffset() is None
    ):
        raise ValueError("raw_snapshot_as_of must be timezone-aware")
    as_of_utc = as_of.astimezone(UTC)
    raw_snapshot_as_of_utc = raw_snapshot_as_of.astimezone(UTC)
    if raw_snapshot_as_of_utc > as_of_utc:
        raise ValueError("RAW snapshot newer than as_of is not allowed")
    if not raw_snapshot_id.strip():
        raise ValueError("raw_snapshot_id must be non-blank")
    bars = tuple(sorted(raw_bars, key=lambda bar: bar.trade_date))
    if not bars:
        raise ValueError("qfq adjustment requires RAW bars")
    if len({bar.trade_date for bar in bars}) != len(bars):
        raise ValueError("qfq adjustment requires unique RAW trade dates")
    code = bars[0].code
    market = bars[0].market
    if any(bar.code != code or bar.market != market for bar in bars):
        raise ValueError("qfq adjustment requires one RAW instrument")
    if any(bar.trade_date > raw_completed_through for bar in bars):
        raise ValueError("RAW bars exceed the snapshot completion proof")
    if raw_completed_through > raw_snapshot_as_of_utc.date():
        raise ValueError("RAW completion proof postdates the snapshot")
    reference_date = bars[-1].trade_date
    selected = _selected_factor_revisions(
        tuple(
            CorporateActionFactor.model_validate(factor.model_dump())
            for factor in factors
        ),
        as_of=as_of_utc,
        code=code,
        market=market,
        reference_date=reference_date,
    )
    max_price_digits = max(
        len(value.as_tuple().digits)
        for bar in bars
        for value in (bar.open, bar.high, bar.low, bar.close)
    )
    max_volume_digits = max(len(Decimal(bar.volume).as_tuple().digits) for bar in bars)
    calculation_precision = max(
        28,
        max_price_digits
        + sum(len(factor.price_factor.as_tuple().digits) for factor in selected),
        max_volume_digits
        + sum(len(factor.volume_factor.as_tuple().digits) for factor in selected),
    )
    adjusted_items: list[AdjustedDailyBar] = []
    with localcontext() as context:
        context.prec = calculation_precision
        for bar in bars:
            applicable = tuple(
                factor for factor in selected if bar.trade_date < factor.ex_date
            )
            price_multiplier = prod(
                (factor.price_factor for factor in applicable),
                start=Decimal("1"),
            )
            volume_multiplier = prod(
                (factor.volume_factor for factor in applicable),
                start=Decimal("1"),
            )
            adjusted_items.append(
                AdjustedDailyBar(
                    code=bar.code,
                    market=bar.market,
                    trade_date=bar.trade_date,
                    open=bar.open * price_multiplier,
                    high=bar.high * price_multiplier,
                    low=bar.low * price_multiplier,
                    close=bar.close * price_multiplier,
                    volume=Decimal(bar.volume) * volume_multiplier,
                    amount=bar.amount,
                )
            )
    adjusted = tuple(adjusted_items)
    return AdjustedKlineSeries(
        raw_snapshot_id=raw_snapshot_id.strip(),
        factor_source_ids=tuple(
            sorted(
                {
                    source_id
                    for factor in selected
                    for source_id in factor.factor_source_ids
                }
            )
        ),
        factor_version=_factor_set_version(selected),
        reference_date=reference_date,
        raw_snapshot_as_of=raw_snapshot_as_of_utc,
        raw_completed_through=raw_completed_through,
        as_of=as_of_utc,
        bars=adjusted,
    )


__all__ = [
    "ActionKind",
    "AdjustedDailyBar",
    "AdjustedKlineSeries",
    "CorporateActionFactor",
    "CumulativeQfqFactorPoint",
    "QfqFactorSnapshot",
    "adjust_qfq_as_of",
    "is_supported_a_share_code",
]

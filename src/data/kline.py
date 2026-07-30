"""Typed contracts for auditable RAW completed daily K-line evidence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MarketCode(str, Enum):
    """Canonical A-share exchange identifiers."""

    SSE = "SSE"
    SZSE = "SZSE"
    BSE = "BSE"


class RawDailyBar(BaseModel):
    """One completed, unadjusted daily market fact.

    ``volume_precision`` is the smallest unit represented by the source after
    normalization to shares. A share-granular source uses 1; a source that
    reports whole lots uses 100.
    """

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    trade_date: date
    period: Literal["1d"] = "1d"
    currency: Literal["CNY"] = "CNY"
    price_basis: Literal["raw"] = "raw"
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    price_tick: Decimal = Field(default=Decimal("0.01"), gt=0)
    volume: int = Field(ge=0)
    volume_precision: int = Field(default=1, ge=1)
    amount: Decimal | None = Field(default=None, ge=0)
    amount_precision: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_raw_bar(self) -> "RawDailyBar":
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within the daily low/high range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within the daily low/high range")
        for field_name in ("open", "high", "low", "close"):
            price = getattr(self, field_name)
            if price % self.price_tick != 0:
                raise ValueError(f"{field_name} must align to price_tick")
        if (self.amount is None) != (self.amount_precision is None):
            raise ValueError(
                "amount and amount_precision must either both be set or both be absent"
            )
        return self


def market_code_for(stock_code: str) -> MarketCode:
    """Map one A-share security code to its exchange."""
    if stock_code.startswith(("4", "8", "92")):
        return MarketCode.BSE
    if stock_code.startswith(("5", "6", "9")):
        return MarketCode.SSE
    return MarketCode.SZSE


def raw_daily_bar_conflict(
    first: RawDailyBar,
    second: RawDailyBar,
) -> tuple[str, str] | None:
    """Return the shared strict reconciliation error for two same-day RAW bars."""

    if second.price_tick != first.price_tick:
        return "price_tick_conflict", "RAW daily price ticks do not match"
    if any(
        getattr(second, field_name) != getattr(first, field_name)
        for field_name in ("open", "high", "low", "close")
    ):
        return (
            "raw_ohlc_conflict",
            "Completed RAW daily OHLC differs by at least one tick",
        )
    volume_precision = max(first.volume_precision, second.volume_precision)
    if abs(first.volume - second.volume) >= volume_precision:
        return (
            "raw_volume_conflict",
            "RAW daily volumes differ beyond declared source precision",
        )
    if first.amount is not None and second.amount is not None:
        first_precision = first.amount_precision or Decimal("0")
        second_precision = second.amount_precision or Decimal("0")
        precision = max(first_precision, second_precision)
        if abs(first.amount - second.amount) >= precision:
            return (
                "raw_amount_conflict",
                "RAW daily amounts differ beyond declared source precision",
            )
    return None


def select_canonical_raw_daily_bar(
    candidates: Iterable[tuple[str, RawDailyBar]],
) -> RawDailyBar:
    """Choose one RAW candidate by precision, then stable source-id tie-break."""

    choices = tuple(candidates)
    if not choices:
        raise ValueError("canonical RAW daily selection requires candidates")
    return min(
        choices,
        key=lambda choice: (
            choice[1].volume_precision,
            choice[1].amount is None,
            choice[1].amount_precision or Decimal("Infinity"),
            choice[0],
        ),
    )[1]


__all__ = [
    "MarketCode",
    "RawDailyBar",
    "market_code_for",
    "raw_daily_bar_conflict",
    "select_canonical_raw_daily_bar",
]

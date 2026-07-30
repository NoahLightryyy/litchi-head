"""Typed contracts for auditable RAW completed daily K-line evidence."""

from __future__ import annotations

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


__all__ = ["MarketCode", "RawDailyBar", "market_code_for"]

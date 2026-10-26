"""Frozen display-only ETF identity and quote contract; independent of stock research."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator


class EtfIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str = Field(pattern=r"^\d{6}$")
    symbol: str = Field(pattern=r"^(sh|sz)\d{6}$")
    exchange: Literal["SH", "SZ"]
    name: str = Field(min_length=1)
    instrument_type: Literal["etf"] = "etf"

    @model_validator(mode="after")
    def consistent_identity(self) -> "EtfIdentity":
        if self.symbol != self.exchange.lower() + self.code:
            raise ValueError("ETF symbol and market do not match code")
        return self


class EtfQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    price: float = Field(gt=0)
    previous_close: float = Field(gt=0)
    change: float
    change_pct: float
    open: float | None = Field(default=None, gt=0)
    high: float | None = Field(default=None, gt=0)
    low: float | None = Field(default=None, gt=0)
    quoted_at: AwareDatetime
    source_name: str = Field(min_length=1)


class EtfDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    identity: EtfIdentity
    quote: EtfQuote | None = None
    status: Literal["ready", "partial"]
    source: Literal["sina"] = "sina"
    source_url: HttpUrl
    catalog_fetched_at: AwareDatetime
    fetched_at: AwareDatetime
    limitations: list[str]


class EtfCatalog(BaseModel):
    items: tuple[EtfIdentity, ...]
    fetched_at: datetime


EtfKlineSource = Literal["tencent", "sina"]


class EtfDailyBar(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_fund_bar(self) -> "EtfDailyBar":
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("ETF OHLC range invalid")
        if any(Decimal(str(value)) % Decimal("0.001") for value in (
            self.open, self.high, self.low, self.close,
        )):
            raise ValueError("ETF price must align to the 0.001 CNY tick")
        return self


class EtfKlineDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: EtfKlineSource
    status: Literal["success", "empty", "failed"]
    error_code: str | None = None


class EtfKlineDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    identity: EtfIdentity
    status: Literal["ready", "empty", "unavailable"]
    source: EtfKlineSource | None = None
    price_basis: Literal["raw"] = "raw"
    price_unit: Literal["CNY"] = "CNY"
    volume_unit: Literal["fund_units"] = "fund_units"
    price_tick: float = Field(default=0.001, ge=0.001, le=0.001)
    verification: Literal["single_source"] = "single_source"
    fetched_at: AwareDatetime
    requested_start: date
    requested_end: date
    data_start: date | None = None
    data_end: date | None = None
    bars: list[EtfDailyBar] = Field(default_factory=list, max_length=730)
    diagnostics: list[EtfKlineDiagnostic]
    limitations: list[str]

    @model_validator(mode="after")
    def consistent_series(self) -> "EtfKlineDisplay":
        if bool(self.bars) != (self.status == "ready") or bool(self.bars) != bool(self.source):
            raise ValueError("ETF daily status/source and bars disagree")
        dates = [bar.date for bar in self.bars]
        if (self.requested_start > self.requested_end or dates != sorted(set(dates)) or
                any(not self.requested_start <= value <= self.requested_end for value in dates)):
            raise ValueError("ETF daily dates invalid")
        if (self.data_start, self.data_end) != (
            dates[0] if dates else None, dates[-1] if dates else None,
        ):
            raise ValueError("ETF daily range and bars disagree")
        return self

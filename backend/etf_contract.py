"""Frozen display-only ETF identity and quote contract; independent of stock research."""
from datetime import datetime
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

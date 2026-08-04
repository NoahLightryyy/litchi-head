"""KR-3 typed four-layer market-data business envelope."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.data.intraday import IntradayBar, IntradayBarState
from src.data.kline import MarketCode, market_code_for
from src.data.kline_adjustment import AdjustedDailyBar, AdjustedKlineSeries
from src.data.models import StockQuote

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _validated_upstreams(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(value.strip() for value in values)
    if any(not value for value in normalized) or len(set(normalized)) < 2:
        raise ValueError("verified market-data layer requires two distinct upstreams")
    return tuple(sorted(set(normalized)))


class TradingPhase(str, Enum):
    """Explicit A-share session phase attached to dynamic market facts."""

    PRE_OPEN = "pre_open"
    CONTINUOUS_AUCTION = "continuous_auction"
    MIDDAY_BREAK = "midday_break"
    CLOSING_AUCTION = "closing_auction"
    CLOSED = "closed"


class KlineBusinessLayer(str, Enum):
    """Stable layer identities used by fail-closed diagnostics."""

    FINAL_DAILY = "FINAL_DAILY"
    FINAL_MINUTE = "FINAL_MINUTE"
    LIVE_QUOTE = "LIVE_QUOTE"
    PROVISIONAL = "PROVISIONAL"


class KlineLayerDiagnostic(BaseModel):
    """One layer's compact availability and source diagnosis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: KlineBusinessLayer
    complete: bool
    upstream_ids: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_complete_sources(self) -> "KlineLayerDiagnostic":
        if self.complete:
            try:
                _validated_upstreams(self.upstream_ids)
            except ValueError as error:
                raise ValueError(
                    "complete layer diagnostic requires two distinct upstreams"
                ) from error
        return self


class KlineBusinessFailure(BaseModel):
    """Fail-closed result that deliberately carries no partial business data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    complete: Literal[False] = False
    symbol: str = Field(pattern=r"^\d{6}$")
    market: MarketCode
    as_of: datetime
    trading_phase: TradingPhase
    error_codes: tuple[str, ...] = Field(min_length=1)
    layer_diagnostics: tuple[KlineLayerDiagnostic, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_diagnostic_coverage(self) -> "KlineBusinessFailure":
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("business timestamps must be timezone-aware")
        layers = tuple(item.layer for item in self.layer_diagnostics)
        if len(layers) != len(KlineBusinessLayer) or set(layers) != set(KlineBusinessLayer):
            raise ValueError("failure must diagnose all four layers exactly once")
        incomplete = tuple(item for item in self.layer_diagnostics if not item.complete)
        diagnostic_codes = tuple(item.error_code for item in incomplete)
        invalid_complete = any(
            item.complete and (item.error_code is not None or item.error_message is not None)
            for item in self.layer_diagnostics
        )
        if (
            not incomplete
            or invalid_complete
            or any(item.error_code is None or not item.error_message for item in incomplete)
            or len(set(self.error_codes)) != len(self.error_codes)
            or any(not code.strip() for code in self.error_codes)
            or set(diagnostic_codes) != set(self.error_codes)
        ):
            raise ValueError("failure diagnostics and error_codes must agree")
        return self


class ProvisionalSessionBar(BaseModel):
    """Today's mutable RAW OHLC state, kept outside completed daily bars."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(pattern=r"^\d{6}$")
    market: MarketCode
    trading_date: date
    as_of: datetime
    trading_phase: TradingPhase
    state: Literal["PROVISIONAL"] = "PROVISIONAL"
    price_basis: Literal["raw"] = "raw"
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    cumulative_volume: int = Field(ge=0)
    cumulative_amount: Decimal | None = Field(default=None, ge=0)
    upstream_ids: tuple[str, ...] = Field(min_length=2)

    @field_validator("upstream_ids")
    @classmethod
    def validate_upstreams(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_upstreams(values)

    @model_validator(mode="after")
    def validate_timestamp(self) -> "ProvisionalSessionBar":
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("business timestamps must be timezone-aware")
        if (
            self.high < self.low
            or not self.low <= self.open <= self.high
            or not self.low <= self.close <= self.high
        ):
            raise ValueError("provisional OHLC must stay within low/high")
        return self


class LiveRawQuote(StockQuote):
    """Immutable verified realtime quote whose price coordinate is RAW."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    price_basis: Literal["raw"] = "raw"


class FinalMinuteBar(IntradayBar):
    """Immutable verified minute that can only represent a finalized interval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: Literal[IntradayBarState.FINAL] = IntradayBarState.FINAL


class KlineBusinessEnvelope(BaseModel):
    """Complete four-layer input accepted by later AI and trading gates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    complete: Literal[True] = True
    symbol: str = Field(pattern=r"^\d{6}$")
    market: MarketCode
    as_of: datetime
    trading_phase: TradingPhase
    final_daily_bars: AdjustedKlineSeries
    daily_upstream_ids: tuple[str, ...] = Field(min_length=2)
    final_minute_bars: tuple[FinalMinuteBar, ...] = Field(min_length=1)
    intraday_upstream_ids: tuple[str, ...] = Field(min_length=2)
    live_quote: LiveRawQuote
    quote_upstream_ids: tuple[str, ...] = Field(min_length=2)
    provisional_session_bar: ProvisionalSessionBar

    @property
    def live_quote_price_basis(self) -> Literal["raw"]:
        return self.live_quote.price_basis

    @field_validator(
        "daily_upstream_ids",
        "intraday_upstream_ids",
        "quote_upstream_ids",
    )
    @classmethod
    def validate_upstreams(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_upstreams(values)

    @field_validator("live_quote", mode="before")
    @classmethod
    def freeze_live_quote(cls, value: object) -> object:
        if isinstance(value, StockQuote) and not isinstance(value, LiveRawQuote):
            return value.model_dump()
        return value

    @field_validator("final_minute_bars", mode="before")
    @classmethod
    def freeze_final_minutes(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(
                item.model_dump()
                if isinstance(item, IntradayBar) and not isinstance(item, FinalMinuteBar)
                else item
                for item in value
            )
        return value

    @model_validator(mode="after")
    def validate_layer_boundaries(self) -> "KlineBusinessEnvelope":
        quote_at = self.live_quote.fetched_at
        if (
            self.as_of.tzinfo is None
            or self.as_of.utcoffset() is None
            or quote_at is None
            or quote_at.tzinfo is None
            or quote_at.utcoffset() is None
        ):
            raise ValueError("business timestamps must be timezone-aware")
        layer_timestamps = (
            self.final_daily_bars.as_of,
            *(bar.timestamp for bar in self.final_minute_bars),
            quote_at,
            self.provisional_session_bar.as_of,
        )
        if any(timestamp > self.as_of for timestamp in layer_timestamps):
            raise ValueError("market-data layer timestamp cannot exceed envelope as_of")
        envelope_session_date = self.as_of.astimezone(SHANGHAI).date()
        provisional_session_date = self.provisional_session_bar.as_of.astimezone(SHANGHAI).date()
        if (
            self.provisional_session_bar.trading_date != envelope_session_date
            or provisional_session_date != envelope_session_date
            or self.provisional_session_bar.trading_phase is not self.trading_phase
        ):
            raise ValueError("PROVISIONAL metadata must match envelope session")
        if self.final_daily_bars.reference_date >= self.provisional_session_bar.trading_date:
            raise ValueError("FINAL_DAILY must end before PROVISIONAL session date")
        minute_timestamps = tuple(bar.timestamp for bar in self.final_minute_bars)
        minute_dates = {timestamp.astimezone(SHANGHAI).date() for timestamp in minute_timestamps}
        if minute_timestamps != tuple(sorted(set(minute_timestamps))) or minute_dates != {
            self.provisional_session_bar.trading_date
        }:
            raise ValueError(
                "FINAL_MINUTE timestamps must be unique, ordered, and in PROVISIONAL session"
            )
        if self.live_quote.code != self.symbol:
            raise ValueError("live quote identity must match envelope symbol")
        daily_identities = {(bar.code, bar.market) for bar in self.final_daily_bars.bars}
        minute_identities = {
            (bar.code, market_code_for(bar.code)) for bar in self.final_minute_bars
        }
        provisional_identity = (
            self.provisional_session_bar.code,
            self.provisional_session_bar.market,
        )
        expected_identity = (self.symbol, self.market)
        if (
            daily_identities != {expected_identity}
            or minute_identities != {expected_identity}
            or provisional_identity != expected_identity
        ):
            raise ValueError("market-data layer identity must match envelope")
        return self


class DailyPromotionRecord(BaseModel):
    """Immutable audit record for one PROVISIONAL to FINAL_DAILY promotion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    promotion_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal["PROMOTED"] = "PROMOTED"
    symbol: str = Field(pattern=r"^\d{6}$")
    market: MarketCode
    trading_date: date
    provisional_bar: ProvisionalSessionBar
    final_series_as_of: datetime
    raw_snapshot_as_of: datetime
    promoted_at: datetime
    raw_snapshot_id: str = Field(min_length=1)
    factor_version: str = Field(min_length=1)
    daily_upstream_ids: tuple[str, ...] = Field(min_length=2)
    final_bar: AdjustedDailyBar

    @property
    def provisional_as_of(self) -> datetime:
        return self.provisional_bar.as_of

    @field_validator("daily_upstream_ids")
    @classmethod
    def validate_upstreams(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_upstreams(values)

    @model_validator(mode="after")
    def validate_record(self) -> "DailyPromotionRecord":
        if (
            self.final_series_as_of.tzinfo is None
            or self.final_series_as_of.utcoffset() is None
            or self.raw_snapshot_as_of.tzinfo is None
            or self.raw_snapshot_as_of.utcoffset() is None
            or self.promoted_at.tzinfo is None
            or self.promoted_at.utcoffset() is None
            or self.final_series_as_of < self.provisional_bar.as_of
            or self.raw_snapshot_as_of < self.provisional_bar.as_of
            or self.provisional_bar.as_of > self.promoted_at
            or self.final_series_as_of > self.promoted_at
            or self.raw_snapshot_as_of > self.final_series_as_of
        ):
            raise ValueError("promotion record timestamps are invalid")
        if (
            self.final_bar.code != self.symbol
            or self.final_bar.market is not self.market
            or self.final_bar.trade_date != self.trading_date
            or self.provisional_bar.code != self.symbol
            or self.provisional_bar.market is not self.market
            or self.provisional_bar.trading_date != self.trading_date
        ):
            raise ValueError("promotion record final bar identity is invalid")
        expected_id = _promotion_id(
            provisional=self.provisional_bar,
            raw_snapshot_id=self.raw_snapshot_id,
            factor_version=self.factor_version,
            final_series_as_of=self.final_series_as_of,
            raw_snapshot_as_of=self.raw_snapshot_as_of,
            final_bar=self.final_bar,
            daily_upstream_ids=self.daily_upstream_ids,
        )
        if self.promotion_id != expected_id:
            raise ValueError("promotion record content hash is invalid")
        return self


class DailyPromotionConflictError(RuntimeError):
    """A retry would replace an existing immutable promotion record."""


def _promotion_id(
    *,
    provisional: ProvisionalSessionBar,
    raw_snapshot_id: str,
    factor_version: str,
    final_series_as_of: datetime,
    raw_snapshot_as_of: datetime,
    final_bar: AdjustedDailyBar,
    daily_upstream_ids: tuple[str, ...],
) -> str:
    identity_payload = {
        "provisional": provisional.model_dump(mode="json"),
        "raw_snapshot_id": raw_snapshot_id,
        "factor_version": factor_version,
        "final_series_as_of": final_series_as_of.isoformat(),
        "raw_snapshot_as_of": raw_snapshot_as_of.isoformat(),
        "final_bar": final_bar.model_dump(mode="json"),
        "daily_upstream_ids": daily_upstream_ids,
    }
    return hashlib.sha256(
        json.dumps(
            identity_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def promote_provisional_session(
    *,
    provisional: ProvisionalSessionBar,
    final_daily_series: AdjustedKlineSeries,
    daily_upstream_ids: tuple[str, ...],
    promoted_at: datetime,
    existing: DailyPromotionRecord | None = None,
) -> DailyPromotionRecord:
    """Create one deterministic promotion record from verified closing evidence."""

    normalized_upstreams = _validated_upstreams(daily_upstream_ids)
    final_bar = final_daily_series.bars[-1]
    if (
        final_daily_series.reference_date != provisional.trading_date
        or final_daily_series.raw_completed_through < provisional.trading_date
        or final_bar.trade_date != provisional.trading_date
        or final_bar.code != provisional.code
        or final_bar.market is not provisional.market
    ):
        raise ValueError("final daily series must close promoted session")
    if (
        promoted_at.tzinfo is None
        or promoted_at.utcoffset() is None
        or final_daily_series.as_of < provisional.as_of
        or final_daily_series.raw_snapshot_as_of < provisional.as_of
        or provisional.as_of > promoted_at
        or final_daily_series.raw_snapshot_as_of > promoted_at
        or final_daily_series.as_of > promoted_at
    ):
        raise ValueError("promotion requires timezone-aware evidence no newer than promoted_at")
    promotion_id = _promotion_id(
        provisional=provisional,
        raw_snapshot_id=final_daily_series.raw_snapshot_id,
        factor_version=final_daily_series.factor_version,
        final_series_as_of=final_daily_series.as_of,
        raw_snapshot_as_of=final_daily_series.raw_snapshot_as_of,
        final_bar=final_bar,
        daily_upstream_ids=normalized_upstreams,
    )
    candidate = DailyPromotionRecord(
        promotion_id=promotion_id,
        symbol=provisional.code,
        market=provisional.market,
        trading_date=provisional.trading_date,
        provisional_bar=provisional,
        final_series_as_of=final_daily_series.as_of,
        raw_snapshot_as_of=final_daily_series.raw_snapshot_as_of,
        promoted_at=promoted_at,
        raw_snapshot_id=final_daily_series.raw_snapshot_id,
        factor_version=final_daily_series.factor_version,
        daily_upstream_ids=normalized_upstreams,
        final_bar=final_bar,
    )
    if existing is not None and existing.promotion_id == candidate.promotion_id:
        return existing
    if existing is not None:
        raise DailyPromotionConflictError("existing daily promotion conflicts with retry evidence")
    return candidate


KlineBusinessResult = Annotated[
    KlineBusinessEnvelope | KlineBusinessFailure,
    Field(discriminator="complete"),
]


__all__ = [
    "KlineBusinessEnvelope",
    "KlineBusinessFailure",
    "KlineBusinessLayer",
    "KlineBusinessResult",
    "KlineLayerDiagnostic",
    "FinalMinuteBar",
    "LiveRawQuote",
    "DailyPromotionRecord",
    "DailyPromotionConflictError",
    "ProvisionalSessionBar",
    "TradingPhase",
    "promote_provisional_session",
]

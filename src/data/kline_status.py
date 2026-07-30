"""Continuous official security-status evidence ledger."""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.data.kline import MarketCode
from src.data.kline_calendar import (
    OfficialSecurityStatusWindow,
    SecurityStatusCoverageError,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"


class SuspensionEventKind(str, Enum):
    """Daily K-line relevant full-day security-status transitions."""

    FULL_DAY_START = "full_day_start"
    FULL_DAY_RESUME = "full_day_resume"


class SecurityTradingState(str, Enum):
    """Trading state at the opening boundary of one natural date."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class OfficialSuspensionEvent(BaseModel):
    """One explicit suspension transition extracted from an official document."""

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    kind: SuspensionEventKind
    effective_on: date
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=_SHA256_PATTERN)


class OfficialSecurityLifecycleEvidence(BaseModel):
    """Official listing and optional delisting boundary for one security."""

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    listed_on: date
    delisted_on: date | None = None
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "OfficialSecurityLifecycleEvidence":
        if self.delisted_on is not None and self.delisted_on <= self.listed_on:
            raise ValueError("delisting date must be later than listing date")
        return self


class OfficialSecurityStateCheckpoint(BaseModel):
    """Auditable state anchor produced by an earlier continuous ledger."""

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    state_on: date
    state: SecurityTradingState
    pending_events: tuple[OfficialSuspensionEvent, ...] = ()
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> "OfficialSecurityStateCheckpoint":
        if any(
            event.code != self.code
            or event.market is not self.market
            or event.effective_on < self.state_on
            for event in self.pending_events
        ):
            raise ValueError(
                "checkpoint pending event identity or effective date is invalid"
            )
        return self


class OfficialSuspensionEventBatch(BaseModel):
    """One complete official query batch and its normalized response digest."""

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    coverage_start: date
    coverage_end: date
    events: tuple[OfficialSuspensionEvent, ...]
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_batch(self) -> "OfficialSuspensionEventBatch":
        if self.coverage_start > self.coverage_end:
            raise ValueError("event batch coverage start must not exceed end")
        if any(
            event.code != self.code or event.market is not self.market
            for event in self.events
        ):
            raise ValueError("event batch identity does not match its events")
        return self


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


class SuspensionStatusLedger:
    """Reduce continuous official event batches into one status window."""

    def __init__(
        self,
        *,
        lifecycle: OfficialSecurityLifecycleEvidence,
        checkpoint: OfficialSecurityStateCheckpoint,
        batches: tuple[OfficialSuspensionEventBatch, ...],
    ) -> None:
        identities = {
            (lifecycle.code, lifecycle.market),
            (checkpoint.code, checkpoint.market),
            *((batch.code, batch.market) for batch in batches),
        }
        if len(identities) != 1:
            raise ValueError("security status ledger identity mismatch")
        self._lifecycle = lifecycle
        self._checkpoint = checkpoint
        self._batches = tuple(
            sorted(
                batches,
                key=lambda batch: (
                    batch.coverage_start,
                    batch.coverage_end,
                    batch.content_hash,
                ),
            )
        )

    def _assert_continuous_coverage(self, required_end: date) -> None:
        if self._checkpoint.state_on > required_end:
            return
        if not self._batches:
            raise SecurityStatusCoverageError(
                "official suspension batches do not provide continuous coverage"
            )
        covered_through = self._checkpoint.state_on - timedelta(days=1)
        for batch in self._batches:
            if batch.coverage_end < self._checkpoint.state_on:
                continue
            if batch.coverage_start > covered_through + timedelta(days=1):
                raise SecurityStatusCoverageError(
                    "official suspension batches do not provide continuous coverage"
                )
            if batch.coverage_end > covered_through:
                covered_through = batch.coverage_end
            if covered_through >= required_end:
                return
        raise SecurityStatusCoverageError(
            "official suspension batches do not provide continuous coverage"
        )

    def build_window(
        self,
        *,
        start: date,
        end: date,
        market_open_dates: tuple[date, ...],
    ) -> OfficialSecurityStatusWindow:
        """Build only when checkpoint and official batches prove continuity."""
        if start > end:
            raise ValueError("security status start must not exceed end")
        anchor_start = max(start, self._lifecycle.listed_on)
        if end >= self._lifecycle.listed_on and (
            self._checkpoint.state_on > anchor_start
        ):
            raise SecurityStatusCoverageError(
                "official security checkpoint does not anchor requested window"
            )

        required_end = end
        if self._lifecycle.delisted_on is not None:
            required_end = min(
                required_end,
                self._lifecycle.delisted_on - timedelta(days=1),
            )
        self._assert_continuous_coverage(required_end)

        events: list[OfficialSuspensionEvent] = list(
            self._checkpoint.pending_events
        )
        source_urls = [
            self._lifecycle.source_url,
            self._checkpoint.source_url,
        ]
        source_hashes = [
            self._lifecycle.content_hash,
            self._checkpoint.content_hash,
        ]
        for event in self._checkpoint.pending_events:
            source_urls.append(event.source_url)
            source_hashes.append(event.content_hash)
        for batch in self._batches:
            if (
                batch.coverage_end < self._checkpoint.state_on
                or batch.coverage_start > required_end
            ):
                continue
            source_urls.append(batch.source_url)
            source_hashes.append(batch.content_hash)
            for event in batch.events:
                if self._checkpoint.state_on <= event.effective_on <= end:
                    events.append(event)
                    source_urls.append(event.source_url)
                    source_hashes.append(event.content_hash)

        events_by_date: dict[date, set[SuspensionEventKind]] = {}
        for event in events:
            events_by_date.setdefault(event.effective_on, set()).add(event.kind)
        if any(len(kinds) > 1 for kinds in events_by_date.values()):
            raise SecurityStatusCoverageError(
                "official suspension events have conflicting transitions"
            )

        state = self._checkpoint.state
        for effective_on in sorted(
            day for day in events_by_date if day < start
        ):
            kinds = events_by_date[effective_on]
            if SuspensionEventKind.FULL_DAY_START in kinds:
                state = SecurityTradingState.SUSPENDED
            elif SuspensionEventKind.FULL_DAY_RESUME in kinds:
                state = SecurityTradingState.ACTIVE

        suspended_dates: list[date] = []
        for open_date in sorted(set(market_open_dates)):
            if not start <= open_date <= end:
                continue
            kinds = events_by_date.get(open_date, set())
            if SuspensionEventKind.FULL_DAY_START in kinds:
                state = SecurityTradingState.SUSPENDED
            elif SuspensionEventKind.FULL_DAY_RESUME in kinds:
                state = SecurityTradingState.ACTIVE
            if state is SecurityTradingState.SUSPENDED:
                suspended_dates.append(open_date)

        return OfficialSecurityStatusWindow(
            code=self._lifecycle.code,
            market=self._lifecycle.market,
            coverage_start=start,
            coverage_end=end,
            listed_on=self._lifecycle.listed_on,
            delisted_on=self._lifecycle.delisted_on,
            full_day_suspensions=tuple(suspended_dates),
            intraday_suspensions=(),
            source_urls=_unique(source_urls),
            source_hashes=_unique(source_hashes),
        )


__all__ = [
    "OfficialSecurityLifecycleEvidence",
    "OfficialSecurityStateCheckpoint",
    "OfficialSuspensionEvent",
    "OfficialSuspensionEventBatch",
    "SecurityTradingState",
    "SuspensionEventKind",
    "SuspensionStatusLedger",
]

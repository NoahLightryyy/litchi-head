"""Versioned official A-share market calendars for K-line completeness."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from pydantic import BaseModel, Field, computed_field, model_validator

from src.data.kline import MarketCode


class CalendarCoverageError(ValueError):
    """The requested market/year has no approved official calendar version."""


class MarketCalendarVersion(BaseModel):
    """One exchange-specific, normalized annual closure schedule."""

    market: MarketCode
    year: int = Field(ge=1990, le=2100)
    source_url: str = Field(min_length=1)
    published_on: date
    closed_weekdays: tuple[date, ...]

    @model_validator(mode="after")
    def validate_dates(self) -> "MarketCalendarVersion":
        if any(day.year != self.year for day in self.closed_weekdays):
            raise ValueError("closed dates must belong to the calendar year")
        if any(day.weekday() >= 5 for day in self.closed_weekdays):
            raise ValueError("closed_weekdays must not include weekends")
        if len(set(self.closed_weekdays)) != len(self.closed_weekdays):
            raise ValueError("closed_weekdays must not contain duplicates")
        return self

    @computed_field
    @property
    def content_hash(self) -> str:
        """Hash the normalized schedule extracted from the authority notice."""
        payload = {
            "market": self.market.value,
            "year": self.year,
            "source_url": self.source_url,
            "published_on": self.published_on.isoformat(),
            "closed_weekdays": [
                day.isoformat() for day in self.closed_weekdays
            ],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OfficialTradingCalendar:
    """Resolve open dates only from approved, versioned exchange schedules."""

    def __init__(self, versions: tuple[MarketCalendarVersion, ...]) -> None:
        indexed = {(version.market, version.year): version for version in versions}
        if len(indexed) != len(versions):
            raise ValueError("duplicate official market calendar version")
        self._versions = indexed

    @property
    def versions(self) -> tuple[MarketCalendarVersion, ...]:
        return tuple(self._versions.values())

    def open_dates(
        self,
        market: MarketCode,
        start: date,
        end: date,
    ) -> tuple[date, ...]:
        if start > end:
            raise ValueError("calendar start date must not exceed end date")
        missing = [
            year
            for year in range(start.year, end.year + 1)
            if (market, year) not in self._versions
        ]
        if missing:
            years = ", ".join(str(year) for year in missing)
            raise CalendarCoverageError(
                f"official {market.value} calendar coverage missing for {years}"
            )

        current = start
        opened: list[date] = []
        while current <= end:
            version = self._versions[(market, current.year)]
            if (
                current.weekday() < 5
                and current not in version.closed_weekdays
            ):
                opened.append(current)
            current += timedelta(days=1)
        return tuple(opened)


_CLOSED_WEEKDAYS_2026 = (
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 23),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 5, 4),
    date(2026, 5, 5),
    date(2026, 6, 19),
    date(2026, 9, 25),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
)


def official_a_share_calendar_2026() -> OfficialTradingCalendar:
    """Build separately versioned SSE, SZSE and BSE 2026 schedules."""
    sources = {
        MarketCode.SSE: (
            "https://www.sse.com.cn/disclosure/dealinstruc/closed/"
        ),
        MarketCode.SZSE: (
            "https://www.szse.cn/English/services/trading/calendar/index.html"
        ),
        MarketCode.BSE: "https://www.bse.cn/important_news/200027428.html",
    }
    return OfficialTradingCalendar(
        tuple(
            MarketCalendarVersion(
                market=market,
                year=2026,
                source_url=source_url,
                published_on=date(2025, 12, 22),
                closed_weekdays=_CLOSED_WEEKDAYS_2026,
            )
            for market, source_url in sources.items()
        )
    )


__all__ = [
    "CalendarCoverageError",
    "MarketCalendarVersion",
    "OfficialTradingCalendar",
    "official_a_share_calendar_2026",
]

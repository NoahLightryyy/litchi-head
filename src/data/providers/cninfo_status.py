"""Auditable CNINFO suspension and resumption event evidence.

This adapter deliberately emits events rather than a complete security-status
window. A later ledger must prove continuous historical coverage before these
events may exclude dates from K-line completeness checks.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import date
from enum import Enum
from typing import Any, Protocol, cast

from pydantic import BaseModel, Field

from src.data.kline import MarketCode
from src.data.providers.cninfo import (
    CNINFO_STATIC_URL,
    CninfoDirectFetcher,
    _default_direct_fetcher,
)

CNINFO_DOCUMENT_TIMEOUT_SECONDS = 20.0
_DATE_BODY = (
    r"(?P<year>\d{4})\s*年\s*"
    r"(?P<month>\d{1,2})\s*月\s*"
    r"(?P<day>\d{1,2})\s*日"
)
_START_PATTERN = re.compile(
    rf"自\s*{_DATE_BODY}[^。；]{{0,20}}?开市起\s*(?:继续\s*)?停牌"
)
_RESUME_PATTERN = re.compile(
    rf"自\s*{_DATE_BODY}[^。；]{{0,20}}?开市起\s*复牌"
)


class SuspensionEventSourceError(RuntimeError):
    """Official event evidence is unsupported, incomplete, or unavailable."""


class SuspensionEventKind(str, Enum):
    """Daily K-line relevant full-day security-status transitions."""

    FULL_DAY_START = "full_day_start"
    FULL_DAY_RESUME = "full_day_resume"


class OfficialDocument(BaseModel):
    """Normalized official attachment with an integrity digest."""

    text: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class OfficialSuspensionEvent(BaseModel):
    """One explicit suspension transition extracted from an official document."""

    code: str = Field(min_length=6, max_length=6)
    market: MarketCode
    kind: SuspensionEventKind
    effective_on: date
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class OfficialDocumentFetcher(Protocol):
    """Replaceable official PDF download and text-extraction boundary."""

    def __call__(self, url: str) -> OfficialDocument:
        """Return extracted text and a SHA-256 digest of the original bytes."""
        ...


def _default_document_fetcher(url: str) -> OfficialDocument:
    import httpx
    import pymupdf

    response = httpx.get(
        url,
        timeout=CNINFO_DOCUMENT_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    raw = response.content
    document = pymupdf.open(stream=raw, filetype="pdf")
    try:
        text = "\n".join(
            cast(str, page.get_text("text")) for page in document
        )
    finally:
        document.close()
    return OfficialDocument(
        text=text,
        content_hash=hashlib.sha256(raw).hexdigest(),
    )


def _parse_total(payload: Mapping[str, Any]) -> tuple[int, list[Any]]:
    raw_total = payload.get("totalAnnouncement")
    if isinstance(raw_total, bool):
        raise ValueError("totalAnnouncement must be a nonnegative integer")
    try:
        total = int(str(raw_total))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "totalAnnouncement must be a nonnegative integer"
        ) from exc
    announcements = payload.get("announcements")
    if total < 0 or not isinstance(announcements, list):
        raise ValueError("official announcement payload is incomplete")
    if total != len(announcements):
        raise ValueError(
            "totalAnnouncement does not match announcements: "
            f"{total} != {len(announcements)}"
        )
    return total, announcements


def _required_text(item: Mapping[str, Any], field: str) -> str:
    value = str(item.get(field, "")).strip()
    if not value:
        raise ValueError(f"official announcement missing {field}")
    return value


def _attachment_url(item: Mapping[str, Any]) -> str:
    path = _required_text(item, "adjunctUrl").lstrip("/")
    return f"{CNINFO_STATIC_URL}{path}"


def _effective_dates(pattern: re.Pattern[str], text: str) -> tuple[date, ...]:
    dates: list[date] = []
    for match in pattern.finditer(text):
        dates.append(
            date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        )
    return tuple(dict.fromkeys(dates))


class CninfoSuspensionEventSource:
    """Extract explicit stock suspension transitions from CNINFO attachments."""

    def __init__(
        self,
        announcement_fetcher: CninfoDirectFetcher | None = None,
        document_fetcher: OfficialDocumentFetcher | None = None,
    ) -> None:
        self._announcement_fetcher = (
            announcement_fetcher or _default_direct_fetcher
        )
        self._document_fetcher = document_fetcher or _default_document_fetcher

    def fetch_events(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
    ) -> tuple[OfficialSuspensionEvent, ...]:
        """Fetch explicit events; never infer a complete status window."""
        if market is MarketCode.BSE:
            raise SuspensionEventSourceError(
                "CNINFO BSE security-status coverage is not verified"
            )
        if start > end:
            raise SuspensionEventSourceError(
                "suspension event start must not exceed end"
            )

        try:
            payload = self._announcement_fetcher(
                symbol=code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if not isinstance(payload, Mapping):
                raise ValueError("official announcement payload must be an object")
            _, announcements = _parse_total(payload)
            events: list[OfficialSuspensionEvent] = []
            for raw_item in announcements:
                if not isinstance(raw_item, Mapping):
                    raise ValueError("official announcement item must be an object")
                if _required_text(raw_item, "secCode") != code:
                    raise ValueError("official announcement stock code mismatch")
                title = _required_text(raw_item, "announcementTitle")
                wants_start = "停牌" in title and "暂停转股" not in title
                wants_resume = "复牌" in title
                if not wants_start and not wants_resume:
                    continue

                source_url = _attachment_url(raw_item)
                document = self._document_fetcher(source_url)
                transitions: list[tuple[SuspensionEventKind, date]] = []
                if wants_start:
                    transitions.extend(
                        (SuspensionEventKind.FULL_DAY_START, effective_on)
                        for effective_on in _effective_dates(
                            _START_PATTERN,
                            document.text,
                        )
                    )
                if wants_resume:
                    transitions.extend(
                        (SuspensionEventKind.FULL_DAY_RESUME, effective_on)
                        for effective_on in _effective_dates(
                            _RESUME_PATTERN,
                            document.text,
                        )
                    )
                parsed_kinds = {kind for kind, _ in transitions}
                if (
                    (wants_start and SuspensionEventKind.FULL_DAY_START not in parsed_kinds)
                    or (
                        wants_resume
                        and SuspensionEventKind.FULL_DAY_RESUME not in parsed_kinds
                    )
                ):
                    raise ValueError(
                        "official suspension announcement has no explicit "
                        "effective date"
                    )
                events.extend(
                    OfficialSuspensionEvent(
                        code=code,
                        market=market,
                        kind=kind,
                        effective_on=effective_on,
                        source_url=source_url,
                        content_hash=document.content_hash,
                    )
                    for kind, effective_on in transitions
                )
        except SuspensionEventSourceError:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise SuspensionEventSourceError(message) from exc

        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.effective_on,
                    event.kind.value,
                    event.source_url,
                ),
            )
        )


__all__ = [
    "CninfoSuspensionEventSource",
    "OfficialDocument",
    "OfficialSuspensionEvent",
    "SuspensionEventKind",
    "SuspensionEventSourceError",
]

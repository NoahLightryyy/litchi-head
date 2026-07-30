"""Continuous official suspension-status ledger tests."""

from datetime import date, timedelta

import pytest

from src.data.kline import MarketCode
from src.data.kline_calendar import SecurityStatusCoverageError
from src.data.kline_status import (
    OfficialSecurityLifecycleEvidence,
    OfficialSecurityStateCheckpoint,
    OfficialSuspensionEvent,
    OfficialSuspensionEventBatch,
    SecurityTradingState,
    SuspensionEventKind,
    SuspensionStatusLedger,
)


def _lifecycle(
    *,
    listed_on: date = date(2021, 6, 3),
    delisted_on: date | None = None,
) -> OfficialSecurityLifecycleEvidence:
    return OfficialSecurityLifecycleEvidence(
        code="300996",
        market=MarketCode.SZSE,
        listed_on=listed_on,
        delisted_on=delisted_on,
        source_url="https://www.szse.cn/official/lifecycle/300996",
        content_hash="1" * 64,
    )


def _checkpoint(
    *,
    state_on: date = date(2026, 7, 20),
    state: SecurityTradingState = SecurityTradingState.ACTIVE,
    pending_events: tuple[OfficialSuspensionEvent, ...] = (),
) -> OfficialSecurityStateCheckpoint:
    return OfficialSecurityStateCheckpoint(
        code="300996",
        market=MarketCode.SZSE,
        state_on=state_on,
        state=state,
        pending_events=pending_events,
        source_url="ledger://300996/2026-07-20",
        content_hash="2" * 64,
    )


def _event(
    kind: SuspensionEventKind,
    effective_on: date,
    suffix: str,
) -> OfficialSuspensionEvent:
    return OfficialSuspensionEvent(
        code="300996",
        market=MarketCode.SZSE,
        kind=kind,
        effective_on=effective_on,
        source_url=f"https://static.cninfo.com.cn/{suffix}.PDF",
        content_hash=suffix[0] * 64,
    )


def _batch(
    start: date,
    end: date,
    *events: OfficialSuspensionEvent,
    digest: str = "a",
) -> OfficialSuspensionEventBatch:
    return OfficialSuspensionEventBatch(
        code="300996",
        market=MarketCode.SZSE,
        coverage_start=start,
        coverage_end=end,
        events=events,
        source_url="https://www.cninfo.com.cn/new/hisAnnouncement/query",
        content_hash=digest * 64,
    )


def _dates(start: date, end: date) -> tuple[date, ...]:
    return tuple(
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )


def test_builds_window_from_continuous_batches_and_deduplicates_events() -> None:
    start = date(2026, 7, 20)
    end = date(2026, 7, 30)
    first_start = _event(
        SuspensionEventKind.FULL_DAY_START,
        date(2026, 7, 27),
        "a-start",
    )
    repeated_start = _event(
        SuspensionEventKind.FULL_DAY_START,
        date(2026, 7, 27),
        "b-repeat",
    )
    continue_start = _event(
        SuspensionEventKind.FULL_DAY_START,
        date(2026, 7, 29),
        "c-continue",
    )
    resume = _event(
        SuspensionEventKind.FULL_DAY_RESUME,
        date(2026, 7, 30),
        "d-resume",
    )
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(),
        batches=(
            _batch(start, date(2026, 7, 25), digest="3"),
            _batch(
                date(2026, 7, 26),
                end,
                first_start,
                repeated_start,
                continue_start,
                resume,
                digest="4",
            ),
        ),
    )

    window = ledger.build_window(
        start=start,
        end=end,
        market_open_dates=_dates(start, end),
    )

    assert window.coverage_start == start
    assert window.coverage_end == end
    assert window.full_day_suspensions == (
        date(2026, 7, 27),
        date(2026, 7, 28),
        date(2026, 7, 29),
    )
    assert window.intraday_suspensions == ()
    assert set(window.source_urls) == {
        "https://www.szse.cn/official/lifecycle/300996",
        "ledger://300996/2026-07-20",
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        "https://static.cninfo.com.cn/a-start.PDF",
        "https://static.cninfo.com.cn/b-repeat.PDF",
        "https://static.cninfo.com.cn/c-continue.PDF",
        "https://static.cninfo.com.cn/d-resume.PDF",
    }
    assert set(window.source_hashes) == {
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
    }


def test_suspended_checkpoint_excludes_dates_until_resume() -> None:
    start = date(2026, 7, 20)
    end = date(2026, 7, 24)
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(state=SecurityTradingState.SUSPENDED),
        batches=(
            _batch(
                start,
                end,
                _event(
                    SuspensionEventKind.FULL_DAY_RESUME,
                    date(2026, 7, 23),
                    "e-resume",
                ),
            ),
        ),
    )

    window = ledger.build_window(
        start=start,
        end=end,
        market_open_dates=_dates(start, end),
    )

    assert window.full_day_suspensions == (
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
    )


def test_replays_transitions_before_requested_window_to_derive_opening_state() -> None:
    start = date(2026, 7, 20)
    end = date(2026, 7, 24)
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(state_on=date(2026, 7, 1)),
        batches=(
            _batch(
                date(2026, 7, 1),
                end,
                _event(
                    SuspensionEventKind.FULL_DAY_START,
                    date(2026, 7, 17),
                    "5-start",
                ),
                _event(
                    SuspensionEventKind.FULL_DAY_RESUME,
                    date(2026, 7, 23),
                    "6-resume",
                ),
            ),
        ),
    )

    window = ledger.build_window(
        start=start,
        end=end,
        market_open_dates=_dates(start, end),
    )

    assert window.full_day_suspensions == (
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
    )


def test_checkpoint_preserves_announced_but_not_yet_effective_transition() -> None:
    start = date(2026, 7, 26)
    end = date(2026, 7, 30)
    pending_start = _event(
        SuspensionEventKind.FULL_DAY_START,
        date(2026, 7, 27),
        "7-pending",
    )
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(
            state_on=start,
            pending_events=(pending_start,),
        ),
        batches=(
            _batch(
                start,
                end,
                _event(
                    SuspensionEventKind.FULL_DAY_RESUME,
                    date(2026, 7, 30),
                    "d-resume",
                ),
            ),
        ),
    )

    window = ledger.build_window(
        start=start,
        end=end,
        market_open_dates=_dates(start, end),
    )

    assert window.full_day_suspensions == (
        date(2026, 7, 27),
        date(2026, 7, 28),
        date(2026, 7, 29),
    )
    assert pending_start.source_url in window.source_urls
    assert pending_start.content_hash in window.source_hashes


def test_rejects_a_gap_between_official_query_batches() -> None:
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(),
        batches=(
            _batch(date(2026, 7, 20), date(2026, 7, 24)),
            _batch(date(2026, 7, 26), date(2026, 7, 30)),
        ),
    )

    with pytest.raises(SecurityStatusCoverageError, match="continuous"):
        ledger.build_window(
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
            market_open_dates=_dates(
                date(2026, 7, 20),
                date(2026, 7, 30),
            ),
        )


def test_rejects_conflicting_start_and_resume_on_same_effective_date() -> None:
    effective_on = date(2026, 7, 27)
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(),
        batches=(
            _batch(
                date(2026, 7, 20),
                date(2026, 7, 30),
                _event(
                    SuspensionEventKind.FULL_DAY_START,
                    effective_on,
                    "f-start",
                ),
                _event(
                    SuspensionEventKind.FULL_DAY_RESUME,
                    effective_on,
                    "f-resume",
                ),
            ),
        ),
    )

    with pytest.raises(SecurityStatusCoverageError, match="conflicting"):
        ledger.build_window(
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
            market_open_dates=_dates(
                date(2026, 7, 20),
                date(2026, 7, 30),
            ),
        )


def test_rejects_checkpoint_that_does_not_anchor_requested_window() -> None:
    ledger = SuspensionStatusLedger(
        lifecycle=_lifecycle(),
        checkpoint=_checkpoint(state_on=date(2026, 7, 21)),
        batches=(
            _batch(date(2026, 7, 21), date(2026, 7, 30)),
        ),
    )

    with pytest.raises(SecurityStatusCoverageError, match="checkpoint"):
        ledger.build_window(
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
            market_open_dates=_dates(
                date(2026, 7, 20),
                date(2026, 7, 30),
            ),
        )


def test_rejects_batch_or_event_for_another_security() -> None:
    foreign_event = _event(
        SuspensionEventKind.FULL_DAY_START,
        date(2026, 7, 27),
        "9-foreign",
    ).model_copy(update={"code": "600000", "market": MarketCode.SSE})

    with pytest.raises(ValueError, match="identity"):
        OfficialSuspensionEventBatch(
            code="300996",
            market=MarketCode.SZSE,
            coverage_start=date(2026, 7, 20),
            coverage_end=date(2026, 7, 30),
            events=(foreign_event,),
            source_url="https://www.cninfo.com.cn/query",
            content_hash="8" * 64,
        )

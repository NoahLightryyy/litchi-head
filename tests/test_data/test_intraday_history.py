"""TD-072 分时历史影子回填与正式量能基线契约。"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from src.data.intraday import IntradayBarState, IntradayCheckpoint
from src.data.intraday_history import (
    IntradayHistoricalSession,
    IntradayHistoryCoordinator,
    IntradayHistoryStore,
    IntradayHistoryStoreError,
    IntradayHistoryTrust,
)
from src.data.kline import MarketCode
from src.data.providers.intraday_history import TencentIntradayHistorySource

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _regular_clocks() -> tuple[time, ...]:
    morning = (
        tuple(time(9, 30 + minute) for minute in range(30))
        + tuple(time(10, minute) for minute in range(60))
        + tuple(time(11, minute) for minute in range(31))
    )
    afternoon = (
        tuple(time(13, minute) for minute in range(60))
        + tuple(time(14, minute) for minute in range(60))
        + (time(15, 0),)
    )
    return morning + afternoon


def _session(
    trade_date: date,
    *,
    trust: IntradayHistoryTrust,
    volume_scale: int = 1,
    missing_clock: time | None = None,
) -> IntradayHistoricalSession:
    cumulative = 0
    checkpoints: list[IntradayCheckpoint] = []
    for index, clock in enumerate(_regular_clocks(), start=1):
        if clock == missing_clock:
            continue
        cumulative += index * 100 * volume_scale
        checkpoints.append(
            IntradayCheckpoint(
                code="000001",
                timestamp=datetime.combine(trade_date, clock, tzinfo=SHANGHAI),
                close=10.0,
                cumulative_volume=cumulative,
                cumulative_amount=float(cumulative * 10),
                state=IntradayBarState.FINAL,
            )
        )
    return IntradayHistoricalSession(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=trade_date,
        checkpoints=tuple(checkpoints),
        trust=trust,
        source_ids=("tencent-history",)
        if trust is IntradayHistoryTrust.SHADOW
        else (
            "eastmoney-live",
            "tencent-live",
        ),
        fetched_at=datetime(2026, 8, 3, 8, 0, tzinfo=SHANGHAI),
        response_hashes=("a" * 64,),
    )


def test_complete_session_rejects_a_missing_regular_minute() -> None:
    with pytest.raises(ValidationError, match="complete regular-session minute set"):
        _session(
            date(2026, 7, 31),
            trust=IntradayHistoryTrust.SHADOW,
            missing_clock=time(10, 0),
        )


def test_complete_session_rejects_a_zero_volume_suspension_day() -> None:
    with pytest.raises(ValidationError, match="positive completed volume"):
        _session(
            date(2026, 7, 31),
            trust=IntradayHistoryTrust.SHADOW,
            volume_scale=0,
        )


def test_shadow_backfill_is_persisted_but_never_enters_formal_baseline(
    tmp_path: Path,
) -> None:
    store = IntradayHistoryStore(tmp_path)
    store.persist(_session(date(2026, 7, 31), trust=IntradayHistoryTrust.SHADOW))

    assert store.session_dates("000001", trust=IntradayHistoryTrust.SHADOW) == (date(2026, 7, 31),)
    expected_partition = (
        f"market={MarketCode.SZSE.value}/code=000001/trade_date=2026-07-31"
    )
    assert expected_partition in store.member_paths("000001")[0].as_posix()
    assert (
        store.baseline(
            "000001",
            as_of=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
        )
        is None
    )


def test_formal_baseline_uses_median_of_twenty_verified_same_time_sessions(
    tmp_path: Path,
) -> None:
    store = IntradayHistoryStore(tmp_path)
    day = date(2026, 7, 1)
    written = 0
    while written < 20:
        if day.weekday() < 5:
            store.persist(
                _session(
                    day,
                    trust=IntradayHistoryTrust.VERIFIED,
                    volume_scale=written + 1,
                )
            )
            written += 1
        day += timedelta(days=1)

    baseline = store.baseline(
        "000001",
        as_of=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
    )

    assert baseline is not None
    assert baseline.as_of_minute == "10:00"
    assert baseline.sample_days == 20
    # 09:30..10:00 的累计量为 49,600；20 天缩放 1..20 的中位数为 10.5。
    assert baseline.expected_cumulative_volume == 520_800


def test_tampered_parquet_session_fails_closed(tmp_path: Path) -> None:
    store = IntradayHistoryStore(tmp_path)
    store.persist(_session(date(2026, 7, 31), trust=IntradayHistoryTrust.VERIFIED))
    member = store.member_paths("000001")[0]
    member.write_bytes(b"tampered")

    with pytest.raises(IntradayHistoryStoreError, match="hash mismatch"):
        store.baseline(
            "000001",
            as_of=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
        )


def test_tampered_manifest_selector_cannot_relabel_another_stock(
    tmp_path: Path,
) -> None:
    store = IntradayHistoryStore(tmp_path)
    store.persist(_session(date(2026, 7, 31), trust=IntradayHistoryTrust.VERIFIED))
    with sqlite3.connect(tmp_path / "manifest.sqlite3") as connection:
        connection.execute("UPDATE intraday_sessions SET code = '000002'")

    with pytest.raises(IntradayHistoryStoreError, match="selector mismatch"):
        store.baseline(
            "000002",
            as_of=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
        )


def test_tencent_backfill_filters_post_close_rows_and_marks_shadow() -> None:
    rows: list[str] = []
    cumulative_lots = 0
    for index, clock in enumerate(_regular_clocks(), start=1):
        cumulative_lots += index
        rows.append(
            f"{clock.strftime('%H%M')} 10.00 {cumulative_lots} {cumulative_lots * 1000:.2f}"
        )
    rows.append("1530 10.00 999999 9999999.00")
    payload = {
        "code": 0,
        "data": {
            "sz000001": {
                "data": [
                    {"date": "20260731", "data": rows, "prec": "10.00"},
                    {"date": "20260803", "data": ["0930 10.00 0 0.00"]},
                ]
            }
        },
    }
    source = TencentIntradayHistorySource(
        fetcher=lambda _code: json.dumps(payload).encode(),
        now_provider=lambda: datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
    )

    sessions = source.fetch("000001")

    assert len(sessions) == 1
    assert sessions[0].trust is IntradayHistoryTrust.SHADOW
    assert len(sessions[0].checkpoints) == 242
    assert sessions[0].checkpoints[-1].timestamp.time() == time(15, 0)
    assert sessions[0].checkpoints[-1].cumulative_volume == cumulative_lots * 100


def test_coordinator_exposes_shadow_only_state_without_using_it_as_baseline(
    tmp_path: Path,
) -> None:
    shadow = _session(date(2026, 7, 31), trust=IntradayHistoryTrust.SHADOW)

    class BackfillSource:
        def fetch(self, _code: str) -> tuple[IntradayHistoricalSession, ...]:
            return (shadow,)

    coordinator = IntradayHistoryCoordinator(
        IntradayHistoryStore(tmp_path),
        backfill_source=BackfillSource(),
    )

    prepared = coordinator.prepare(
        "000001",
        as_of=datetime(2026, 8, 3, 10, 0, tzinfo=SHANGHAI),
        verified_series=(),
    )

    assert prepared.baseline is None
    assert "relative_volume_backfill_shadow_only" in prepared.limitations

"""L1 分时战况的确定性计算与证据边界。"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.data.intraday import (
    IntradayBar,
    IntradayBarState,
    IntradayBattlefieldEngine,
    TimeOfDayVolumeBaseline,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
SESSION_START = datetime(2026, 7, 29, 9, 30, tzinfo=SHANGHAI)


def _bar(
    minute: int,
    *,
    close: float,
    volume: int = 1_000,
    amount: float | None = None,
    state: IntradayBarState = IntradayBarState.FINAL,
) -> IntradayBar:
    return IntradayBar(
        code="000001",
        timestamp=SESSION_START + timedelta(minutes=minute),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        amount=amount if amount is not None else close * volume,
        state=state,
    )


def test_snapshot_uses_live_vwap_and_keeps_current_provisional_bar() -> None:
    bars = [
        _bar(0, close=10.00, volume=1_000),
        _bar(1, close=10.10, volume=2_000),
        _bar(
            2,
            close=10.20,
            volume=1_000,
            state=IntradayBarState.PROVISIONAL,
        ),
    ]

    snapshot = IntradayBattlefieldEngine().analyze(bars)

    assert snapshot.evidence_level == "L1"
    assert snapshot.current_price == 10.20
    assert snapshot.current_bar_state is IntradayBarState.PROVISIONAL
    assert snapshot.session_vwap == 10.10
    assert snapshot.vwap_position == "above"
    assert "current_bar_provisional" in snapshot.limitations


def test_opening_range_requires_the_complete_first_thirty_minutes() -> None:
    complete_opening_range = [
        _bar(minute, close=10.00 + minute / 100) for minute in range(30)
    ]

    complete = IntradayBattlefieldEngine().analyze(complete_opening_range)
    incomplete = IntradayBattlefieldEngine().analyze(complete_opening_range[:-1])

    assert complete.opening_range_high == 10.29
    assert complete.opening_range_low == 10.00
    assert incomplete.opening_range_high is None
    assert incomplete.opening_range_low is None
    assert "opening_range_incomplete" in incomplete.limitations


def test_relative_volume_requires_twenty_same_time_historical_sessions() -> None:
    bars = [_bar(0, close=10.00, volume=1_000), _bar(1, close=10.01, volume=2_000)]
    mature_baseline = TimeOfDayVolumeBaseline(
        as_of_minute="09:31",
        sample_days=20,
        expected_cumulative_volume=2_000,
    )
    immature_baseline = mature_baseline.model_copy(update={"sample_days": 19})

    mature = IntradayBattlefieldEngine().analyze(bars, volume_baseline=mature_baseline)
    immature = IntradayBattlefieldEngine().analyze(
        bars,
        volume_baseline=immature_baseline,
    )

    assert mature.relative_volume == 1.5
    assert mature.relative_volume_sample_days == 20
    assert immature.relative_volume is None
    assert "relative_volume_baseline_insufficient" in immature.limitations


def test_l1_output_never_claims_trader_identity() -> None:
    snapshot = IntradayBattlefieldEngine().analyze(
        [_bar(0, close=10.00), _bar(1, close=10.10)]
    )

    serialized = snapshot.model_dump_json()

    assert snapshot.attribution_supported is False
    assert "主力" not in serialized
    assert "量化" not in serialized
    assert "机构" not in serialized
    assert "identity_attribution_unavailable_at_l1" in snapshot.limitations


def test_vwap_uses_share_volume_not_upstream_board_lots() -> None:
    snapshot = IntradayBattlefieldEngine().analyze(
        [
            _bar(
                0,
                close=11.19,
                volume=450_700,
                amount=5_043_333.00,
            )
        ]
    )

    assert snapshot.session_vwap == 11.19

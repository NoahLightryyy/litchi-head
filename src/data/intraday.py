"""L1 分时战况的标准化模型与确定性计算。

这里只计算市场数据能够直接支持的事实，不推断主力、机构或程序化账户身份。
"""

from __future__ import annotations

from datetime import datetime, time
from enum import Enum
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

SHANGHAI = ZoneInfo("Asia/Shanghai")


class IntradayBarState(str, Enum):
    """分钟条是否已经结束。"""

    FINAL = "final"
    PROVISIONAL = "provisional"


class IntradayBar(BaseModel):
    """一个来源无关的 A 股一分钟行情条。"""

    code: str = Field(pattern=r"^\d{6}$")
    timestamp: datetime
    open: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    low: float = Field(ge=0.0)
    close: float = Field(ge=0.0)
    volume: int = Field(ge=0, description="本分钟成交股数")
    amount: float = Field(ge=0.0, description="本分钟成交额（元）")
    state: IntradayBarState

    @model_validator(mode="after")
    def validate_bar(self) -> "IntradayBar":
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low and high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low and high")
        return self


class TimeOfDayVolumeBaseline(BaseModel):
    """过去交易日相同盘中时刻的累计成交量基线。"""

    as_of_minute: str = Field(pattern=r"^\d{2}:\d{2}$")
    sample_days: int = Field(ge=1)
    expected_cumulative_volume: float = Field(gt=0.0)


class IntradayBattlefieldSnapshot(BaseModel):
    """交给界面或后续业务节点的 L1 分时战况快照。"""

    code: str
    evidence_level: Literal["L1"] = "L1"
    as_of: datetime
    current_price: float
    current_bar_state: IntradayBarState
    session_vwap: float | None
    vwap_deviation_pct: float | None
    vwap_position: Literal["above", "at", "below", "unavailable"]
    opening_range_high: float | None
    opening_range_low: float | None
    cumulative_volume: int
    relative_volume: float | None
    relative_volume_sample_days: int | None
    attribution_supported: Literal[False] = False
    limitations: list[str] = Field(default_factory=list)


class IntradayBattlefieldEngine:
    """用规范分钟条生成不依赖 LLM 的实时战况快照。"""

    def analyze(
        self,
        bars: list[IntradayBar],
        *,
        volume_baseline: TimeOfDayVolumeBaseline | None = None,
    ) -> IntradayBattlefieldSnapshot:
        if not bars:
            raise ValueError("at least one intraday bar is required")

        ordered = sorted(bars, key=lambda bar: bar.timestamp)
        self._validate_series(ordered)
        latest = ordered[-1]
        cumulative_volume = sum(bar.volume for bar in ordered)
        cumulative_amount = sum(bar.amount for bar in ordered)
        session_vwap = (
            round(cumulative_amount / cumulative_volume, 6)
            if cumulative_volume > 0
            else None
        )

        if session_vwap is None or session_vwap == 0:
            vwap_position: Literal["above", "at", "below", "unavailable"] = (
                "unavailable"
            )
            vwap_deviation_pct = None
        else:
            difference = latest.close - session_vwap
            vwap_position = (
                "at"
                if abs(difference) < 1e-9
                else "above"
                if difference > 0
                else "below"
            )
            vwap_deviation_pct = round(difference / session_vwap * 100, 6)

        opening_range = self._opening_range(ordered)
        limitations = ["identity_attribution_unavailable_at_l1"]
        if latest.state is IntradayBarState.PROVISIONAL:
            limitations.append("current_bar_provisional")
        if opening_range is None:
            limitations.append("opening_range_incomplete")

        relative_volume: float | None = None
        relative_volume_sample_days: int | None = None
        latest_minute = latest.timestamp.astimezone(SHANGHAI).strftime("%H:%M")
        if volume_baseline is None:
            limitations.append("relative_volume_baseline_unavailable")
        elif volume_baseline.sample_days < 20:
            limitations.append("relative_volume_baseline_insufficient")
        elif volume_baseline.as_of_minute != latest_minute:
            limitations.append("relative_volume_baseline_time_mismatch")
        else:
            relative_volume = round(
                cumulative_volume / volume_baseline.expected_cumulative_volume,
                6,
            )
            relative_volume_sample_days = volume_baseline.sample_days

        return IntradayBattlefieldSnapshot(
            code=latest.code,
            as_of=latest.timestamp,
            current_price=latest.close,
            current_bar_state=latest.state,
            session_vwap=session_vwap,
            vwap_deviation_pct=vwap_deviation_pct,
            vwap_position=vwap_position,
            opening_range_high=opening_range[0] if opening_range else None,
            opening_range_low=opening_range[1] if opening_range else None,
            cumulative_volume=cumulative_volume,
            relative_volume=relative_volume,
            relative_volume_sample_days=relative_volume_sample_days,
            limitations=limitations,
        )

    @staticmethod
    def _validate_series(bars: list[IntradayBar]) -> None:
        codes = {bar.code for bar in bars}
        local_dates = {
            bar.timestamp.astimezone(SHANGHAI).date()
            for bar in bars
        }
        timestamps = {bar.timestamp for bar in bars}
        if len(codes) != 1:
            raise ValueError("all intraday bars must belong to one instrument")
        if len(local_dates) != 1:
            raise ValueError("all intraday bars must belong to one Shanghai session")
        if len(timestamps) != len(bars):
            raise ValueError("intraday bars must have unique timestamps")

    @staticmethod
    def _opening_range(
        bars: list[IntradayBar],
    ) -> tuple[float, float] | None:
        by_clock = {
            bar.timestamp.astimezone(SHANGHAI).time().replace(tzinfo=None): bar
            for bar in bars
            if bar.state is IntradayBarState.FINAL
        }
        expected_clocks = {
            time(9, minute)
            for minute in range(30, 60)
        }
        if not expected_clocks.issubset(by_clock):
            return None
        opening_bars = [by_clock[clock] for clock in sorted(expected_clocks)]
        return (
            max(bar.high for bar in opening_bars),
            min(bar.low for bar in opening_bars),
        )


__all__ = [
    "IntradayBar",
    "IntradayBarState",
    "IntradayBattlefieldEngine",
    "IntradayBattlefieldSnapshot",
    "TimeOfDayVolumeBaseline",
]

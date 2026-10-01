"""Five-session minute display, isolated from verified history and AI evidence."""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.data.intraday_history import REGULAR_SESSION_CLOCKS
from src.data.kline import market_code_for
from src.data.kline_calendar import official_a_share_calendar_2026
from src.data.providers.intraday_history import SHANGHAI, _default_fetcher

logger = logging.getLogger(__name__)


class MinuteDisplayPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    timestamp: datetime
    close: float = Field(gt=0)


class FiveDayDisplay(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    source: Literal["tencent"] = "tencent"
    price_basis: Literal["unverified_raw"] = "unverified_raw"
    verification: Literal["single_source"] = "single_source"
    status: Literal["partial", "empty", "failed"]
    fetched_at: datetime
    days: list[date] = Field(default_factory=list)
    points: list[MinuteDisplayPoint] = Field(default_factory=list)
    incomplete_days: list[date] = Field(default_factory=list)
    missing_days: list[date] = Field(default_factory=list)
    error_code: str | None = None


def parse_five_day(raw: bytes, symbol: str, now: datetime) -> FiveDayDisplay:
    payload = json.loads(raw)
    prefix = {"SSE": "sh", "SZSE": "sz", "BSE": "bj"}[market_code_for(symbol).value]
    if payload.get("code") != 0:
        raise ValueError("invalid minute history response")
    rows = payload.get("data", {}).get(prefix + symbol, {}).get("data")
    if not isinstance(rows, list):
        raise ValueError("missing symbol minute history")
    clocks = {c.strftime("%H%M") for c in REGULAR_SESSION_CLOCKS}
    points: list[MinuteDisplayPoint] = []
    days: list[date] = []
    incomplete: list[date] = []
    calendar = official_a_share_calendar_2026()
    for day in rows:
        trade_date = datetime.strptime(day["date"], "%Y%m%d").date()
        if trade_date in days or trade_date > now.date() or not calendar.open_dates(
            market_code_for(symbol), trade_date, trade_date
        ):
            raise ValueError("invalid or duplicate trading date")
        if not isinstance(day.get("data"), list):
            raise ValueError("invalid minute rows")
        seen: set[str] = set()
        daily: list[MinuteDisplayPoint] = []
        for row in day["data"]:
            fields = row.split()
            if not fields or fields[0] not in clocks:
                continue  # only regular trading hours; no synthetic overnight minutes
            if len(fields) < 2 or fields[0] in seen:
                raise ValueError("invalid or duplicate minute")
            seen.add(fields[0])
            stamp = datetime.combine(trade_date,
                datetime.strptime(fields[0], "%H%M").time(), tzinfo=SHANGHAI)
            if stamp > now:
                raise ValueError("future minute")
            daily.append(MinuteDisplayPoint(timestamp=stamp, close=float(fields[1])))
        if not daily:
            raise ValueError("empty session")
        days.append(trade_date)
        points.extend(daily)
        if seen != clocks:
            incomplete.append(trade_date)
    days = sorted(days)[-5:]
    points = sorted((p for p in points if p.timestamp.date() in days), key=lambda p: p.timestamp)
    missing = sorted(set(calendar.open_dates(market_code_for(symbol), days[0], days[-1]))
                     - set(days)) if days else []
    return FiveDayDisplay(symbol=symbol, status="partial" if points else "empty", fetched_at=now,
                          days=days, points=points,
                          incomplete_days=[d for d in incomplete if d in days],
                          missing_days=missing)


_cache: dict[str, tuple[float, FiveDayDisplay]] = {}
_lock = Lock()


def get_five_day_display(symbol: str) -> FiveDayDisplay:
    now = datetime.now(SHANGHAI)
    if not _lock.acquire(timeout=1):
        return FiveDayDisplay(symbol=symbol, status="failed", fetched_at=now, error_code="BUSY")
    try:
        cached = _cache.get(symbol)
        if cached and time.monotonic() < cached[0]:
            return cached[1]
        result = parse_five_day(_default_fetcher(symbol), symbol, now)
        if result.points:
            if len(_cache) >= 32:
                _cache.pop(next(iter(_cache)))
            _cache[symbol] = (time.monotonic() + 30, result)
        return result
    except Exception:
        logger.exception("Five-day display unavailable: %s", symbol)
        return FiveDayDisplay(symbol=symbol, status="failed", fetched_at=now,
                              error_code="FIVE_DAY_UNAVAILABLE")
    finally:
        _lock.release()

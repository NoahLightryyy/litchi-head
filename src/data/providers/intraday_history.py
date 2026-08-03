"""腾讯五日分钟历史的影子回填适配器。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.data.intraday import IntradayBarState, IntradayCheckpoint
from src.data.intraday_history import (
    REGULAR_SESSION_CLOCKS,
    IntradayHistoricalSession,
    IntradayHistoryTrust,
)
from src.data.kline import market_code_for
from src.data.kline_calendar import (
    OfficialTradingCalendar,
    official_a_share_calendar_2026,
)
from src.data.providers.quotes import USER_AGENT, _market_prefix

SHANGHAI = ZoneInfo("Asia/Shanghai")
TENCENT_INTRADAY_HISTORY_URL = "https://web.ifzq.gtimg.cn/appstock/app/day/query"


def _default_fetcher(code: str) -> bytes:
    import httpx

    symbol = f"{_market_prefix(code)}{code}"
    response = httpx.get(
        TENCENT_INTRADAY_HISTORY_URL,
        params={"code": symbol},
        headers={"User-Agent": USER_AGENT, "Referer": "https://gu.qq.com/"},
        timeout=10.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


class TencentIntradayHistorySource:
    """只进入影子层；不能单独生成正式 Relative Volume。"""

    def __init__(
        self,
        *,
        fetcher: Callable[[str], bytes] = _default_fetcher,
        now_provider: Callable[[], datetime] = lambda: datetime.now(SHANGHAI),
        calendar: OfficialTradingCalendar | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._now_provider = now_provider
        self._calendar = calendar or official_a_share_calendar_2026()

    def fetch(self, code: str) -> tuple[IntradayHistoricalSession, ...]:
        raw = self._fetcher(code)
        payload: Any = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("code") != 0:
            raise ValueError("Tencent intraday history response is invalid")
        symbol = f"{_market_prefix(code)}{code}"
        all_data = payload.get("data")
        symbol_data = all_data.get(symbol) if isinstance(all_data, Mapping) else None
        days = symbol_data.get("data") if isinstance(symbol_data, Mapping) else None
        if not isinstance(days, list):
            raise ValueError("Tencent intraday history days are missing")
        now = self._now_provider()
        if now.tzinfo is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        today = now.astimezone(SHANGHAI).date()
        required = {clock.strftime("%H%M") for clock in REGULAR_SESSION_CLOCKS}
        response_hash = hashlib.sha256(raw).hexdigest()
        sessions: list[IntradayHistoricalSession] = []
        for item in days:
            if not isinstance(item, Mapping):
                raise ValueError("Tencent intraday history day must be an object")
            trade_date = datetime.strptime(str(item.get("date", "")), "%Y%m%d").date()
            if trade_date >= today:
                continue
            market = market_code_for(code)
            if trade_date not in self._calendar.open_dates(market, trade_date, trade_date):
                raise ValueError("Tencent intraday history contains a non-trading date")
            rows = item.get("data")
            if not isinstance(rows, list):
                raise ValueError("Tencent intraday history rows are missing")
            checkpoints: list[IntradayCheckpoint] = []
            seen: set[str] = set()
            for row in rows:
                fields = str(row).split()
                if len(fields) < 4 or fields[0] not in required:
                    continue
                if fields[0] in seen:
                    raise ValueError("Tencent intraday history contains duplicate minutes")
                seen.add(fields[0])
                clock = datetime.strptime(fields[0], "%H%M").time()
                checkpoints.append(
                    IntradayCheckpoint(
                        code=code,
                        timestamp=datetime.combine(trade_date, clock, tzinfo=SHANGHAI),
                        close=float(fields[1]),
                        cumulative_volume=int(fields[2]) * 100,
                        cumulative_amount=float(fields[3]),
                        state=IntradayBarState.FINAL,
                    )
                )
            sessions.append(
                IntradayHistoricalSession(
                    code=code,
                    market=market,
                    trade_date=trade_date,
                    checkpoints=tuple(checkpoints),
                    trust=IntradayHistoryTrust.SHADOW,
                    source_ids=("direct-tencent-intraday-history",),
                    fetched_at=now,
                    response_hashes=(response_hash,),
                    price_adjustment="unverified_raw",
                )
            )
        return tuple(sorted(sessions, key=lambda session: session.trade_date))


__all__ = ["TencentIntradayHistorySource"]

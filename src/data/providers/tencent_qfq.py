"""Current-provider QFQ prices from the already used Tencent daily endpoint.

Not an official corporate-action audit or point-in-time backtest series. Volume
is intentionally excluded: price adjustment does not prove share adjustment.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.data.kline import market_code_for
from src.data.providers.kline import KLINE_TIMEOUT_SECONDS, TENCENT_RAW_DAILY_URL


class ProviderQfqBar(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    code: str = Field(pattern=r"^\d{6}$")
    trade_date: date
    price_basis: Literal["provider_qfq_current"] = "provider_qfq_current"
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def valid_ohlc(self) -> ProviderQfqBar:
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid QFQ OHLC")
        return self


def _symbol(code: str) -> str:
    market = market_code_for(code)
    return {"SSE": "sh", "SZSE": "sz", "BSE": "bj"}[market.value] + code


def parse_qfq_daily(
    payload: Any, code: str, start: date, end: date, now: datetime
) -> list[ProviderQfqBar]:
    if now.tzinfo is None:
        raise ValueError("Aware collection time required")
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ValueError("Tencent QFQ response rejected")
    data = payload.get("data")
    symbol_data = data.get(_symbol(code)) if isinstance(data, dict) else None
    rows = symbol_data.get("qfqday") if isinstance(symbol_data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("No explicit QFQ series for requested identity")
    result: list[ProviderQfqBar] = []
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("Malformed QFQ row")
        bar = ProviderQfqBar(
            code=code, trade_date=row[0], open=row[1], close=row[2], high=row[3], low=row[4]
        )
        if not start <= bar.trade_date <= end or bar.trade_date >= today:
            raise ValueError("QFQ row outside completed requested window")
        if result and bar.trade_date <= result[-1].trade_date:
            raise ValueError("QFQ dates must be unique and increasing")
        result.append(bar)
    return result


def fetch_qfq_daily(
    code: str, start: date, end: date
) -> tuple[list[ProviderQfqBar], datetime, str]:
    symbol = _symbol(code)
    response = httpx.get(
        TENCENT_RAW_DAILY_URL,
        params={"param": f"{symbol},day,{start.isoformat()},{end.isoformat()},260,qfq"},
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"},
        timeout=KLINE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    fetched_at = datetime.now(ZoneInfo("Asia/Shanghai"))
    return (
        parse_qfq_daily(response.json(), code, start, end, fetched_at),
        fetched_at,
        hashlib.sha256(response.content).hexdigest(),
    )

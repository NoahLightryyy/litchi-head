"""ETF RAW daily display with fund precision and independently usable sources."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from backend.etf_contract import (
    EtfDailyBar,
    EtfIdentity,
    EtfKlineDiagnostic,
    EtfKlineDisplay,
    EtfKlineSource,
)
from src.data.kline import MarketCode, RawDailyBar
from src.data.providers.kline import (
    SINA_RAW_DAILY_URL,
    TENCENT_RAW_DAILY_URL,
    _decimal,
    _integer,
    _sina_payload,
    _tencent_rows,
)
from src.data.providers.quotes import SHANGHAI

logger = logging.getLogger(__name__)
TOTAL_TIMEOUT = 10.0
SOURCE_TIMEOUT = 4.0
_slots = asyncio.Semaphore(4)
_LIMITATIONS = [
    "不复权场内交易价格，不是基金净值；成交量单位为份。",
    "仅展示北京时间昨日及之前行情，覆盖以返回日期为准；单源数据未作跨源校验。",
]


def _bar(identity: EtfIdentity, trade_date: date, values: list[Any], source: EtfKlineSource
         ) -> EtfDailyBar:
    # Reuse the existing RAW invariants, overriding only the ETF price tick.
    # Tencent reports lots (100 fund units); Sina reports individual fund units.
    volume = _decimal(values[4], "volume") * (100 if source == "tencent" else 1)
    raw = RawDailyBar(
        code=identity.code,
        market=MarketCode.SSE if identity.exchange == "SH" else MarketCode.SZSE,
        trade_date=trade_date,
        open=_decimal(values[0], "open"), close=_decimal(values[1], "close"),
        high=_decimal(values[2], "high"), low=_decimal(values[3], "low"),
        price_tick=Decimal("0.001"), volume=_integer(volume, "fund_units"),
        volume_precision=100 if source == "tencent" else 1,
    )
    return EtfDailyBar(
        date=raw.trade_date, open=float(raw.open), close=float(raw.close),
        high=float(raw.high), low=float(raw.low), volume=raw.volume,
    )


def parse_etf_bars(
    response: httpx.Response, source: EtfKlineSource, identity: EtfIdentity,
    start: date, end: date, today: date,
) -> list[EtfDailyBar]:
    """Bind the provider payload to the catalog symbol, never guess its exchange."""
    if len(response.content) > 2_000_000:
        raise ValueError("ETF daily response too large")
    if source == "tencent":
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ETF daily response must be an object")
        rows = _tencent_rows(payload, expected_symbol=identity.symbol)
        dated_values = [(row[0], row[1:6]) for row in rows]
    else:
        sina_rows = _sina_payload(response.text, expected_symbol=identity.symbol)
        dated_values = [(row.get("day"), [row.get(field) for field in
                         ("open", "close", "high", "low", "volume")]) for row in sina_rows]
    bars: list[EtfDailyBar] = []
    previous: date | None = None
    for stamp, values in dated_values:
        trade_date = date.fromisoformat(str(stamp))
        if trade_date > today or (previous is not None and trade_date <= previous):
            raise ValueError("ETF daily dates are future, duplicated or unordered")
        previous = trade_date
        if source == "tencent" and not start <= trade_date <= end:
            raise ValueError("ETF daily response does not match requested window")
        # Sina returns a recent tail, which may contain older days and today's open session.
        if start <= trade_date <= end:
            bars.append(_bar(identity, trade_date, values, source))
    return bars


def _result(
    identity: EtfIdentity, now: datetime, start: date, end: date,
    diagnostics: list[EtfKlineDiagnostic], bars: list[EtfDailyBar] | None = None,
    source: EtfKlineSource | None = None,
) -> EtfKlineDisplay:
    bars = bars or []
    return EtfKlineDisplay(
        identity=identity, fetched_at=now, requested_start=start, requested_end=end,
        status="ready" if bars else (
            "unavailable" if any(item.status == "failed" for item in diagnostics) else "empty"
        ),
        source=source, bars=bars, data_start=bars[0].date if bars else None,
        data_end=bars[-1].date if bars else None, diagnostics=diagnostics,
        limitations=_LIMITATIONS,
    )


async def get_etf_kline(
    identity: EtfIdentity, days: int = 90, *,
    transport: httpx.AsyncBaseTransport | None = None, now: datetime | None = None,
) -> EtfKlineDisplay:
    """Return the first usable source within 10s; no stock defaults or paid calls."""
    if not 30 <= days <= 730:
        raise ValueError("ETF daily range must be between 30 and 730 calendar days")
    now = now or datetime.now(SHANGHAI)
    if now.tzinfo is None:
        raise ValueError("ETF daily clock must include timezone")
    now = now.astimezone(SHANGHAI)
    end = now.date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    diagnostics: list[EtfKlineDiagnostic] = []

    async def load() -> EtfKlineDisplay:
        async with _slots, httpx.AsyncClient(
            transport=transport, timeout=SOURCE_TIMEOUT, follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
        ) as client:
            for source in ("tencent", "sina"):
                try:
                    if source == "tencent":
                        url = TENCENT_RAW_DAILY_URL
                        params = {"param": f"{identity.symbol},day,{start},{end},{days + 10},"}
                    else:
                        count = min(days * 2 + 10, 1023)
                        url = SINA_RAW_DAILY_URL.format(symbol=identity.symbol, datalen=count)
                        params = {"symbol": identity.symbol, "scale": "240", "ma": "no",
                                  "datalen": str(count)}
                    response = await asyncio.wait_for(
                        client.get(url, params=params), SOURCE_TIMEOUT,
                    )
                    response.raise_for_status()
                    bars = parse_etf_bars(response, source, identity, start, end, now.date())
                except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError) as exc:
                    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                        error = "request_timeout"
                    elif isinstance(exc, httpx.HTTPError):
                        error = "upstream_request_failed"
                    else:
                        error = "invalid_upstream_payload"
                    logger.warning("ETF daily unavailable: symbol=%s source=%s error=%s",
                                   identity.symbol, source, error)
                    diagnostics.append(EtfKlineDiagnostic(source=source, status="failed",
                                                         error_code=error))
                    continue
                diagnostics.append(EtfKlineDiagnostic(source=source,
                                                     status="success" if bars else "empty"))
                if bars:
                    return _result(identity, now, start, end, diagnostics, bars, source)
            return _result(identity, now, start, end, diagnostics)

    try:
        return await asyncio.wait_for(load(), TOTAL_TIMEOUT)
    except TimeoutError:
        logger.warning("ETF daily total deadline reached: symbol=%s", identity.symbol)
        attempted = {item.source for item in diagnostics}
        diagnostics.extend(
            EtfKlineDiagnostic(source=source, status="failed", error_code="request_timeout")
            for source in ("tencent", "sina") if source not in attempted
        )
        return _result(identity, now, start, end, diagnostics)

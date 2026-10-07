"""Period-specific rankings. Never re-rank today's winners as historical winners."""

from __future__ import annotations

import asyncio
import logging
import math
import re
import sqlite3
import time
from datetime import date, datetime
from datetime import time as day_time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from backend.async_utils import run_sync
from src.data.kline import MarketCode
from src.data.kline_calendar import official_a_share_calendar_2026
from src.data.providers.quotes import SHANGHAI

logger = logging.getLogger(__name__)
router = APIRouter()
Metric = Literal["change", "main_net", "gross_in"]
Period = Literal["latest", "previous", "3", "5", "10", "20", "60"]
FIELDS: dict[str, dict[str, str]] = {
    "change": {"latest": "f3", "3": "f127", "5": "f109", "10": "f160", "60": "f24"},
    "main_net": {"latest": "f62", "3": "f267", "5": "f164", "10": "f174"},
}
SCOPE = "东方财富沪深A股候选榜前50项；不含完整北交所市场，单源未交叉验证"


class RankingRow(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    code: str
    name: str
    value: float
    price: float | None = None
    quoted_at: datetime


class RankingResult(BaseModel):
    metric: Metric
    period: Period
    status: Literal["ready", "partial", "unavailable"]
    data: list[RankingRow] = []
    start_date: date | None = None
    end_date: date | None = None
    fetched_at: datetime
    source: str = "eastmoney"
    scope: str = SCOPE
    unit: Literal["percent", "CNY"]
    cached: bool = False
    reason: str = ""


def expected_window(period: Period, now: datetime) -> tuple[date, date]:
    local = now.astimezone(SHANGHAI)
    calendar = official_a_share_calendar_2026()
    days = list(calendar.open_dates(MarketCode.SSE, date(local.year, 1, 1), local.date()))
    if days and days[-1] == local.date() and local.time() < day_time(9, 15):
        days.pop()
    if period == "previous":
        days = days[:-1]
    count = 1 if period in {"latest", "previous"} else int(period)
    if len(days) < count:
        raise ValueError("交易日历覆盖不足，无法核验统计区间")
    return days[-count], days[-1]


def number(value: object) -> float | None:
    try:
        result = float(str(value))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_rankings(payload: dict, metric: Metric, period: Period, now: datetime) -> RankingResult:
    start, end = expected_window(period, now)
    field = FIELDS[metric][period]
    block = payload.get("data")
    raw = block.get("diff") if isinstance(block, dict) else None
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list) or not raw:
        raise ValueError("来源返回空榜单")
    rows: dict[str, RankingRow] = {}
    rejected = 0
    for item in raw:
        if not isinstance(item, dict):
            rejected += 1
            continue
        value, stamp = number(item.get(field)), number(item.get("f124"))
        code, name = str(item.get("f12", "")), str(item.get("f14", "")).strip()
        try:
            quoted = datetime.fromtimestamp(stamp or 0, SHANGHAI)
        except (ValueError, OverflowError, OSError):
            rejected += 1
            continue
        if (
            not re.fullmatch(r"\d{6}", code)
            or not name
            or value is None
            or stamp is None
            or quoted > now
            or quoted.date() != end
            or code in rows
        ):
            rejected += 1
            continue
        price = number(item.get("f2"))
        rows[code] = RankingRow(
            code=code,
            name=name,
            value=value,
            price=price if price is not None and price > 0 else None,
            quoted_at=quoted,
        )
    if not rows:
        raise ValueError("没有日期与所选区间一致的有效排行数据")
    return RankingResult(
        metric=metric,
        period=period,
        status="partial" if rejected else "ready",
        data=sorted(rows.values(), key=lambda row: (-row.value, row.code)),
        start_date=start,
        end_date=end,
        fetched_at=now,
        unit="percent" if metric == "change" else "CNY",
        reason=f"{rejected}项无效、重复或日期不符，已排除" if rejected else "",
    )


class RankingStore:
    def __init__(self, path: Path = Path("data/discovery/rankings.db")) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS rankings "
            "(metric TEXT, period TEXT, day TEXT, body TEXT, "
            "PRIMARY KEY(metric,period,day))"
        )
        return connection

    def save(self, result: RankingResult) -> None:
        # Only completed, same-day observations can become a previous-day snapshot.
        if not result.end_date or any(row.quoted_at.time() < day_time(15) for row in result.data):
            return
        connection = self.connect()
        try:
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO rankings VALUES (?,?,?,?)",
                    (result.metric, result.period, str(result.end_date), result.model_dump_json()),
                )
        finally:
            connection.close()

    def get(self, metric: Metric, period: Period, day: date) -> RankingResult | None:
        connection = self.connect()
        try:
            row = connection.execute(
                "SELECT body FROM rankings WHERE metric=? AND period=? AND day=?",
                (metric, period, str(day)),
            ).fetchone()
        finally:
            connection.close()
        if not row:
            return None
        result = RankingResult.model_validate_json(row[0])
        if result.metric != metric or result.period != period or result.end_date != day:
            raise ValueError("排行历史身份不一致")
        return result.model_copy(update={"cached": True})


store = RankingStore()
_cache: dict[tuple[str, str], tuple[float, RankingResult]] = {}
_locks: dict[tuple[str, str], asyncio.Lock] = {}


def unavailable(metric: Metric, period: Period, now: datetime, reason: str) -> RankingResult:
    try:
        start, end = expected_window(period, now)
    except ValueError:
        start = end = None
    return RankingResult(
        metric=metric,
        period=period,
        status="unavailable",
        fetched_at=now,
        start_date=start,
        end_date=end,
        unit="percent" if metric == "change" else "CNY",
        reason=reason,
    )


def fetch_rankings(metric: Metric, period: Period, now: datetime) -> RankingResult:
    _, end = expected_window(period, now)
    if metric == "gross_in":
        return unavailable(
            metric, period, now, "当前来源没有可核验的个股总流入字段；净流入不能反推总流入。"
        )
    if period == "previous":
        saved = store.get(metric, "latest", end)
        if saved:
            return saved.model_copy(
                update={"period": "previous", "reason": "已保存的上一交易日收盘榜单"}
            )
        return unavailable(
            metric, period, now, "尚未采集到上一交易日收盘榜单；不以今日候选回算替代历史榜。"
        )
    field = FIELDS.get(metric, {}).get(period)
    if not field:
        return unavailable(
            metric, period, now, "来源未提供此区间排行，历史数据尚不足以核验该周期。"
        )
    params = {
        "fid": field,
        "po": "1",
        "pz": "50",
        "pn": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": f"f12,f14,f2,{field},f124",
    }
    for host in ("push2.eastmoney.com", "push2delay.eastmoney.com"):
        try:
            response = httpx.get(f"https://{host}/api/qt/clist/get", params=params, timeout=8)
            response.raise_for_status()
            result = parse_rankings(response.json(), metric, period, now)
            if host.startswith("push2delay"):
                result.reason = "来源为东方财富延迟行情。" + result.reason
            return result
        except Exception as exc:
            logger.warning(
                "Ranking source failed: metric=%s period=%s host=%s error=%s",
                metric,
                period,
                host,
                type(exc).__name__,
            )
    saved = store.get(metric, period, end)
    if saved:
        return saved.model_copy(
            update={"status": "partial", "reason": "刷新失败，保留该周期已保存收盘榜单"}
        )
    return unavailable(
        metric, period, now, "当前无法取得东方财富排行数据，请稍后重试。"
    )


@router.get("/rankings", response_model=RankingResult)
async def rankings(
    metric: Metric = "change", period: Period = "latest", refresh: bool = False
) -> RankingResult:
    now = datetime.now(SHANGHAI)
    key = (metric, period)
    async with _locks.setdefault(key, asyncio.Lock()):
        cached = _cache.get(key)
        if not refresh and cached and time.monotonic() - cached[0] < 120:
            return cached[1].model_copy(update={"cached": True})
        try:
            result = await run_sync(fetch_rankings, metric, period, now)
            if metric == "change" and period == "latest" and not result.data:
                from backend.routers.discovery import gainers

                legacy = await gainers()
                _, end = expected_window(period, now)
                rows = [
                    RankingRow(
                        code=r.code,
                        name=r.name,
                        price=r.price,
                        value=r.change_pct,
                        quoted_at=r.quoted_at,
                    )
                    for r in legacy.data
                    if r.quoted_at.date() == end
                ]
                if rows:
                    result = RankingResult(
                        metric=metric,
                        period=period,
                        status="partial",
                        data=rows,
                        start_date=end,
                        end_date=end,
                        fetched_at=legacy.fetched_at,
                        source="sina",
                        scope=legacy.scope,
                        unit="percent",
                        cached=legacy.cached,
                        reason="东方财富不可用，显示新浪单日候选榜；范围与其他周期来源不同。",
                    )
            if result.data:
                await run_sync(store.save, result)
            _cache[key] = (time.monotonic(), result)
            return result
        except Exception:
            logger.exception("Ranking request failed: %s %s", metric, period)
            return unavailable(metric, period, now, "排行读取或交易日历核验失败，请重试。")

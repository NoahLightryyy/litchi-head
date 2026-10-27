"""Read-only market follow-up using an explicit close-to-close reference interval."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from zoneinfo import ZoneInfo

from backend.async_utils import run_sync
from backend.kline_display import RawDailyDisplay, get_raw_daily_display
from backend.retro_observation_contract import RetroObservation
from src.data.evidence import SourceStatus
from src.retro.models import RetroRecord

logger = logging.getLogger(__name__)
_cache: OrderedDict[str, tuple[float, RawDailyDisplay]] = OrderedDict()
_locks: dict[str, asyncio.Lock] = {}
_slots = asyncio.Semaphore(3)


async def load_history(code: str) -> RawDailyDisplay:
    async with _locks.setdefault(code, asyncio.Lock()):
        cached = _cache.get(code)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1]
        try:
            async with _slots, asyncio.timeout(15):
                result = await run_sync(get_raw_daily_display, code, days=950)
        except Exception:
            if not cached or cached[1].status is not SourceStatus.SUCCESS_DATA:
                raise
            logger.exception("Retro refresh failed; retaining dated history: %s", code)
            result = cached[1].model_copy(update={"error_code": "retro_refresh_failed"})
        if (
            result.status is not SourceStatus.SUCCESS_DATA
            and cached
            and cached[1].status is SourceStatus.SUCCESS_DATA
        ):
            result = cached[1].model_copy(update={"error_code": "retro_refresh_failed"})
        # Cache empty/unsupported results too, so records of the same stock do not repeat requests.
        _cache[code] = (time.monotonic(), result)
        _cache.move_to_end(code)
        while len(_cache) > 100:
            _cache.popitem(last=False)
        return result


def build_observation(record: RetroRecord, history: RawDailyDisplay) -> RetroObservation:
    recorded_date = (
        record.created_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
        if record.created_at.tzinfo
        else record.created_at.date()
    )
    result = RetroObservation(
        record_id=record.record_id,
        stock_code=record.stock_code,
        recorded_date=recorded_date,
        status="unavailable",
        message="暂未取得历史日线，稍后会重新查看。",
        fetched_at=history.fetched_at,
    )
    if history.symbol != record.stock_code or any(
        b.code != record.stock_code for b in history.bars
    ):
        raise ValueError("Retro history belongs to another stock")
    if history.status is SourceStatus.UNSUPPORTED:
        result.message = "当前历史日线来源暂不支持这只股票，其他记录照常更新。"
        return result
    if history.status is not SourceStatus.SUCCESS_DATA or not history.bars:
        return result
    dates = [bar.trade_date for bar in history.bars]
    if dates != sorted(set(dates)):
        raise ValueError("Retro history dates are duplicate or unordered")
    subsequent = [bar for bar in history.bars if bar.trade_date >= recorded_date]
    if not subsequent:
        result.status = "waiting"
        result.message = "还没有记录日期之后的完整收盘行情，拿到后自动更新。"
        return result
    first, latest = subsequent[0], subsequent[-1]
    if first.close <= 0 or latest.close <= 0:
        raise ValueError("Retro comparison requires positive closing prices")
    result.baseline_date, result.latest_date = first.trade_date, latest.trade_date
    result.baseline_price, result.latest_price = float(first.close), float(latest.close)
    if first.trade_date == latest.trade_date:
        result.status = "waiting"
        result.message = "已取得起点收盘价，拿到新的完整历史日线后自动比较。"
        return result
    result.change_pct = round((float(latest.close) / float(first.close) - 1) * 100, 4)
    result.status = "observed"
    result.message = (
        "按已取得的收盘日期比较。"
        if first.trade_date == recorded_date
        else "起点晚于记录日期，按下方实际取得的收盘区间比较。"
    )
    consensus = record.consensus.lower()
    direction = (
        1
        if consensus == "bullish" or "看涨" in consensus
        else (-1 if consensus == "bearish" or "看跌" in consensus else 0)
    )
    change = float(latest.close) - float(first.close)
    result.alignment = (
        "no_direction"
        if not direction
        else "flat"
        if change == 0
        else "same"
        if change * direction > 0
        else "opposite"
    )
    return result


async def observe(record: RetroRecord) -> RetroObservation:
    try:
        history = await load_history(record.stock_code)
        result = build_observation(record, history)
        if history.error_code == "retro_refresh_failed":
            result.message += "本次刷新未成功，保留上述日期的收盘价。"
        return result
    except Exception:
        logger.exception(
            "Retro observation unavailable: record=%s code=%s", record.record_id, record.stock_code
        )
        return RetroObservation(
            record_id=record.record_id,
            stock_code=record.stock_code,
            status="unavailable",
            message="这次行情没有更新成功，稍后可刷新。",
        )

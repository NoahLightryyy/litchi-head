"""Index-only history; never resolve an index through stock-code inference."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.data.providers.quotes import SHANGHAI

router = APIRouter()
logger = logging.getLogger(__name__)
INDEX_NAMES = {"sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指"}


class IndexBar(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> IndexBar:
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Invalid index OHLC range")
        return self


class IndexHistory(BaseModel):
    symbol: str
    name: str
    source: Literal["tencent"] = "tencent"
    verification: Literal["single_source"] = "single_source"
    price_unit: Literal["points"] = "points"
    volume_unit: Literal["source_native"] = "source_native"
    fetched_at: datetime
    bars: list[IndexBar]


def parse_index_history(payload: dict, symbol: str, now: datetime) -> IndexHistory:
    if symbol not in INDEX_NAMES:
        raise ValueError("Unknown index")
    block = payload.get("data", {}).get(symbol, {})
    rows = block.get("day")
    if payload.get("code") != 0 or not isinstance(rows, list) or not rows:
        raise ValueError("Missing index daily series")
    bars: list[IndexBar] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("Malformed index candle")
        bar = IndexBar(
            date=row[0], open=row[1], close=row[2], high=row[3], low=row[4], volume=row[5]
        )
        if bar.date > now.astimezone(SHANGHAI).date() or (bars and bar.date <= bars[-1].date):
            raise ValueError("Unordered or future index candle")
        bars.append(bar)
    return IndexHistory(symbol=symbol, name=INDEX_NAMES[symbol], fetched_at=now, bars=bars)


@router.get("/indices/{symbol}/history", response_model=IndexHistory)
async def index_history(symbol: str) -> IndexHistory:
    if symbol not in INDEX_NAMES:
        raise HTTPException(404, "Unknown index")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get(
                "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                params={"param": f"{symbol},day,,,640,"},
            )
            response.raise_for_status()
            return parse_index_history(response.json(), symbol, datetime.now(SHANGHAI))
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        logger.exception("Index history unavailable: symbol=%s", symbol)
        raise HTTPException(502, "Index history unavailable") from None

"""Typed Eastmoney board snapshots with complete pagination and bounded caching.

The snapshot host is the same upstream as the legacy AKShare board endpoints.
Its potential delay must remain visible; it is not a realtime consensus source.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field

BoardKind = Literal["industry", "concept"]
BOARD_SNAPSHOT_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
BOARD_CACHE_SECONDS = 30.0
BOARD_FETCH_SECONDS = 8.0
PAGE_SIZE = 100
SHANGHAI = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


class BoardQuoteSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    code: str = Field(pattern=r"^BK\d{4}$")
    name: str = Field(min_length=1)
    change_pct: float
    fund_flow: float | None
    as_of: datetime


class BoardSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: BoardKind
    quotes: tuple[BoardQuoteSnapshot, ...]
    fetched_at: datetime
    cached: bool = False
    source: Literal["eastmoney"] = "eastmoney"
    possibly_delayed: Literal[True] = True


def _number(value: object, *, nullable: bool = False) -> float | None:
    if nullable and (value is None or value == "-"):
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int, str)):
        raise ValueError("board numeric field has invalid type")
    return float(value)


class EastmoneyBoardSnapshots:
    """One in-flight fetch per category; cache only complete successful snapshots."""

    def __init__(
        self, *, transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._locks = {kind: Lock() for kind in ("industry", "concept")}
        self._cache: dict[BoardKind, tuple[BoardSnapshot, float]] = {}

    def fetch(self, kind: BoardKind) -> BoardSnapshot:
        if kind not in self._locks:
            raise ValueError("unsupported board category")
        deadline = self._clock() + BOARD_FETCH_SECONDS
        if not self._locks[kind].acquire(timeout=BOARD_FETCH_SECONDS):
            raise TimeoutError("board snapshot busy")
        try:
            cached = self._cache.get(kind)
            if cached is not None and self._clock() < cached[1]:
                return cached[0].model_copy(update={"cached": True})
            snapshot = self._fetch_complete(kind, deadline)
            if snapshot.quotes:
                self._cache[kind] = (snapshot, self._clock() + BOARD_CACHE_SECONDS)
            return snapshot
        except Exception:
            logger.exception("Eastmoney board snapshot failed: category=%s", kind)
            raise
        finally:
            self._locks[kind].release()

    def _fetch_complete(self, kind: BoardKind, deadline: float) -> BoardSnapshot:
        quotes: list[BoardQuoteSnapshot] = []
        seen: set[str] = set()
        total: int | None = None
        page = 1
        params = {
            "pz": str(PAGE_SIZE), "po": "1", "np": "1", "fltt": "2", "invt": "2",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281", "fid": "f12",
            "fs": f"m:90 t:{2 if kind == 'industry' else 3} f:!50",
            "fields": "f12,f13,f14,f3,f62,f124",
        }
        with httpx.Client(
            transport=self._transport,
            headers={"Referer": "https://quote.eastmoney.com/", "User-Agent": "Mozilla/5.0"},
        ) as client:
            while total is None or len(quotes) < total:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise TimeoutError("board snapshot total deadline exceeded")
                response = client.get(
                    BOARD_SNAPSHOT_URL, params={**params, "pn": str(page)},
                    timeout=min(3.0, remaining),
                )
                response.raise_for_status()
                if self._clock() > deadline:
                    raise TimeoutError("board snapshot total deadline exceeded")
                payload = response.json()
                page_total, rows = self._page(payload)
                if total is not None and page_total != total:
                    raise ValueError("board total changed during pagination")
                total = page_total
                expected = min(PAGE_SIZE, total - len(quotes))
                if len(rows) != expected:
                    raise ValueError("board page is incomplete")
                for row in rows:
                    quote = self._quote(row)
                    if quote.code in seen:
                        raise ValueError("duplicate board across pages")
                    seen.add(quote.code)
                    quotes.append(quote)
                page += 1
        return BoardSnapshot(
            kind=kind, quotes=tuple(quotes), fetched_at=datetime.now(SHANGHAI),
        )

    @staticmethod
    def _page(payload: Any) -> tuple[int, list[dict[str, Any]]]:
        if not isinstance(payload, dict) or payload.get("rc") != 0:
            raise ValueError("invalid board response envelope")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("missing board response data")
        total, rows = data.get("total"), data.get("diff")
        if type(total) is not int or not 0 <= total <= 10000:
            raise ValueError("invalid board total")
        if total == 0 and rows is None:
            rows = []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("invalid board rows")
        return total, rows

    @staticmethod
    def _quote(row: dict[str, Any]) -> BoardQuoteSnapshot:
        if type(row.get("f13")) is not int or row["f13"] != 90:
            raise ValueError("board market identity mismatch")
        name, code, epoch = row.get("f14"), row.get("f12"), row.get("f124")
        if not isinstance(name, str) or not isinstance(code, str):
            raise ValueError("invalid board identity")
        if type(epoch) is not int or epoch <= 0:
            raise ValueError("board timestamp missing or invalid")
        change_pct = _number(row.get("f3"))
        assert change_pct is not None
        return BoardQuoteSnapshot(
            code=code, name=name.strip(), change_pct=change_pct,
            fund_flow=_number(row.get("f62"), nullable=True),
            as_of=datetime.fromtimestamp(epoch, SHANGHAI),
        )


board_snapshots = EastmoneyBoardSnapshots()

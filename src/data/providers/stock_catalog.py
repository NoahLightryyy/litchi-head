"""Independently load the same exchange directories used by AKShare's aggregate.

One slow/failed exchange must not discard other exchanges. SDK calls without a
timeout retain their one in-flight slot; repeated searches cannot spawn more.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import RLock

import akshare as ak
import pandas as pd
from pydantic import BaseModel, Field

from src.data.models import StockInfo

logger = logging.getLogger(__name__)


class StockCatalogSnapshot(BaseModel):
    items: list[StockInfo] = Field(default_factory=list)
    failed_markets: list[str] = Field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.items) and not self.failed_markets


class PartialStockCatalogError(ConnectionError):
    """Provider exception carrying usable identities without claiming completeness."""

    def __init__(self, snapshot: StockCatalogSnapshot) -> None:
        super().__init__("Stock directory incomplete: " + ", ".join(snapshot.failed_markets))
        self.snapshot = snapshot


def _rows(frame: pd.DataFrame, code_column: str, name_column: str, market: str) -> list[StockInfo]:
    rows: dict[str, StockInfo] = {}
    for _, row in frame.iterrows():
        raw_code = str(row[code_column]).strip()
        if not re.fullmatch(r"\d{1,6}", raw_code) or int(raw_code) == 0:
            raise ValueError("Invalid stock directory code")
        code = raw_code.zfill(6)
        name = str(row[name_column]).strip()
        if not re.fullmatch(r"\d{6}", code) or not name or name.casefold() in {"nan", "none"}:
            raise ValueError("Invalid stock directory identity")
        if code in rows and rows[code].name != name:
            raise ValueError("Conflicting stock directory identity")
        rows[code] = StockInfo(code=code, name=name, market=market)
    if not rows:
        raise ValueError("Empty exchange stock directory")
    return list(rows.values())


def _exchange_loaders() -> dict[str, Callable[[], list[StockInfo]]]:
    # These are exactly the four existing stock_info_a_code_name constituents.
    return {
        "沪市主板": lambda: _rows(
            ak.stock_info_sh_name_code(symbol="主板A股"), "证券代码", "证券简称", "sh"
        ),
        "深市": lambda: _rows(
            ak.stock_info_sz_name_code(symbol="A股列表"), "A股代码", "A股简称", "sz"
        ),
        "科创板": lambda: _rows(
            ak.stock_info_sh_name_code(symbol="科创板"), "证券代码", "证券简称", "sh"
        ),
        "北交所": lambda: _rows(ak.stock_info_bj_name_code(), "证券代码", "证券简称", "bj"),
    }


class ExchangeStockCatalog:
    """Per-exchange success TTL + retry cooldown + bounded, reusable in-flight work."""

    def __init__(self, loaders: dict[str, Callable[[], list[StockInfo]]] | None = None) -> None:
        self._loaders = loaders if loaders is not None else _exchange_loaders()
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, len(self._loaders)), thread_name_prefix="stock-catalog"
        )
        self._lock = RLock()
        self._pending: dict[str, Future[list[StockInfo]]] = {}
        self._success: dict[str, tuple[float, list[StockInfo]]] = {}
        self._retry_after: dict[str, float] = {}

    def snapshot(self, *, timeout: float = 8.0) -> StockCatalogSnapshot:
        with self._lock:
            now = time.monotonic()
            for market, load in self._loaders.items():
                cached = self._success.get(market)
                if cached and now - cached[0] < 3600:
                    continue
                if market not in self._pending and now >= self._retry_after.get(market, 0):
                    self._pending[market] = self._pool.submit(load)
            pending = list(self._pending.values())
        if pending:
            wait(pending, timeout=timeout)
        with self._lock:
            now = time.monotonic()
            for market, future in list(self._pending.items()):
                if not future.done():
                    continue
                del self._pending[market]
                try:
                    rows = future.result()
                    if not rows:
                        raise ValueError("Empty exchange directory")
                    self._success[market] = (now, rows)
                    self._retry_after.pop(market, None)
                except Exception:
                    self._retry_after[market] = now + 15
                    logger.exception("Stock directory unavailable: %s", market)
            items: list[StockInfo] = []
            failed: list[str] = []
            for market in self._loaders:
                cached = self._success.get(market)
                if cached and now - cached[0] < 3600:
                    items.extend(cached[1])
                else:
                    failed.append(market)
            return StockCatalogSnapshot(items=items, failed_markets=failed)


# Shared across AKShareSource instances; at most one pending call per exchange.
exchange_stock_catalog = ExchangeStockCatalog()

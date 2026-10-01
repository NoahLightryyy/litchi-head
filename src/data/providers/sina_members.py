"""Source-native member pages; no name mapping to Eastmoney classifications."""
from __future__ import annotations

import re
import time
from datetime import datetime
from threading import Lock
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from src.data.providers.sina_boards import BASE, SHANGHAI


class SinaMember(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    code: str = Field(pattern=r"^\d{6}$")
    name: str = Field(min_length=1)
    price: float = Field(ge=0)
    change_pct: float
    net_flow: float  # hundred-million CNY (亿元), not main-force flow


class SinaMemberPage(BaseModel):
    source: Literal["sina"] = "sina"
    board_code: str
    page: int
    page_size: Literal[20] = 20
    total: int
    stocks: tuple[SinaMember, ...]
    service_updated_at: datetime
    cached: bool = False


class SinaMemberProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport
        self._lock = Lock()
        self._cache: dict[tuple[str, int], tuple[float, SinaMemberPage]] = {}

    def fetch(self, code: str, page: int = 1) -> SinaMemberPage:
        if not re.fullmatch(r"(?:new_|gn_)[A-Za-z0-9_]+", code) or not 1 <= page <= 500:
            raise ValueError("invalid sina member query")
        deadline = time.monotonic() + 8
        if not self._lock.acquire(timeout=8):
            raise TimeoutError("sina member source busy")
        try:
            key = (code, page)
            cached = self._cache.get(key)
            if cached and time.monotonic() < cached[0]:
                return cached[1].model_copy(update={"cached": True})
            with httpx.Client(transport=self.transport, headers={
                "Referer": "https://money.finance.sina.com.cn/moneyflow/",
                "User-Agent": "Mozilla/5.0",
            }) as client:
                def get(method: str, params: dict[str, Any]) -> Any:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("sina members deadline exceeded")
                    response = client.get(BASE + method, params=params, timeout=min(3, remaining))
                    response.raise_for_status()
                    result = response.json()
                    if time.monotonic() > deadline:
                        raise TimeoutError("sina members deadline exceeded")
                    return result

                stamp = int(get("ssi_get_extend", {"id": 2}))
                updated = datetime.fromtimestamp(stamp, SHANGHAI)
                if stamp <= 0 or updated > datetime.now(SHANGHAI):
                    raise ValueError("invalid sina service timestamp")
                bankuai = f"{'0' if code.startswith('new_') else '1'}/{code}"
                count = int(get("ssc_bkzj_ssggzj", {"bankuai": bankuai}))
                if not 0 <= count <= 10000:
                    raise ValueError("invalid sina member count")
                expected = max(0, min(20, count - (page - 1) * 20))
                rows = get("ssl_bkzj_ssggzj", {"bankuai": bankuai, "page": page,
                           "num": 20, "sort": "netamount", "asc": 0}) if expected else []
                if not isinstance(rows, list) or len(rows) != expected:
                    raise ValueError("incomplete sina member page")
                stocks: list[SinaMember] = []
                for row in rows:
                    if not re.fullmatch(r"(?:sh|sz|bj)\d{6}", row["symbol"]):
                        raise ValueError("invalid sina stock symbol")
                    stocks.append(SinaMember(code=row["symbol"][2:], name=row["name"],
                        price=float(row["trade"]), change_pct=float(row["changeratio"]) * 100,
                        net_flow=float(row["netamount"]) / 1e8))
                if len({s.code for s in stocks}) != len(stocks):
                    raise ValueError("duplicate sina members")
                if int(get("ssi_get_extend", {"id": 2})) != stamp:
                    raise ValueError("sina service updated during member fetch")
            result = SinaMemberPage(board_code=code, page=page, total=count,
                                    stocks=tuple(stocks), service_updated_at=updated)
            if len(self._cache) >= 64:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (time.monotonic() + 30, result)
            return result
        finally:
            self._lock.release()


sina_members = SinaMemberProvider()

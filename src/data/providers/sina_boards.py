"""Sina display-only boards: preserve provider IDs and distinguish net from main flow."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field

from src.data.providers.eastmoney_boards import BOARD_CACHE_SECONDS, BOARD_FETCH_SECONDS

BASE = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow."
SHANGHAI = ZoneInfo("Asia/Shanghai")


class SinaBoard(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    code: str = Field(pattern=r"^(new_|gn_)[A-Za-z0-9_]+$")
    name: str = Field(min_length=1)
    category: Literal["industry", "concept"]
    change_pct: float
    net_flow: float  # yuan; explicitly NOT main-force net flow
    leader: str


class SinaBoardCollection(BaseModel):
    boards: tuple[SinaBoard, ...]
    service_updated_at: datetime
    fetched_at: datetime
    cached: bool = False


class SinaBoardProvider:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport
        self._lock = Lock()
        self._cache: tuple[float, SinaBoardCollection] | None = None

    def fetch(self) -> SinaBoardCollection:
        deadline = time.monotonic() + BOARD_FETCH_SECONDS
        if not self._lock.acquire(timeout=BOARD_FETCH_SECONDS):
            raise TimeoutError("sina boards busy")
        try:
            if self._cache and time.monotonic() < self._cache[0]:
                return self._cache[1].model_copy(update={"cached": True})
            with httpx.Client(transport=self.transport, headers={
                "Referer": "https://money.finance.sina.com.cn/moneyflow/",
                "User-Agent": "Mozilla/5.0",
            }) as client:
                def get(method: str, params: dict[str, Any]) -> Any:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("sina boards deadline exceeded")
                    response = client.get(BASE + method, params=params, timeout=min(3, remaining))
                    response.raise_for_status()
                    result = response.json()
                    if time.monotonic() > deadline:
                        raise TimeoutError("sina boards deadline exceeded")
                    return result

                stamp = int(get("ssi_get_extend", {"id": 2}))
                updated = datetime.fromtimestamp(stamp, SHANGHAI)
                if stamp <= 0 or updated > datetime.now(SHANGHAI):
                    raise ValueError("invalid source service timestamp")

                def category(kind: Literal["industry", "concept"]) -> list[SinaBoard]:
                    flag = 0 if kind == "industry" else 1
                    count = int(get("ssc_bkzj_bk", {"fenlei": flag}))
                    if count <= 0:
                        raise ValueError("empty sina category")
                    boards: list[SinaBoard] = []
                    for page in range(1, (count + 99) // 100 + 1):
                        rows = get("ssl_bkzj_bk", {"fenlei": flag, "page": page,
                                   "num": 100, "sort": "netamount", "asc": 0})
                        if not isinstance(rows, list) or len(rows) != min(100, count-len(boards)):
                            raise ValueError("incomplete sina pagination")
                        for row in rows:
                            if str(row["cate_type"]) != str(flag):
                                raise ValueError("sina category mismatch")
                            board = SinaBoard(code=row["category"], name=row["name"], category=kind,
                                              change_pct=float(row["avg_changeratio"])*100,
                                              net_flow=float(row["netamount"]),
                                              leader=str(row.get("ts_name") or ""))
                            if not board.code.startswith("new_" if flag == 0 else "gn_"):
                                raise ValueError("sina code namespace mismatch")
                            boards.append(board)
                    if len({board.code for board in boards}) != count:
                        raise ValueError("duplicate sina boards")
                    return boards

                with ThreadPoolExecutor(max_workers=2) as pool:
                    industry = pool.submit(category, "industry")
                    concept = pool.submit(category, "concept")
                    boards = industry.result() + concept.result()
                if int(get("ssi_get_extend", {"id": 2})) != stamp:
                    raise ValueError("sina service updated during pagination; retry")
            result = SinaBoardCollection(boards=tuple(boards), service_updated_at=updated,
                                         fetched_at=datetime.now(SHANGHAI))
            self._cache = (time.monotonic() + BOARD_CACHE_SECONDS, result)
            return result
        finally:
            self._lock.release()


sina_boards = SinaBoardProvider()

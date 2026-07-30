"""Official SSE/SZSE listing and delisting lifecycle evidence."""

from __future__ import annotations

import hashlib
import io
import warnings
from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field

from src.data.kline import MarketCode
from src.data.kline_status import OfficialSecurityLifecycleEvidence
from src.data.providers.bse_status import (
    BSE_CODE_MAPPING_URL as BSE_CODE_MAPPING_URL,
)
from src.data.providers.bse_status import (
    BSE_LIST_QUERY_URL as BSE_LIST_QUERY_URL,
)
from src.data.providers.bse_status import (
    BSE_LISTED_COMPANY_PAGE_URL as BSE_LISTED_COMPANY_PAGE_URL,
)
from src.data.providers.bse_status import (
    BSE_MARKET_CALENDAR_PAGE_URL as BSE_MARKET_CALENDAR_PAGE_URL,
)
from src.data.providers.bse_status import (
    BSE_TRADING_TIPS_QUERY_URL as BSE_TRADING_TIPS_QUERY_URL,
)
from src.data.providers.bse_status import (
    BSE_TRANSFERRED_WITHOUT_STRUCTURED_LISTING_DATE,
    fetch_bse_lifecycle_records,
)

SSE_QUERY_URL = "https://query.sse.com.cn/sseQuery/commonQuery.do"
SSE_ACTIVE_PAGE_URL = "https://www.sse.com.cn/assortment/stock/list/share/"
SSE_DELISTED_PAGE_URL = "https://www.sse.com.cn/assortment/stock/list/delisting/"
SZSE_REPORT_URL = "https://www.szse.cn/api/report/ShowReport"
SZSE_ACTIVE_PAGE_URL = "https://www.szse.cn/market/product/stock/list/index.html"
SZSE_DELISTED_PAGE_URL = "https://www.szse.cn/market/stock/suspend/index.html"
LIFECYCLE_TIMEOUT_SECONDS = 30.0


class SecurityLifecycleSourceError(RuntimeError):
    """Official lifecycle evidence is unavailable, ambiguous, or unsupported."""


class OfficialLifecycleSnapshot(BaseModel):
    """One normalized row from an official full-list response."""

    code: str = Field(min_length=6, max_length=6)
    listed_on: date
    delisted_on: date | None = None
    source_url: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class OfficialLifecycleFetcher(Protocol):
    """Replaceable official full-list fetch boundary."""

    def __call__(
        self,
        market: MarketCode,
        delisted: bool,
    ) -> tuple[OfficialLifecycleSnapshot, ...]:
        """Return every normalized row from one official response."""
        ...


def _parse_date(value: object, field: str) -> date:
    import pandas as pd

    parsed = pd.to_datetime(str(value), errors="raise")
    if not isinstance(parsed, pd.Timestamp):
        raise ValueError(f"invalid official {field}: {value!r}")
    return parsed.date()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fetch_sse(delisted: bool) -> tuple[OfficialLifecycleSnapshot, ...]:
    import httpx

    page_url = SSE_DELISTED_PAGE_URL if delisted else SSE_ACTIVE_PAGE_URL
    params = {
        "STOCK_TYPE": "1,8",
        "REG_PROVINCE": "",
        "CSRC_CODE": "",
        "STOCK_CODE": "",
        "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
        "COMPANY_STATUS": "3" if delisted else "2,4,5,7,8",
        "type": "inParams",
        "isPagination": "true",
        "pageHelp.cacheSize": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.pageSize": "10000",
        "pageHelp.pageNo": "1",
        "pageHelp.endPage": "1",
    }
    response = httpx.get(
        SSE_QUERY_URL,
        params=params,
        headers={
            "Host": "query.sse.com.cn",
            "Referer": page_url,
            "User-Agent": "litchi-head/0.1",
        },
        timeout=LIFECYCLE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(
        payload.get("result"),
        list,
    ):
        raise ValueError("official SSE lifecycle response is incomplete")
    digest = _sha256(response.content)
    snapshots: list[OfficialLifecycleSnapshot] = []
    for item in payload["result"]:
        if not isinstance(item, dict):
            raise ValueError("official SSE lifecycle row must be an object")
        code = str(item.get("A_STOCK_CODE", "")).strip()
        if not code:
            continue
        raw_delisted = str(item.get("DELIST_DATE", "")).strip()
        snapshots.append(
            OfficialLifecycleSnapshot(
                code=code,
                listed_on=_parse_date(item.get("LIST_DATE"), "listing date"),
                delisted_on=(
                    _parse_date(raw_delisted, "delisting date")
                    if delisted and raw_delisted not in {"", "-"}
                    else None
                ),
                source_url=page_url,
                content_hash=digest,
            )
        )
    return tuple(snapshots)


def _fetch_szse(delisted: bool) -> tuple[OfficialLifecycleSnapshot, ...]:
    import httpx
    import pandas as pd

    page_url = SZSE_DELISTED_PAGE_URL if delisted else SZSE_ACTIVE_PAGE_URL
    response = httpx.get(
        SZSE_REPORT_URL,
        params={
            "SHOWTYPE": "xlsx",
            "CATALOGID": "1793_ssgs" if delisted else "1110",
            "TABKEY": "tab2" if delisted else "tab1",
            "random": "0.1",
        },
        headers={"Referer": page_url, "User-Agent": "litchi-head/0.1"},
        timeout=LIFECYCLE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        frame = pd.read_excel(io.BytesIO(response.content))
    code_column = "证券代码" if delisted else "A股代码"
    listed_column = "上市日期" if delisted else "A股上市日期"
    required = {code_column, listed_column}
    if not required.issubset(frame.columns):
        raise ValueError("official SZSE lifecycle response is incomplete")
    digest = _sha256(response.content)
    snapshots: list[OfficialLifecycleSnapshot] = []
    for row in frame.to_dict(orient="records"):
        raw_code = str(row[code_column]).split(".", 1)[0].strip()
        if not raw_code.isdigit():
            continue
        snapshots.append(
            OfficialLifecycleSnapshot(
                code=raw_code.zfill(6),
                listed_on=_parse_date(row[listed_column], "listing date"),
                delisted_on=(
                    _parse_date(row["终止上市日期"], "delisting date") if delisted else None
                ),
                source_url=page_url,
                content_hash=digest,
            )
        )
    return tuple(snapshots)


def _default_fetcher(
    market: MarketCode,
    delisted: bool,
) -> tuple[OfficialLifecycleSnapshot, ...]:
    if market is MarketCode.SSE:
        return _fetch_sse(delisted)
    if market is MarketCode.SZSE:
        return _fetch_szse(delisted)
    return tuple(
        OfficialLifecycleSnapshot(
            code=record.code,
            listed_on=record.listed_on,
            delisted_on=record.delisted_on,
            source_url=record.source_url,
            content_hash=record.content_hash,
        )
        for record in fetch_bse_lifecycle_records(delisted)
    )


class OfficialSecurityLifecycleSource:
    """Resolve one security only from official exchange lifecycle lists."""

    def __init__(self, fetcher: OfficialLifecycleFetcher | None = None) -> None:
        self._fetcher = fetcher or _default_fetcher
        self._uses_default_fetcher = fetcher is None

    def fetch(
        self,
        *,
        code: str,
        market: MarketCode,
    ) -> OfficialSecurityLifecycleEvidence:
        if (
            self._uses_default_fetcher
            and market is MarketCode.BSE
            and code in BSE_TRANSFERRED_WITHOUT_STRUCTURED_LISTING_DATE
        ):
            raise SecurityLifecycleSourceError(
                "BSE transferred security requires composite evidence"
            )
        try:
            for delisted in (False, True):
                matches = tuple(
                    snapshot
                    for snapshot in self._fetcher(market, delisted)
                    if snapshot.code == code
                )
                if len(matches) > 1:
                    raise SecurityLifecycleSourceError(
                        f"duplicate official lifecycle identity for {code}"
                    )
                if len(matches) == 1:
                    snapshot = matches[0]
                    return OfficialSecurityLifecycleEvidence(
                        code=code,
                        market=market,
                        listed_on=snapshot.listed_on,
                        delisted_on=snapshot.delisted_on,
                        source_url=snapshot.source_url,
                        content_hash=snapshot.content_hash,
                    )
        except SecurityLifecycleSourceError:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise SecurityLifecycleSourceError(message) from exc
        raise SecurityLifecycleSourceError(f"official lifecycle identity not found for {code}")


__all__ = [
    "OfficialLifecycleSnapshot",
    "OfficialSecurityLifecycleSource",
    "SecurityLifecycleSourceError",
]

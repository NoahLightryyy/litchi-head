"""Official BSE lifecycle aliases and suspension event evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any, Protocol

from src.data.kline import MarketCode
from src.data.kline_status import (
    OfficialSuspensionEvent,
    OfficialSuspensionEventBatch,
    SuspensionEventKind,
)

BSE_LIST_QUERY_URL = "https://www.bse.cn/nqxxController/nqxxCnzq.do"
BSE_LISTED_COMPANY_PAGE_URL = "https://www.bse.cn/nq/listedcompany.html"
BSE_CODE_MAPPING_URL = "https://www.bse.cn/service/code_mapping.html"
BSE_TRADING_TIPS_QUERY_URL = "https://www.bse.cn/tradingtipsController/tradingtipsExPage.do"
BSE_MARKET_CALENDAR_PAGE_URL = "https://www.bse.cn/disclosure/tradingtips.html"
BSE_OPENED_ON = date(2021, 11, 15)
BSE_TIMEOUT_SECONDS = 30.0
BSE_TRANSFERRED_WITHOUT_STRUCTURED_LISTING_DATE = frozenset({"832317", "833874", "833994"})
_CALLBACK = "lhcb"
_CODE = re.compile(r"^\d{6}$")
_SINGLE_QUOTED_DATE = re.compile(r"'(\d{4}-\d{2}-\d{2})'")
_STATUS_TYPE_CODES = ("0600", "0700", "9001")
_MAX_PAGES = 1000
_MAX_ELEMENTS = 20000


class BseSuspensionEventSourceError(RuntimeError):
    """BSE official status evidence is unavailable, incomplete, or invalid."""


class BseTradingTipsPageFetcher(Protocol):
    """Replaceable raw official market-calendar page boundary."""

    def __call__(
        self,
        *,
        code: str,
        start: date,
        end: date,
        page: int,
        type_codes: tuple[str, ...],
    ) -> bytes:
        """Return one raw JSONP page."""
        ...


class BseCodeMappingFetcher(Protocol):
    """Replaceable raw official old/new code mapping boundary."""

    def __call__(self) -> bytes:
        """Return the complete official mapping HTML."""
        ...


@dataclass(frozen=True)
class BseLifecycleRecord:
    """Normalized lifecycle row before the shared evidence model."""

    code: str
    listed_on: date
    delisted_on: date | None
    source_url: str
    content_hash: str


@dataclass(frozen=True)
class _Alias:
    old_code: str
    new_code: str
    listed_on: date


@dataclass(frozen=True)
class _Page:
    rows: tuple[Mapping[str, Any], ...]
    number: int
    number_of_elements: int
    size: int
    total_elements: int
    total_pages: int
    first_page: bool
    last_page: bool


def _digest_chunks(chunks: tuple[bytes, ...]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(len(chunk).to_bytes(8, byteorder="big"))
        digest.update(chunk)
    return digest.hexdigest()


def _parse_jsonp(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("official BSE response is not UTF-8") from exc
    match = re.fullmatch(
        r"\s*[A-Za-z_$][\w$]*\((.*)\)\s*;?\s*",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("official BSE response is not valid JSONP")
    body = _SINGLE_QUOTED_DATE.sub(r'"\1"', match.group(1))
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("official BSE JSONP payload is malformed") from exc


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"official BSE {field} must be a nonnegative integer")
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"official BSE {field} must be a nonnegative integer") from exc
    if parsed < 0:
        raise ValueError(f"official BSE {field} must be a nonnegative integer")
    return parsed


def _parse_page(value: object) -> _Page:
    if not isinstance(value, Mapping):
        raise ValueError("official BSE pagination object is missing")
    raw_rows = value.get("content")
    if not isinstance(raw_rows, list) or any(not isinstance(row, Mapping) for row in raw_rows):
        raise ValueError("official BSE pagination content is incomplete")
    return _Page(
        rows=tuple(raw_rows),
        number=_nonnegative_int(value.get("number"), "page number"),
        number_of_elements=_nonnegative_int(
            value.get("numberOfElements"),
            "page element count",
        ),
        size=_nonnegative_int(value.get("size"), "page size"),
        total_elements=_nonnegative_int(
            value.get("totalElements"),
            "total element count",
        ),
        total_pages=_nonnegative_int(value.get("totalPages"), "total pages"),
        first_page=value.get("firstPage") is True,
        last_page=value.get("lastPage") is True,
    )


def _validate_page(
    page: _Page,
    *,
    requested_page: int,
    total_pages: int,
    total_elements: int,
) -> None:
    if page.size == 0:
        raise ValueError("official BSE pagination page size is invalid")
    expected_pages = 0 if total_elements == 0 else (total_elements + page.size - 1) // page.size
    expected_last = total_pages == 0 or requested_page == total_pages - 1
    if (
        total_pages > _MAX_PAGES
        or total_elements > _MAX_ELEMENTS
        or total_pages != expected_pages
        or page.number != requested_page
        or page.number_of_elements != len(page.rows)
        or page.number_of_elements > page.size
        or page.total_pages != total_pages
        or page.total_elements != total_elements
        or page.first_page != (requested_page == 0)
        or page.last_page != expected_last
    ):
        raise ValueError("official BSE pagination metadata is inconsistent")


def _parse_date(value: object, field: str) -> date:
    import pandas as pd

    parsed = pd.to_datetime(str(value), errors="raise")
    if not isinstance(parsed, pd.Timestamp):
        raise ValueError(f"invalid official BSE {field}: {value!r}")
    return parsed.date()


def _default_mapping_fetcher() -> bytes:
    import httpx

    response = httpx.get(
        BSE_CODE_MAPPING_URL,
        headers={
            "Referer": BSE_LISTED_COMPANY_PAGE_URL,
            "User-Agent": "Mozilla/5.0 litchi-head/0.1",
        },
        timeout=BSE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _parse_aliases(raw: bytes) -> tuple[_Alias, ...]:
    import pandas as pd

    try:
        text = raw.decode("utf-8")
        frames = pd.read_html(StringIO(text))
    except Exception as exc:
        raise ValueError("official BSE code mapping is incomplete") from exc
    required_columns = {"上市日期", "旧代码", "新代码"}
    candidates = []
    for frame in frames:
        frame.columns = [str(column).strip() for column in frame.columns]
        if required_columns.issubset(frame.columns):
            candidates.append(frame)
            continue
        if frame.empty:
            continue
        first_row = [str(value).strip() for value in frame.iloc[0].tolist()]
        if required_columns.issubset(first_row):
            normalized = frame.iloc[1:].copy()
            normalized.columns = first_row
            candidates.append(normalized)
    if len(candidates) != 1:
        raise ValueError("official BSE code mapping table is ambiguous")
    aliases: list[_Alias] = []
    for row in candidates[0].to_dict(orient="records"):
        row_values = {str(value).strip() for value in row.values()}
        if len(row_values) == 1 and next(iter(row_values)).startswith("注："):
            continue
        old_code = str(row["旧代码"]).split(".", 1)[0].strip()
        new_code = str(row["新代码"]).split(".", 1)[0].strip()
        if (
            not _CODE.fullmatch(old_code)
            or not _CODE.fullmatch(new_code)
            or old_code[0] not in {"4", "8"}
            or not new_code.startswith("92")
            or old_code == new_code
        ):
            raise ValueError("official BSE code mapping identity is invalid")
        aliases.append(
            _Alias(
                old_code=old_code,
                new_code=new_code,
                listed_on=_parse_date(
                    row["上市日期"],
                    "mapping listing date",
                ),
            )
        )
    if not aliases:
        raise ValueError("official BSE code mapping is incomplete")
    old_codes = [alias.old_code for alias in aliases]
    new_codes = [alias.new_code for alias in aliases]
    if len(old_codes) != len(set(old_codes)) or len(new_codes) != len(set(new_codes)):
        raise ValueError("official BSE code mapping has duplicate identities")
    return tuple(aliases)


def _identity(
    code: str,
    aliases: tuple[_Alias, ...],
) -> tuple[str, frozenset[str], _Alias | None]:
    matches = tuple(alias for alias in aliases if code in {alias.old_code, alias.new_code})
    if len(matches) > 1:
        raise ValueError("official BSE code mapping identity is ambiguous")
    if matches:
        alias = matches[0]
        return (
            alias.new_code,
            frozenset({alias.old_code, alias.new_code}),
            alias,
        )
    if not code.startswith("92"):
        raise ValueError("official BSE code mapping missing legacy identity")
    return code, frozenset({code}), None


def _default_trading_tips_page_fetcher(
    *,
    code: str,
    start: date,
    end: date,
    page: int,
    type_codes: tuple[str, ...],
) -> bytes:
    import httpx

    params: list[tuple[str, Any]] = [
        ("page", str(page)),
        ("xxfcbj[]", "2"),
        ("label[]", "0"),
        ("label[]", "2"),
    ]
    params.extend(("typecode[]", type_code) for type_code in type_codes)
    params.extend(
        [
            ("companycode", code),
            ("publishDate", ""),
            ("startTime", start.isoformat()),
            ("endTime", end.isoformat()),
            ("sortfield", "publish_date"),
            ("needPublishDate", "true"),
            ("isInit", "0"),
            ("sorttype", "asc"),
            ("callback", _CALLBACK),
        ]
    )
    response = httpx.get(
        BSE_TRADING_TIPS_QUERY_URL,
        params=params,
        headers={
            "Referer": BSE_MARKET_CALENDAR_PAGE_URL,
            "User-Agent": "Mozilla/5.0 litchi-head/0.1",
        },
        timeout=BSE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _parse_type_counts(value: object) -> dict[str, int]:
    if not isinstance(value, list):
        raise ValueError("official BSE event counts are incomplete")
    counts: dict[str, int] = {}
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("official BSE event counts are incomplete")
        type_code = str(item.get("typecode", "")).strip()
        if not re.fullmatch(r"\d{4}", type_code) or type_code in counts:
            raise ValueError("official BSE event counts are inconsistent")
        counts[type_code] = _nonnegative_int(
            item.get("num"),
            "event count",
        )
    return counts


def _trading_tips_page(
    raw: bytes,
    start: date,
    end: date,
) -> tuple[_Page, dict[str, int]]:
    payload = _parse_jsonp(raw)
    if (
        not isinstance(payload, list)
        or len(payload) != 4
        or not isinstance(payload[0], list)
        or len(payload[0]) != 1
        or payload[2] != start.isoformat()
        or payload[3] != end.isoformat()
    ):
        raise ValueError("official BSE query window or response is incomplete")
    return _parse_page(payload[0][0]), _parse_type_counts(payload[1])


def _fetch_trading_tips_pages(
    *,
    code: str,
    start: date,
    end: date,
    type_codes: tuple[str, ...],
    fetcher: BseTradingTipsPageFetcher,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[bytes, ...]]:
    raw_pages: list[bytes] = []
    rows: list[Mapping[str, Any]] = []
    first_raw = fetcher(
        code=code,
        start=start,
        end=end,
        page=0,
        type_codes=type_codes,
    )
    raw_pages.append(first_raw)
    first, first_counts = _trading_tips_page(first_raw, start, end)
    _validate_page(
        first,
        requested_page=0,
        total_pages=first.total_pages,
        total_elements=first.total_elements,
    )
    if sum(first_counts.get(code, 0) for code in type_codes) != (first.total_elements):
        raise ValueError("official BSE event count conflicts with pagination")
    rows.extend(first.rows)
    for page_number in range(1, first.total_pages):
        raw = fetcher(
            code=code,
            start=start,
            end=end,
            page=page_number,
            type_codes=type_codes,
        )
        raw_pages.append(raw)
        page, counts = _trading_tips_page(raw, start, end)
        if counts != first_counts:
            raise ValueError("official BSE event counts changed across pages")
        _validate_page(
            page,
            requested_page=page_number,
            total_pages=first.total_pages,
            total_elements=first.total_elements,
        )
        rows.extend(page.rows)
    if len(rows) != first.total_elements:
        raise ValueError("official BSE pagination does not cover every advertised row")
    grouped = {code: 0 for code in type_codes}
    for row in rows:
        type_code = str(row.get("typecode", "")).strip()
        if type_code not in grouped:
            raise ValueError("official BSE event type is outside requested coverage")
        grouped[type_code] += 1
    if any(grouped[code] != first_counts.get(code, 0) for code in type_codes):
        raise ValueError("official BSE event count conflicts with rows")
    return tuple(rows), tuple(raw_pages)


def _default_list_page_fetcher(page: int) -> bytes:
    import httpx

    params: list[tuple[str, Any]] = [
        ("page", str(page)),
        ("typejb", "T"),
        ("xxfcbj[]", "2"),
        ("xxzqdm", ""),
        ("sortfield", "xxzqdm"),
        ("sorttype", "asc"),
        ("callback", _CALLBACK),
    ]
    response = httpx.get(
        BSE_LIST_QUERY_URL,
        params=params,
        headers={
            "Referer": BSE_LISTED_COMPANY_PAGE_URL,
            "User-Agent": "Mozilla/5.0 litchi-head/0.1",
        },
        timeout=BSE_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _list_page(raw: bytes) -> _Page:
    payload = _parse_jsonp(raw)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], Mapping):
        raise ValueError("official BSE listed-company response is incomplete")
    return _parse_page(payload[0])


def _fetch_list_pages(
    fetcher: Callable[[int], bytes],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[bytes, ...]]:
    raw_pages: list[bytes] = []
    rows: list[Mapping[str, Any]] = []
    first_raw = fetcher(0)
    raw_pages.append(first_raw)
    first = _list_page(first_raw)
    _validate_page(
        first,
        requested_page=0,
        total_pages=first.total_pages,
        total_elements=first.total_elements,
    )
    rows.extend(first.rows)
    for page_number in range(1, first.total_pages):
        raw = fetcher(page_number)
        raw_pages.append(raw)
        page = _list_page(raw)
        _validate_page(
            page,
            requested_page=page_number,
            total_pages=first.total_pages,
            total_elements=first.total_elements,
        )
        rows.extend(page.rows)
    if len(rows) != first.total_elements:
        raise ValueError("official BSE pagination does not cover every advertised row")
    return tuple(rows), tuple(raw_pages)


def _required_code(row: Mapping[str, Any], field: str) -> str:
    code = str(row.get(field, "")).strip()
    if not _CODE.fullmatch(code):
        raise ValueError(f"official BSE response missing valid {field}")
    return code


def _validate_stock_tip(
    row: Mapping[str, Any],
    *,
    aliases: frozenset[str],
    type_codes: frozenset[str],
) -> tuple[str, date]:
    code = _required_code(row, "companycode")
    if (
        code not in aliases
        or str(row.get("xxfcbj", "")).strip() != "2"
        or str(row.get("productType", "")).strip() != "10"
        or str(row.get("xxzqjb", "")).strip() != "T"
    ):
        raise ValueError("official BSE event identity does not match request")
    type_code = str(row.get("typecode", "")).strip()
    if type_code not in type_codes:
        raise ValueError("official BSE event type is outside requested coverage")
    return type_code, _parse_date(row.get("publishdate"), "event date")


def fetch_bse_lifecycle_records(
    delisted: bool,
) -> tuple[BseLifecycleRecord, ...]:
    """Fetch current or 920-mapped delisted BSE lifecycle evidence."""
    mapping_raw = _default_mapping_fetcher()
    aliases = _parse_aliases(mapping_raw)
    if not delisted:
        rows, raw_pages = _fetch_list_pages(_default_list_page_fetcher)
        digest = _digest_chunks((mapping_raw, *raw_pages))
        records: list[BseLifecycleRecord] = []
        seen: set[str] = set()
        aliases_by_new = {alias.new_code: alias for alias in aliases}
        for row in rows:
            code = _required_code(row, "xxzqdm")
            if str(row.get("xxfcbj", "")).strip() != "2" or code in seen:
                raise ValueError("official BSE listed-company identity is inconsistent")
            seen.add(code)
            listed_on = _parse_date(row.get("fxssrq"), "listing date")
            alias = aliases_by_new.get(code)
            if alias is not None and alias.listed_on != listed_on:
                raise ValueError("official BSE listing date conflicts with code mapping")
            codes = (code,) if alias is None else (code, alias.old_code)
            records.extend(
                BseLifecycleRecord(
                    code=identity,
                    listed_on=listed_on,
                    delisted_on=None,
                    source_url=BSE_LISTED_COMPANY_PAGE_URL,
                    content_hash=digest,
                )
                for identity in codes
            )
        return tuple(records)

    rows, raw_pages = _fetch_trading_tips_pages(
        code="",
        start=BSE_OPENED_ON,
        end=date.today(),
        type_codes=("1101",),
        fetcher=_default_trading_tips_page_fetcher,
    )
    digest = _digest_chunks((mapping_raw, *raw_pages))
    aliases_by_code = {
        identity: alias for alias in aliases for identity in (alias.old_code, alias.new_code)
    }
    terminated: dict[str, date] = {}
    for row in rows:
        if str(row.get("productType", "")).strip() != "10":
            continue
        code = _required_code(row, "companycode")
        alias = aliases_by_code.get(code)
        if alias is None:
            if code in BSE_TRANSFERRED_WITHOUT_STRUCTURED_LISTING_DATE:
                continue
            raise ValueError("official BSE delisted identity lacks a listing-date mapping")
        type_code, delisted_on = _validate_stock_tip(
            row,
            aliases=frozenset({alias.old_code, alias.new_code}),
            type_codes=frozenset({"1101"}),
        )
        if type_code != "1101":
            raise ValueError("official BSE delisting response is incomplete")
        previous = terminated.setdefault(alias.new_code, delisted_on)
        if previous != delisted_on:
            raise ValueError("official BSE delisted identity has conflicting dates")
    records: list[BseLifecycleRecord] = []
    aliases_by_new = {alias.new_code: alias for alias in aliases}
    for new_code, delisted_on in terminated.items():
        alias = aliases_by_new[new_code]
        for identity in (alias.new_code, alias.old_code):
            records.append(
                BseLifecycleRecord(
                    code=identity,
                    listed_on=alias.listed_on,
                    delisted_on=delisted_on,
                    source_url=BSE_MARKET_CALENDAR_PAGE_URL,
                    content_hash=digest,
                )
            )
    return tuple(records)


class BseSuspensionEventSource:
    """Read BSE full-day transitions from its complete market-calendar pages."""

    def __init__(
        self,
        page_fetcher: BseTradingTipsPageFetcher | None = None,
        mapping_fetcher: BseCodeMappingFetcher | None = None,
    ) -> None:
        self._page_fetcher = page_fetcher or _default_trading_tips_page_fetcher
        self._mapping_fetcher = mapping_fetcher or _default_mapping_fetcher

    def fetch_batch(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
    ) -> OfficialSuspensionEventBatch:
        """Fetch one complete, paginated natural-date event batch."""
        if market is not MarketCode.BSE:
            raise BseSuspensionEventSourceError("BSE status source only supports MarketCode.BSE")
        if start > end:
            raise BseSuspensionEventSourceError("suspension event start must not exceed end")
        try:
            mapping_raw = self._mapping_fetcher()
            canonical_code, aliases, _ = _identity(
                code,
                _parse_aliases(mapping_raw),
            )
            rows, raw_pages = _fetch_trading_tips_pages(
                code=canonical_code,
                start=start,
                end=end,
                type_codes=_STATUS_TYPE_CODES,
                fetcher=self._page_fetcher,
            )
            digest = _digest_chunks((mapping_raw, *raw_pages))
            events: list[OfficialSuspensionEvent] = []
            for row in rows:
                type_code, effective_on = _validate_stock_tip(
                    row,
                    aliases=aliases,
                    type_codes=frozenset(_STATUS_TYPE_CODES),
                )
                if not start <= effective_on <= end:
                    raise ValueError("official BSE event falls outside query window")
                kind = {
                    "0600": SuspensionEventKind.FULL_DAY_START,
                    "0700": SuspensionEventKind.FULL_DAY_RESUME,
                }.get(type_code)
                if kind is None:
                    continue
                events.append(
                    OfficialSuspensionEvent(
                        code=code,
                        market=market,
                        kind=kind,
                        effective_on=effective_on,
                        source_url=BSE_MARKET_CALENDAR_PAGE_URL,
                        content_hash=digest,
                    )
                )
            normalized_events = tuple(
                sorted(
                    events,
                    key=lambda event: (
                        event.effective_on,
                        event.kind.value,
                        event.source_url,
                    ),
                )
            )
            return OfficialSuspensionEventBatch(
                code=code,
                market=market,
                coverage_start=start,
                coverage_end=end,
                events=normalized_events,
                source_url=BSE_MARKET_CALENDAR_PAGE_URL,
                content_hash=digest,
            )
        except BseSuspensionEventSourceError:
            raise
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            raise BseSuspensionEventSourceError(message) from exc

    def fetch_events(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
    ) -> tuple[OfficialSuspensionEvent, ...]:
        """Compatibility view over the complete official BSE batch."""
        return self.fetch_batch(
            code=code,
            market=market,
            start=start,
            end=end,
        ).events


__all__ = [
    "BSE_MARKET_CALENDAR_PAGE_URL",
    "BseSuspensionEventSource",
    "BseSuspensionEventSourceError",
]

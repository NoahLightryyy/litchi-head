"""BSE official market-calendar suspension event evidence tests."""

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest

from src.data.kline import MarketCode
from src.data.kline_status import (
    OfficialSecurityLifecycleEvidence,
    OfficialSecurityStateCheckpoint,
    SecurityTradingState,
    SuspensionEventKind,
    SuspensionStatusLedger,
)
from src.data.providers.bse_status import (
    BSE_MARKET_CALENDAR_PAGE_URL,
    BseSuspensionEventSource,
    BseSuspensionEventSourceError,
)


def _jsonp(payload: object) -> bytes:
    return f"lhcb({json.dumps(payload, ensure_ascii=False)})".encode()


def _page(
    rows: list[Mapping[str, object]],
    *,
    number: int = 0,
    total_pages: int = 1,
    total_elements: int | None = None,
    size: int = 20,
) -> dict[str, object]:
    count = len(rows) if total_elements is None else total_elements
    return {
        "content": rows,
        "firstPage": number == 0,
        "lastPage": total_pages == 0 or number == total_pages - 1,
        "number": number,
        "numberOfElements": len(rows),
        "size": size,
        "sort": None,
        "totalElements": count,
        "totalPages": total_pages,
    }


def _row(
    typecode: str,
    effective_on: str,
    *,
    code: str = "920685",
    comments: str = "",
) -> dict[str, object]:
    names = {
        "0600": "停牌",
        "0700": "复牌",
        "9001": "盘中临停",
    }
    return {
        "comments": comments,
        "companycode": code,
        "companyname": "新芝生物",
        "productType": "10",
        "publishdate": effective_on,
        "typecode": typecode,
        "typename": names[typecode],
        "xxfcbj": "2",
        "xxzqjb": "T",
    }


def _payload(
    page: dict[str, object],
    *,
    start: str = "2026-07-16",
    end: str = "2026-07-30",
    counts: tuple[tuple[str, int], ...] | None = None,
) -> bytes:
    if counts is None:
        grouped: dict[str, int] = {}
        for row in page["content"]:
            assert isinstance(row, Mapping)
            type_code = str(row["typecode"])
            grouped[type_code] = grouped.get(type_code, 0) + 1
        counts = tuple(grouped.items())
    return _jsonp(
        [
            [page],
            [
                {"typecode": type_code, "num": count}
                for type_code, count in counts
            ],
            start,
            end,
        ]
    )


def _mapping_html(
    *,
    old_code: str = "835685",
    new_code: str = "920685",
) -> bytes:
    return (
        "<table><tr><th>序号</th><th>证券简称</th><th>上市日期</th>"
        "<th>旧代码</th><th>新代码</th></tr>"
        "<tr><td>1</td><td>新芝生物</td><td>2022/10/10</td>"
        f"<td>{old_code}</td><td>{new_code}</td></tr></table>"
    ).encode()


def test_complete_pages_emit_only_full_day_transitions_and_one_batch_hash() -> None:
    pages = {
        0: _payload(
            _page(
                [
                    _row("0600", "2026-07-16", comments="长期停牌"),
                    _row(
                        "9001",
                        "2026-07-22",
                        comments="自10时09分08秒起临时停牌，10时19分08秒复牌",
                    ),
                ],
                total_pages=2,
                total_elements=3,
                size=2,
            ),
            counts=(("0600", 1), ("0700", 1), ("9001", 1)),
        ),
        1: _payload(
            _page(
                [_row("0700", "2026-07-30")],
                number=1,
                total_pages=2,
                total_elements=3,
                size=2,
            ),
            counts=(("0600", 1), ("0700", 1), ("9001", 1)),
        ),
    }
    requested_pages: list[int] = []

    def fetch_page(**kwargs: Any) -> bytes:
        requested_pages.append(kwargs["page"])
        return pages[kwargs["page"]]

    batch = BseSuspensionEventSource(
        page_fetcher=fetch_page,
        mapping_fetcher=_mapping_html,
    ).fetch_batch(
        code="920685",
        market=MarketCode.BSE,
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
    )

    assert requested_pages == [0, 1]
    assert [(event.kind, event.effective_on) for event in batch.events] == [
        (SuspensionEventKind.FULL_DAY_START, date(2026, 7, 16)),
        (SuspensionEventKind.FULL_DAY_RESUME, date(2026, 7, 30)),
    ]
    assert all(event.content_hash == batch.content_hash for event in batch.events)
    assert batch.source_url == BSE_MARKET_CALENDAR_PAGE_URL
    assert len(batch.content_hash) == 64


def test_official_mapping_accepts_historical_old_code_rows() -> None:
    source = BseSuspensionEventSource(
        page_fetcher=lambda **_: _payload(
            _page(
                [
                    _row(
                        "0600",
                        "2026-07-16",
                        code="835685",
                        comments="长期停牌",
                    )
                ]
            )
        ),
        mapping_fetcher=_mapping_html,
    )

    events = source.fetch_events(
        code="920685",
        market=MarketCode.BSE,
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
    )

    assert len(events) == 1
    assert events[0].code == "920685"


def test_empty_complete_official_window_is_a_hashed_empty_batch() -> None:
    source = BseSuspensionEventSource(
        page_fetcher=lambda **_: _payload(
            _page([], total_pages=0),
        ),
        mapping_fetcher=_mapping_html,
    )

    batch = source.fetch_batch(
        code="920685",
        market=MarketCode.BSE,
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
    )

    assert batch.events == ()
    assert len(batch.content_hash) == 64


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (
            _payload(
                _page([], total_pages=0),
                start="2026-07-17",
            ),
            "window",
        ),
        (
            _payload(
                _page([_row("0600", "2026-07-16", code="920999")]),
            ),
            "identity",
        ),
        (
            _payload(
                _page(
                    [_row("0600", "2026-07-16")],
                    total_pages=2,
                    total_elements=2,
                )
            ),
            "pagination",
        ),
        (
            _payload(
                _page([], total_pages=1, total_elements=0),
                counts=(),
            ),
            "pagination",
        ),
        (
            _payload(
                _page([], total_pages=0),
                counts=(("0600", 1),),
            ),
            "count",
        ),
    ],
)
def test_malformed_official_batch_fails_closed(
    raw: bytes,
    message: str,
) -> None:
    source = BseSuspensionEventSource(
        page_fetcher=lambda **_: raw,
        mapping_fetcher=_mapping_html,
    )

    with pytest.raises(BseSuspensionEventSourceError, match=message):
        source.fetch_batch(
            code="920685",
            market=MarketCode.BSE,
            start=date(2026, 7, 16),
            end=date(2026, 7, 30),
        )


def test_bse_events_feed_the_existing_continuous_ledger() -> None:
    batch = BseSuspensionEventSource(
        page_fetcher=lambda **_: _payload(
            _page(
                [
                    _row("0600", "2026-07-16", comments="长期停牌"),
                    _row("0700", "2026-07-30"),
                ]
            )
        ),
        mapping_fetcher=_mapping_html,
    ).fetch_batch(
        code="920685",
        market=MarketCode.BSE,
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
    )
    ledger = SuspensionStatusLedger(
        lifecycle=OfficialSecurityLifecycleEvidence(
            code="920685",
            market=MarketCode.BSE,
            listed_on=date(2022, 10, 10),
            source_url="https://www.bse.cn/nq/listedcompany.html",
            content_hash="a" * 64,
        ),
        checkpoint=OfficialSecurityStateCheckpoint(
            code="920685",
            market=MarketCode.BSE,
            state_on=date(2026, 7, 16),
            state=SecurityTradingState.ACTIVE,
            source_url="ledger://BSE/920685/2026-07-16",
            content_hash="b" * 64,
        ),
        batches=(batch,),
    )

    window = ledger.build_window(
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
        market_open_dates=(
            date(2026, 7, 16),
            date(2026, 7, 17),
            date(2026, 7, 29),
            date(2026, 7, 30),
        ),
    )

    assert window.full_day_suspensions == (
        date(2026, 7, 16),
        date(2026, 7, 17),
        date(2026, 7, 29),
    )


def test_mapping_parser_ignores_unrelated_html_tables() -> None:
    mapping = (
        b"<table><tr><th>date</th><th>code</th><th>other</th></tr>"
        b"<tr><td>2026-01-01</td><td>123456</td><td>654321</td></tr></table>"
        + _mapping_html()
    )
    source = BseSuspensionEventSource(
        page_fetcher=lambda **_: _payload(_page([])),
        mapping_fetcher=lambda: mapping,
    )

    assert source.fetch_events(
        code="920685",
        market=MarketCode.BSE,
        start=date(2026, 7, 16),
        end=date(2026, 7, 30),
    ) == ()


def test_mapping_parser_rejects_official_header_drift() -> None:
    drifted = _mapping_html().replace("旧代码".encode(), "曾用代码".encode())
    source = BseSuspensionEventSource(
        page_fetcher=lambda **_: _payload(_page([])),
        mapping_fetcher=lambda: drifted,
    )

    with pytest.raises(BseSuspensionEventSourceError, match="mapping"):
        source.fetch_events(
            code="920685",
            market=MarketCode.BSE,
            start=date(2026, 7, 16),
            end=date(2026, 7, 30),
        )

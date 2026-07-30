"""CNINFO official suspension/resumption event evidence tests."""

from datetime import date
from typing import Any

import pytest

from src.data.kline import MarketCode
from src.data.providers.cninfo import CNINFO_QUERY_URL
from src.data.providers.cninfo_status import (
    CninfoSuspensionEventSource,
    OfficialDocument,
    SuspensionEventKind,
    SuspensionEventSourceError,
)


def _announcement(
    announcement_id: str,
    title: str,
    attachment: str,
) -> dict[str, Any]:
    return {
        "secCode": "300996",
        "secName": "普联软件",
        "announcementTitle": title,
        "announcementTime": 1785254400000,
        "announcementId": announcement_id,
        "orgId": "9900030872",
        "adjunctUrl": attachment,
    }


def test_extracts_auditable_full_day_start_and_resume_events() -> None:
    payload = {
        "totalAnnouncement": 4,
        "announcements": [
            _announcement(
                "1225441186",
                "关于筹划公司控制权变更事项的停牌公告",
                "finalpage/2026-07-25/1225441186.PDF",
            ),
            _announcement(
                "1225444567",
                "关于筹划公司控制权变更事项暨继续停牌的公告",
                "finalpage/2026-07-29/1225444567.PDF",
            ),
            _announcement(
                "1225447322",
                "关于筹划控制权变更事项进展暨复牌及恢复转股的公告",
                "finalpage/2026-07-30/1225447322.PDF",
            ),
            _announcement(
                "1225441185",
                "关于普联转债暂停转股的公告",
                "finalpage/2026-07-25/1225441185.PDF",
            ),
        ],
    }
    documents = {
        "1225441186.PDF": OfficialDocument(
            text=(
                "公司股票（证券代码：300996）自2026 年7 月27日"
                "（星期一）开市起停牌，预计停牌时间不超过2个交易日。"
            ),
            content_hash="a" * 64,
        ),
        "1225444567.PDF": OfficialDocument(
            text=(
                "公司股票（证券代码：300996）自2026 年7 月29 日"
                "（星期三）开市起继续停牌。"
            ),
            content_hash="b" * 64,
        ),
        "1225447322.PDF": OfficialDocument(
            text=(
                "公司股票（股票代码：300996）自2026 年7 月30 日"
                "（星期四）开市起复牌。"
            ),
            content_hash="c" * 64,
        ),
    }

    def fetch_document(url: str) -> OfficialDocument:
        return documents[url.rsplit("/", 1)[-1]]

    events = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=fetch_document,
    ).fetch_events(
        code="300996",
        market=MarketCode.SZSE,
        start=date(2026, 7, 20),
        end=date(2026, 7, 30),
    )

    assert [(event.kind, event.effective_on) for event in events] == [
        (SuspensionEventKind.FULL_DAY_START, date(2026, 7, 27)),
        (SuspensionEventKind.FULL_DAY_START, date(2026, 7, 29)),
        (SuspensionEventKind.FULL_DAY_RESUME, date(2026, 7, 30)),
    ]
    assert events[0].source_url.endswith("1225441186.PDF")
    assert events[0].content_hash == "a" * 64
    assert all(event.code == "300996" for event in events)
    assert all(event.market is MarketCode.SZSE for event in events)


def test_complete_query_returns_a_hashed_natural_date_batch() -> None:
    payload = {
        "totalAnnouncement": 1,
        "announcements": [
            _announcement(
                "1225441186",
                "关于筹划公司控制权变更事项的停牌公告",
                "finalpage/2026-07-25/1225441186.PDF",
            )
        ],
    }
    source = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda _: OfficialDocument(
            text=(
                "公司股票（证券代码：300996）自2026 年7 月27日"
                "（星期一）开市起停牌。"
            ),
            content_hash="a" * 64,
        ),
    )

    batch = source.fetch_batch(
        code="300996",
        market=MarketCode.SZSE,
        start=date(2026, 7, 20),
        end=date(2026, 7, 30),
    )

    assert batch.coverage_start == date(2026, 7, 20)
    assert batch.coverage_end == date(2026, 7, 30)
    assert batch.source_url == CNINFO_QUERY_URL
    assert len(batch.content_hash) == 64
    assert batch.events[0].effective_on == date(2026, 7, 27)


def test_fails_closed_when_candidate_has_no_explicit_effective_date() -> None:
    payload = {
        "totalAnnouncement": 1,
        "announcements": [
            _announcement(
                "1",
                "关于重大事项停牌的公告",
                "finalpage/2026-07-25/1.PDF",
            )
        ],
    }
    source = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda _: OfficialDocument(
            text="公司拟申请停牌，具体时间另行公告。",
            content_hash="d" * 64,
        ),
    )

    with pytest.raises(SuspensionEventSourceError, match="effective date"):
        source.fetch_events(
            code="300996",
            market=MarketCode.SZSE,
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
        )


def test_rejects_unverified_bse_coverage_instead_of_guessing() -> None:
    source = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 0,
            "announcements": [],
        },
        document_fetcher=lambda _: OfficialDocument(
            text="",
            content_hash="e" * 64,
        ),
    )

    with pytest.raises(SuspensionEventSourceError, match="BSE"):
        source.fetch_events(
            code="920176",
            market=MarketCode.BSE,
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
        )


def test_malformed_or_incomplete_official_payload_fails_closed() -> None:
    source = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [],
        },
        document_fetcher=lambda _: OfficialDocument(
            text="",
            content_hash="f" * 64,
        ),
    )

    with pytest.raises(SuspensionEventSourceError, match="totalAnnouncement"):
        source.fetch_events(
            code="600000",
            market=MarketCode.SSE,
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
        )


def test_document_failure_is_visible_and_does_not_return_partial_events() -> None:
    payload = {
        "totalAnnouncement": 1,
        "announcements": [
            _announcement(
                "1",
                "股票停牌公告",
                "finalpage/2026-07-25/1.PDF",
            )
        ],
    }

    def fail_document(_: str) -> OfficialDocument:
        raise TimeoutError("official PDF timed out")

    source = CninfoSuspensionEventSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=fail_document,
    )

    with pytest.raises(SuspensionEventSourceError, match="official PDF timed out"):
        source.fetch_events(
            code="300996",
            market=MarketCode.SZSE,
            start=date(2026, 7, 20),
            end=date(2026, 7, 30),
        )

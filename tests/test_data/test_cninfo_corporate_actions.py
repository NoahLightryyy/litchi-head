"""CNINFO official corporate-action document parsing tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.data.kline import MarketCode
from src.data.providers.cninfo_actions import (
    CninfoCorporateActionSource,
    CorporateActionSourceError,
)
from src.data.providers.cninfo_status import OfficialDocument


def _announcement(
    *,
    announcement_id: str = "1225352449",
    title: str = "2025年年度权益分派实施公告",
    attachment: str = "finalpage/2026-06-05/1225352449.PDF",
    code: str = "000001",
    name: str = "平安银行",
    org_id: str = "gssz0000001",
    announcement_time: int = 1780588800000,
) -> dict[str, Any]:
    return {
        "secCode": code,
        "secName": name,
        "announcementTitle": title,
        "announcementTime": announcement_time,
        "announcementId": announcement_id,
        "orgId": org_id,
        "adjunctUrl": attachment,
    }


def test_parses_sse_table_distribution_without_szse_section_headings() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [
                _announcement(
                    announcement_id="1224119803",
                    title="2024年年度普通股权益分派实施公告",
                    attachment="finalpage/2025-07-10/1224119803.PDF",
                    code="600000",
                    name="浦发银行",
                    org_id="gssh0600000",
                    announcement_time=1752076800000,
                )
            ],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            重要内容提示：
            每股分配比例 普通股每股现金红利人民币0.41元（含税）
            差异化分红送转：否
            二、分配方案
            本次利润分配以方案实施前的公司普通股总股本30,267,679,579股为基数，
            每股派发现金红利人民币0.41元（含税）。
            三、相关日期
            股份类别 股权登记日 最后交易日 除权（息）日 现金红利发放日
            普通股 2025/7/15 － 2025/7/16 2025/7/16
            """,
            content_hash="b" * 64,
        ),
        clock=lambda: datetime(2025, 7, 16, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="600000",
        market=MarketCode.SSE,
        start=date(2025, 7, 1),
        end=date(2025, 7, 31),
    )[0]

    assert event.record_date == date(2025, 7, 15)
    assert event.ex_date == date(2025, 7, 16)
    assert event.distribution_cash_per_share == Decimal("0.41")
    assert event.adjustment_cash_per_share == Decimal("0.41")


def test_parses_sse_differential_distribution_with_separate_cash_basis() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [
                _announcement(
                    announcement_id="1224715146",
                    title="2025年半年度权益分派实施公告",
                    attachment="finalpage/2025-10-16/1224715146.PDF",
                    code="688008",
                    name="澜起科技",
                    org_id="gssh0600688",
                    announcement_time=1760544000000,
                )
            ],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            是否涉及差异化分红送转：是
            每股现金红利0.20元
            二、分配方案
            3.差异化分红送转方案：
            每10股派发现金红利2.00元（含税）。
            截至本公告披露日，公司总股本为1,145,151,330股，
            回购专用账户的股数为10,871,000股，因此本次发放现金红利的股本基数为
            1,134,280,330股。
            虚拟分派的现金红利=（参与分配的股本总数×实际分派的每股现金红利）÷总股本
            ≈0.1981元/股
            三、相关日期
            股权登记日 除权（息）日 现金红利发放日
            2025/10/21 2025/10/22 2025/10/22
            """,
            content_hash="c" * 64,
        ),
        clock=lambda: datetime(2025, 10, 22, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="688008",
        market=MarketCode.SSE,
        start=date(2025, 10, 1),
        end=date(2025, 10, 31),
    )[0]

    assert event.distribution_cash_per_share == Decimal("0.20")
    assert event.adjustment_cash_per_share == Decimal("0.1981")
    assert event.total_shares == 1_145_151_330
    assert event.participating_shares == 1_134_280_330


def test_parses_cash_from_implementation_section_not_approved_plan() -> None:
    payload = {
        "totalAnnouncement": 1,
        "announcements": [_announcement()],
    }
    text = Path("tests/fixtures/cninfo/000001_1225352449_extracted.txt").read_text(encoding="utf-8")
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: OfficialDocument(
            text=text,
            content_hash=("8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8"),
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    events = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )

    assert len(events) == 1
    event = events[0]
    assert event.action_kind == "cash_dividend"
    assert event.record_date == date(2026, 6, 11)
    assert event.ex_date == date(2026, 6, 12)
    assert event.cash_dividend_per_share == Decimal("0.36000")
    assert str(event.cash_dividend_per_share) == "0.36000"
    assert event.documents[0].external_id == "1225352449"
    assert event.documents[0].content_hash == (
        "8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8"
    )


def test_combines_cash_send_and_transfer_terms_as_one_composite_event() -> None:
    text = """
    二、本次实施的权益分派方案
    本次实施方案为：每10股派1.00元人民币现金（含税），
    每10股送红股2股，并以资本公积金每10股转增3股。
    三、股权登记日与除权除息日
    股权登记日为：2026年6月11日，除权除息日为：2026年6月12日。
    """
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text=text,
            content_hash="a" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert event.action_kind == "composite"
    assert event.cash_dividend_per_share == Decimal("0.100")
    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (3, 2)


def test_parses_share_only_distribution_without_inventing_cash() -> None:
    text = """
    二、本次实施的权益分派方案
    本次实施方案为：以资本公积金向全体股东每10股转增4股，不派发现金红利。
    三、股权登记日与除权除息日
    股权登记日为2026年6月11日，除权除息日为2026年6月12日。
    """
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text=text,
            content_hash="b" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert event.action_kind == "share_change"
    assert event.cash_dividend_per_share is None
    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (7, 5)


def test_aggregates_complementary_notices_by_ex_date_after_all_downloads() -> None:
    payload = {
        "totalAnnouncement": 2,
        "announcements": [
            _announcement(
                announcement_id="cash",
                attachment="finalpage/2026-06-05/cash.PDF",
            ),
            _announcement(
                announcement_id="shares",
                attachment="finalpage/2026-06-06/shares.PDF",
            ),
        ],
    }
    documents = {
        "cash.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派2.00元人民币现金，不送红股，不转增股本。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="c" * 64,
        ),
        "shares.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股转增5股，不派发现金红利。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="d" * 64,
        ),
    }
    downloaded: set[str] = set()

    def fetch_document(url: str) -> OfficialDocument:
        filename = url.rsplit("/", 1)[-1]
        downloaded.add(filename)
        return documents[filename]

    def collected_after_downloads() -> datetime:
        assert downloaded == {"cash.PDF", "shares.PDF"}
        return datetime(2026, 6, 12, 2, 0, tzinfo=UTC)

    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=fetch_document,
        clock=collected_after_downloads,
    )

    events = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )

    assert len(events) == 1
    event = events[0]
    assert event.action_id == "cninfo:000001:2026-06-12"
    assert event.action_kind == "composite"
    assert event.cash_dividend_per_share == Decimal("0.200")
    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (3, 2)
    assert [document.external_id for document in event.documents] == [
        "cash",
        "shares",
    ]
    assert event.collected_at == datetime(2026, 6, 12, 2, 0, tzinfo=UTC)


def test_rejects_invalid_or_mismatched_instrument_before_network() -> None:
    def unexpected_fetch(**_: str) -> dict[str, Any]:
        raise AssertionError("network must not be called")

    source = CninfoCorporateActionSource(
        announcement_fetcher=unexpected_fetch,
    )

    for code, market in (
        ("ABCDEF", MarketCode.SZSE),
        ("600000", MarketCode.SZSE),
        ("920016", MarketCode.BSE),
    ):
        with pytest.raises(
            CorporateActionSourceError,
            match="code|market|BSE|SSE",
        ):
            source.fetch_events(
                code=code,
                market=market,
                start=date(2026, 5, 1),
                end=date(2026, 6, 30),
            )


@pytest.mark.parametrize(
    "title",
    [
        "关于2025年年度权益分派实施公告的更正公告",
        "2025年年度权益分派延期实施公告",
        "关于终止2025年年度权益分派的公告",
        "2025年年度权益分派实施日期调整公告",
    ],
)
def test_fails_closed_on_lifecycle_notice_instead_of_faking_revision(
    title: str,
) -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [
                _announcement(
                    title=title,
                )
            ],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="不应解析",
            content_hash="e" * 64,
        ),
    )

    with pytest.raises(CorporateActionSourceError, match="revision|lifecycle"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_correction_chain_uses_linked_corrected_full_implementation() -> None:
    payload = {
        "totalAnnouncement": 3,
        "announcements": [
            _announcement(
                announcement_id="original",
                attachment="original.PDF",
                announcement_time=1780588800000,
            ),
            _announcement(
                announcement_id="correction",
                title="关于2025年年度权益分派实施公告的更正公告",
                attachment="correction.PDF",
                announcement_time=1780675200000,
            ),
            _announcement(
                announcement_id="corrected-full",
                title="2025年年度权益分派实施公告（更正后）",
                attachment="corrected-full.PDF",
                announcement_time=1780761600000,
            ),
        ],
    }
    documents = {
        "original.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派1.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="1" * 64,
        ),
        "correction.PDF": OfficialDocument(
            text="""
            现对公告ID original《2025年年度权益分派实施公告》进行更正，
            更正后的完整实施公告与本公告同时披露。
            """,
            content_hash="2" * 64,
        ),
        "corrected-full.PDF": OfficialDocument(
            text="""
            本公告为公告ID correction 对应的更正后完整实施公告。
            二、本次实施的权益分派方案
            每10股派2.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月12日，除权除息日为2026年6月13日。
            """,
            content_hash="3" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
        clock=lambda: datetime(2026, 6, 13, 1, 0, tzinfo=UTC),
    )

    events = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )

    assert len(events) == 1
    event = events[0]
    assert event.action_id == "cninfo:000001:original"
    assert event.revision == 3
    assert event.record_date == date(2026, 6, 12)
    assert event.ex_date == date(2026, 6, 13)
    assert event.distribution_cash_per_share == Decimal("0.200")
    assert [document.external_id for document in event.documents] == ["corrected-full"]


@pytest.mark.parametrize(
    ("title", "status_word"),
    [
        ("2025年年度权益分派延期实施公告", "延期"),
        ("关于终止2025年年度权益分派的公告", "终止"),
        ("关于取消2025年年度权益分派的公告", "取消"),
    ],
)
def test_linked_terminal_lifecycle_notice_suppresses_active_event(
    title: str,
    status_word: str,
) -> None:
    payload = {
        "totalAnnouncement": 2,
        "announcements": [
            _announcement(announcement_id="original", attachment="original.PDF"),
            _announcement(
                announcement_id="terminal",
                title=title,
                attachment="terminal.PDF",
                announcement_time=1780675200000,
            ),
        ],
    }
    documents = {
        "original.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派1.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="4" * 64,
        ),
        "terminal.PDF": OfficialDocument(
            text=f"本公司决定{status_word}公告ID original 对应的权益分派实施安排。",
            content_hash="5" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
    )

    assert (
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )
        == ()
    )


def test_lifecycle_notice_linking_multiple_implementations_fails_closed() -> None:
    payload = {
        "totalAnnouncement": 3,
        "announcements": [
            _announcement(announcement_id="first", attachment="first.PDF"),
            _announcement(
                announcement_id="second",
                title="2024年年度权益分派实施公告",
                attachment="second.PDF",
            ),
            _announcement(
                announcement_id="correction",
                title="权益分派实施公告更正公告",
                attachment="correction.PDF",
                announcement_time=1780675200000,
            ),
        ],
    }
    documents = {
        "first.PDF": OfficialDocument(text="原公告一", content_hash="6" * 64),
        "second.PDF": OfficialDocument(text="原公告二", content_hash="7" * 64),
        "correction.PDF": OfficialDocument(
            text="更正公告ID first 及公告ID second 所载事项。",
            content_hash="8" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
    )

    with pytest.raises(CorporateActionSourceError, match="unique|ambiguous|link"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_lifecycle_link_uses_exact_announcement_identity_boundaries() -> None:
    payload = {
        "totalAnnouncement": 3,
        "announcements": [
            _announcement(announcement_id="123", attachment="123.PDF"),
            _announcement(
                announcement_id="1234",
                title="2024年年度权益分派实施公告",
                attachment="1234.PDF",
            ),
            _announcement(
                announcement_id="terminal",
                title="关于终止2024年年度权益分派的公告",
                attachment="terminal.PDF",
                announcement_time=1780675200000,
            ),
        ],
    }
    documents = {
        "123.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派1.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="9" * 64,
        ),
        "1234.PDF": OfficialDocument(text="原公告二", content_hash="a" * 64),
        "terminal.PDF": OfficialDocument(
            text="终止公告ID 1234 对应的权益分派。",
            content_hash="b" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
    )

    events = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )

    assert len(events) == 1
    assert events[0].documents[0].external_id == "123"


def test_lifecycle_notice_cannot_supersede_a_later_implementation() -> None:
    payload = {
        "totalAnnouncement": 2,
        "announcements": [
            _announcement(
                announcement_id="original",
                attachment="original.PDF",
                announcement_time=1780761600000,
            ),
            _announcement(
                announcement_id="terminal",
                title="关于终止2025年年度权益分派的公告",
                attachment="terminal.PDF",
                announcement_time=1780675200000,
            ),
        ],
    }
    documents = {
        "original.PDF": OfficialDocument(text="原公告", content_hash="c" * 64),
        "terminal.PDF": OfficialDocument(
            text="终止公告ID original 对应的权益分派。",
            content_hash="d" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
    )

    with pytest.raises(CorporateActionSourceError, match="chronology|later|link"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_lifecycle_notice_backfills_prior_official_implementation() -> None:
    calls: list[tuple[str, str]] = []

    def fetch_announcements(**kwargs: str) -> dict[str, Any]:
        calls.append((kwargs["start_date"], kwargs["end_date"]))
        if kwargs["start_date"] == "20260601":
            announcements = [
                _announcement(
                    announcement_id="terminal",
                    title="关于终止2025年年度权益分派的公告",
                    attachment="terminal.PDF",
                    announcement_time=1780675200000,
                )
            ]
        else:
            announcements = [
                _announcement(
                    announcement_id="original",
                    attachment="original.PDF",
                    announcement_time=1779724800000,
                )
            ]
        return {
            "totalAnnouncement": len(announcements),
            "announcements": announcements,
        }

    documents = {
        "original.PDF": OfficialDocument(text="原实施公告", content_hash="e" * 64),
        "terminal.PDF": OfficialDocument(
            text="终止公告ID original 对应的权益分派。",
            content_hash="f" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=fetch_announcements,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
    )

    assert (
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
        )
        == ()
    )
    assert calls == [("20260601", "20260630"), ("20250601", "20260531")]


def test_fails_closed_when_same_ex_date_notices_disagree_on_terms() -> None:
    payload = {
        "totalAnnouncement": 2,
        "announcements": [
            _announcement(
                announcement_id="first",
                attachment="first.PDF",
            ),
            _announcement(
                announcement_id="second",
                attachment="second.PDF",
            ),
        ],
    }
    documents = {
        "first.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派1.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="1" * 64,
        ),
        "second.PDF": OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派2.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="2" * 64,
        ),
    }
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: payload,
        document_fetcher=lambda url: documents[url.rsplit("/", 1)[-1]],
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    with pytest.raises(CorporateActionSourceError, match="conflict"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_parses_rights_issue_from_final_issuance_schedule_not_board_plan() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [
                _announcement(
                    title="2026年度配股发行公告",
                    attachment="rights.PDF",
                )
            ],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            一、董事会审议通过的配股预案
            预案按每10股配售5股，配股价格为6.00元/股。
            二、本次配股发行方案
            本次配股以股权登记日收市后总股本为基数，按每10股配售3股的比例配售。
            配股价格：8.25元/股。
            配股股权登记日：2026年6月11日，配股除权日：2026年6月12日。
            """,
            content_hash="3" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert event.action_kind == "rights_issue"
    assert event.record_date == date(2026, 6, 11)
    assert event.ex_date == date(2026, 6, 12)
    assert event.rights_ratio_numerator == 3
    assert event.rights_ratio_denominator == 10
    assert event.rights_subscription_price == Decimal("8.25")


def test_dates_are_read_only_from_final_registration_section() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            一、前次分派回顾
            前次股权登记日为2025年6月10日，除权除息日为2025年6月11日。
            二、本次实施的权益分派方案
            本次每10股派3.6000元人民币现金。
            三、股权登记日与除权除息日
            本次股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            四、权益分派对象
            """,
            content_hash="4" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert event.record_date == date(2026, 6, 11)
    assert event.ex_date == date(2026, 6, 12)


def test_fails_closed_on_differential_distribution_basis() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            公司回购专用证券账户中的股份不参与本次权益分派。
            向参与分派股东每10股派14.50元，并每10股转增4股。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="5" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    with pytest.raises(CorporateActionSourceError, match="differential"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_fails_closed_on_multiple_different_terms_inside_final_section() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            A类股每10股派1.00元人民币现金，B类股每10股派2.00元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="6" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    with pytest.raises(CorporateActionSourceError, match="conflict"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_repeated_identical_share_term_is_not_applied_twice() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            本次每10股转增4股。即向全体股东每10股转增4股。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="7" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert (
        event.share_ratio_numerator,
        event.share_ratio_denominator,
    ) == (7, 5)


def test_tax_amount_before_gross_amount_does_not_change_cash_term() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            扣税后每10股派3.2400元；本次向全体股东每10股派3.6000元人民币现金
            （含税）。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="8" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    event = source.fetch_events(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 5, 1),
        end=date(2026, 6, 30),
    )[0]

    assert str(event.cash_dividend_per_share) == "0.36000"


def test_conflicting_dates_inside_final_section_fail_closed() -> None:
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [_announcement()],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派3.6000元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，另列股权登记日为2026年6月12日，
            除权除息日为2026年6月13日。
            """,
            content_hash="9" * 64,
        ),
        clock=lambda: datetime(2026, 6, 13, 1, 0, tzinfo=UTC),
    )

    with pytest.raises(CorporateActionSourceError, match="conflict"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


def test_duplicate_announcement_identity_cannot_masquerade_as_complete_pages() -> None:
    duplicate = _announcement(
        announcement_id="duplicate",
        title="董事会决议公告",
    )
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 2,
            "announcements": [duplicate, duplicate],
        },
    )

    with pytest.raises(CorporateActionSourceError, match="duplicate"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )


@pytest.mark.parametrize("invalid_id", [None, True, {}, []])
def test_rejects_non_text_announcement_identity(
    invalid_id: object,
) -> None:
    announcement = _announcement()
    announcement["announcementId"] = invalid_id
    source = CninfoCorporateActionSource(
        announcement_fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [announcement],
        },
        document_fetcher=lambda url: OfficialDocument(
            text="""
            二、本次实施的权益分派方案
            每10股派3.6000元人民币现金。
            三、股权登记日与除权除息日
            股权登记日为2026年6月11日，除权除息日为2026年6月12日。
            """,
            content_hash="a" * 64,
        ),
        clock=lambda: datetime(2026, 6, 12, 1, 0, tzinfo=UTC),
    )

    with pytest.raises(CorporateActionSourceError, match="announcementId"):
        source.fetch_events(
            code="000001",
            market=MarketCode.SZSE,
            start=date(2026, 5, 1),
            end=date(2026, 6, 30),
        )

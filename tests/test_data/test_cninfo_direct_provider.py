"""CNINFO 公开端点直连公告适配器测试。"""

from datetime import UTC, datetime
from typing import Any

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.cninfo import CninfoDirectAnnouncementSource


def _request(
    capability: EvidenceCapability = EvidenceCapability.ANNOUNCEMENT,
) -> EvidenceRequest:
    return EvidenceRequest(
        capability=capability,
        stock_code="000001",
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 7, 28, 23, 59, tzinfo=UTC),
    )


def test_direct_descriptor_preserves_adapter_and_real_upstream_identity() -> None:
    source = CninfoDirectAnnouncementSource(fetcher=lambda **_: {})

    assert source.descriptor.source_id == "cninfo-direct"
    assert source.descriptor.upstream_id == "cninfo"
    assert source.descriptor.capabilities == {EvidenceCapability.ANNOUNCEMENT}
    assert source.descriptor.discovery_only is False


def test_direct_fetch_maps_public_response_to_announcement_items() -> None:
    calls: list[dict[str, str]] = []

    def fetcher(**kwargs: str) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "totalAnnouncement": 1,
            "announcements": [
                {
                    "secCode": "000001",
                    "secName": "平安银行",
                    "announcementTitle": "2026年半年度报告",
                    "announcementTime": 1785234600000,
                    "announcementId": "1212345678",
                    "orgId": "gssz0000001",
                    "adjunctUrl": "finalpage/2026-07-28/1212345678.PDF",
                }
            ],
        }

    result = CninfoDirectAnnouncementSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.source_id == "cninfo-direct"
    assert result.upstream_id == "cninfo"
    assert calls == [
        {
            "symbol": "000001",
            "start_date": "20260701",
            "end_date": "20260729",
        }
    ]
    assert len(result.items) == 1
    item = result.items[0]
    assert item.external_id == "1212345678"
    assert item.stock_code == "000001"
    assert item.stock_name == "平安银行"
    assert item.title == "2026年半年度报告"
    assert item.published_at.isoformat() == "2026-07-28T18:30:00+08:00"
    assert item.source_name == "巨潮资讯"
    assert item.url == (
        "https://www.cninfo.com.cn/new/disclosure/detail?"
        "stockCode=000001&announcementId=1212345678&orgId=gssz0000001"
    )
    assert item.attachment_url == (
        "https://static.cninfo.com.cn/"
        "finalpage/2026-07-28/1212345678.PDF"
    )


def test_direct_explicit_zero_total_is_success_empty() -> None:
    source = CninfoDirectAnnouncementSource(
        fetcher=lambda **_: {
            "totalAnnouncement": 0,
            "announcements": [],
        }
    )

    result = source.fetch(_request())

    assert result.status is SourceStatus.SUCCESS_EMPTY
    assert result.items == []
    assert result.error_message is None


def test_direct_zero_total_with_items_is_invalid_payload() -> None:
    source = CninfoDirectAnnouncementSource(
        fetcher=lambda **_: {
            "totalAnnouncement": 0,
            "announcements": [
                {
                    "secCode": "000001",
                    "secName": "平安银行",
                    "announcementTitle": "不应出现",
                    "announcementTime": 1785234600000,
                    "announcementId": "1212345678",
                    "orgId": "gssz0000001",
                }
            ],
        }
    )

    result = source.fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "totalAnnouncement" in (result.error_message or "")


def test_direct_positive_total_without_items_is_invalid_payload() -> None:
    source = CninfoDirectAnnouncementSource(
        fetcher=lambda **_: {
            "totalAnnouncement": 1,
            "announcements": [],
        }
    )

    result = source.fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "announcements" in (result.error_message or "")


def test_direct_network_exception_is_visible_failure() -> None:
    def failing_fetcher(**_: str) -> dict[str, Any]:
        raise TimeoutError("cninfo direct request timed out")

    result = CninfoDirectAnnouncementSource(fetcher=failing_fetcher).fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.items == []
    assert result.error_code == "upstream_request_failed"
    assert result.error_message == "cninfo direct request timed out"


def test_direct_missing_total_is_invalid_payload() -> None:
    source = CninfoDirectAnnouncementSource(
        fetcher=lambda **_: {"announcements": []}
    )

    result = source.fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "totalAnnouncement" in (result.error_message or "")


def test_direct_unsupported_capability_does_not_call_upstream() -> None:
    called = False

    def fetcher(**_: str) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"totalAnnouncement": 0, "announcements": []}

    result = CninfoDirectAnnouncementSource(fetcher=fetcher).fetch(
        _request(EvidenceCapability.NEWS)
    )

    assert result.status is SourceStatus.UNSUPPORTED
    assert called is False

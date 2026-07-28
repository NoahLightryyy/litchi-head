"""CNINFO 公告证据适配器测试。"""

from datetime import UTC, datetime

import pandas as pd

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.providers.cninfo import CninfoAnnouncementSource


def _request(
    capability: EvidenceCapability = EvidenceCapability.ANNOUNCEMENT,
) -> EvidenceRequest:
    return EvidenceRequest(
        capability=capability,
        stock_code="000001",
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 7, 28, 23, 59, tzinfo=UTC),
    )


def test_descriptor_preserves_adapter_and_real_upstream_identity() -> None:
    source = CninfoAnnouncementSource(fetcher=lambda **_: pd.DataFrame())

    assert source.descriptor.source_id == "akshare-cninfo"
    assert source.descriptor.upstream_id == "cninfo"
    assert source.descriptor.capabilities == {EvidenceCapability.ANNOUNCEMENT}
    assert source.descriptor.discovery_only is False


def test_fetch_maps_cninfo_frame_to_announcement_items() -> None:
    calls: list[dict[str, str]] = []

    def fetcher(**kwargs: str) -> pd.DataFrame:
        calls.append(kwargs)
        return pd.DataFrame(
            [
                {
                    "代码": "000001",
                    "简称": "平安银行",
                    "公告标题": "2026年半年度报告",
                    "公告时间": "2026-07-28 18:30:00",
                    "公告链接": (
                        "http://www.cninfo.com.cn/new/disclosure/detail?"
                        "stockCode=000001&announcementId=1212345678&orgId=gssz0000001"
                    ),
                }
            ]
        )

    result = CninfoAnnouncementSource(fetcher=fetcher).fetch(_request())

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.source_id == "akshare-cninfo"
    assert result.upstream_id == "cninfo"
    assert calls == [
        {
            "symbol": "000001",
            "market": "沪深京",
            "keyword": "",
            "category": "",
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


def test_empty_frame_is_success_empty_not_failure() -> None:
    source = CninfoAnnouncementSource(fetcher=lambda **_: pd.DataFrame())

    result = source.fetch(_request())

    assert result.status is SourceStatus.SUCCESS_EMPTY
    assert result.items == []
    assert result.error_message is None


def test_network_exception_is_visible_failure() -> None:
    def failing_fetcher(**_: str) -> pd.DataFrame:
        raise TimeoutError("cninfo request timed out")

    result = CninfoAnnouncementSource(fetcher=failing_fetcher).fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.items == []
    assert result.error_code == "upstream_request_failed"
    assert result.error_message == "cninfo request timed out"


def test_unsupported_capability_does_not_call_upstream() -> None:
    called = False

    def fetcher(**_: str) -> pd.DataFrame:
        nonlocal called
        called = True
        return pd.DataFrame()

    result = CninfoAnnouncementSource(fetcher=fetcher).fetch(
        _request(EvidenceCapability.NEWS)
    )

    assert result.status is SourceStatus.UNSUPPORTED
    assert called is False


def test_missing_explicit_time_window_is_failed_request() -> None:
    source = CninfoAnnouncementSource(fetcher=lambda **_: pd.DataFrame())

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.ANNOUNCEMENT,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_request"
    assert "start_at" in (result.error_message or "")


def test_missing_stock_code_is_failed_request() -> None:
    source = CninfoAnnouncementSource(fetcher=lambda **_: pd.DataFrame())

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.ANNOUNCEMENT,
            start_at=datetime(2026, 7, 1, tzinfo=UTC),
            end_at=datetime(2026, 7, 28, tzinfo=UTC),
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_request"
    assert "stock_code" in (result.error_message or "")


def test_malformed_row_fails_whole_source_result() -> None:
    malformed = pd.DataFrame(
        [
            {
                "代码": "000001",
                "简称": "平安银行",
                "公告标题": "缺少公告编号",
                "公告时间": "2026-07-28 18:30:00",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail",
            }
        ]
    )

    result = CninfoAnnouncementSource(fetcher=lambda **_: malformed).fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.items == []
    assert result.error_code == "invalid_upstream_payload"
    assert "announcementId" in (result.error_message or "")


def test_missing_required_column_fails_whole_source_result() -> None:
    missing_title = pd.DataFrame(
        [
            {
                "代码": "000001",
                "简称": "平安银行",
                "公告时间": "2026-07-28 18:30:00",
                "公告链接": (
                    "http://www.cninfo.com.cn/new/disclosure/detail?"
                    "announcementId=1212345678"
                ),
            }
        ]
    )

    result = CninfoAnnouncementSource(fetcher=lambda **_: missing_title).fetch(_request())

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "公告标题" in (result.error_message or "")

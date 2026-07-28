"""多源证据契约测试。

这些测试先钉住来源独立性和失败语义，避免把同一上游的多个包装器
误算成多个来源，也避免把采集失败伪装成“成功但没有新闻”。
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.data.evidence import (
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.models import NewsItem


class StubNewsSource:
    """只用于验证注册中心契约的最小新闻源。"""

    def __init__(self, descriptor: SourceDescriptor) -> None:
        self.descriptor = descriptor

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        return SourceResult[NewsItem](
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=request.capability,
            status=SourceStatus.SUCCESS_EMPTY,
            fetched_at=datetime.now(UTC),
        )


def _descriptor(
    source_id: str,
    upstream_id: str,
    *,
    discovery_only: bool = False,
) -> SourceDescriptor:
    return SourceDescriptor(
        source_id=source_id,
        upstream_id=upstream_id,
        display_name=source_id,
        capabilities={EvidenceCapability.NEWS},
        discovery_only=discovery_only,
    )


def _result(
    source_id: str,
    upstream_id: str,
    status: SourceStatus,
    *,
    items: list[NewsItem] | None = None,
    error_message: str | None = None,
) -> SourceResult[NewsItem]:
    return SourceResult[NewsItem](
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.NEWS,
        status=status,
        items=items or [],
        fetched_at=datetime.now(UTC),
        error_message=error_message,
    )


def test_registry_selects_sources_by_declared_capability() -> None:
    registry = EvidenceSourceRegistry()
    news_source = StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney"))
    registry.register(news_source)

    assert registry.sources_for(EvidenceCapability.NEWS) == (news_source,)
    assert registry.sources_for(EvidenceCapability.KLINE) == ()


def test_registry_rejects_duplicate_source_id() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("eastmoney-news", "eastmoney")))

    with pytest.raises(ValueError, match="eastmoney-news"):
        registry.register(StubNewsSource(_descriptor("eastmoney-news", "sina")))


def test_success_data_requires_items() -> None:
    with pytest.raises(ValidationError, match="SUCCESS_DATA"):
        _result("eastmoney-news", "eastmoney", SourceStatus.SUCCESS_DATA)


def test_success_empty_cannot_hide_items() -> None:
    item = NewsItem(code="000001", title="公告", date="2026-07-28")

    with pytest.raises(ValidationError, match="SUCCESS_EMPTY"):
        _result(
            "eastmoney-news",
            "eastmoney",
            SourceStatus.SUCCESS_EMPTY,
            items=[item],
        )


def test_failed_result_requires_visible_error() -> None:
    with pytest.raises(ValidationError, match="error_message"):
        _result("eastmoney-news", "eastmoney", SourceStatus.FAILED)


def test_same_upstream_wrapped_twice_counts_once() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))
    registry.register(StubNewsSource(_descriptor("direct-eastmoney", "eastmoney")))
    registry.register(StubNewsSource(_descriptor("akshare-sina", "sina")))

    assessment = registry.assess(
        EvidencePolicy(
            capability=EvidenceCapability.NEWS,
            min_independent_upstreams=2,
        ),
        [
            _result("akshare-eastmoney", "eastmoney", SourceStatus.SUCCESS_EMPTY),
            _result("direct-eastmoney", "eastmoney", SourceStatus.SUCCESS_EMPTY),
        ],
    )

    assert assessment.complete is False
    assert assessment.successful_upstream_ids == {"eastmoney"}
    assert assessment.missing_independent_upstreams == 1


def test_success_empty_counts_as_a_completed_query() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))
    registry.register(StubNewsSource(_descriptor("akshare-sina", "sina")))

    assessment = registry.assess(
        EvidencePolicy(
            capability=EvidenceCapability.NEWS,
            min_independent_upstreams=2,
        ),
        [
            _result("akshare-eastmoney", "eastmoney", SourceStatus.SUCCESS_EMPTY),
            _result("akshare-sina", "sina", SourceStatus.SUCCESS_EMPTY),
        ],
    )

    assert assessment.complete is True
    assert assessment.successful_upstream_ids == {"eastmoney", "sina"}
    assert assessment.missing_independent_upstreams == 0


def test_failure_and_discovery_only_source_do_not_satisfy_policy() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))
    registry.register(
        StubNewsSource(
            _descriptor("rsshub-finance", "rsshub-community", discovery_only=True)
        )
    )

    assessment = registry.assess(
        EvidencePolicy(
            capability=EvidenceCapability.NEWS,
            min_independent_upstreams=2,
        ),
        [
            _result(
                "akshare-eastmoney",
                "eastmoney",
                SourceStatus.FAILED,
                error_message="连接超时",
            ),
            _result(
                "rsshub-finance",
                "rsshub-community",
                SourceStatus.SUCCESS_EMPTY,
            ),
        ],
    )

    assert assessment.complete is False
    assert assessment.successful_upstream_ids == set()
    assert assessment.failed_source_ids == {"akshare-eastmoney"}
    assert assessment.discovery_only_source_ids == {"rsshub-finance"}


def test_required_authoritative_upstream_must_succeed() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("cninfo-announcements", "cninfo")))
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))
    registry.register(StubNewsSource(_descriptor("akshare-sina", "sina")))

    assessment = registry.assess(
        EvidencePolicy(
            capability=EvidenceCapability.NEWS,
            min_independent_upstreams=2,
            required_upstream_ids={"cninfo"},
        ),
        [
            _result(
                "cninfo-announcements",
                "cninfo",
                SourceStatus.FAILED,
                error_message="上游不可用",
            ),
            _result("akshare-eastmoney", "eastmoney", SourceStatus.SUCCESS_EMPTY),
            _result("akshare-sina", "sina", SourceStatus.SUCCESS_EMPTY),
        ],
    )

    assert assessment.complete is False
    assert assessment.missing_required_upstream_ids == {"cninfo"}


def test_result_cannot_claim_a_different_upstream_than_registered_source() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))

    with pytest.raises(ValueError, match="upstream"):
        registry.assess(
            EvidencePolicy(
                capability=EvidenceCapability.NEWS,
                min_independent_upstreams=1,
            ),
            [
                _result(
                    "akshare-eastmoney",
                    "sina",
                    SourceStatus.SUCCESS_EMPTY,
                )
            ],
        )


def test_assessment_rejects_multiple_final_results_from_same_source() -> None:
    registry = EvidenceSourceRegistry()
    registry.register(StubNewsSource(_descriptor("akshare-eastmoney", "eastmoney")))

    with pytest.raises(ValueError, match="duplicate result.*akshare-eastmoney"):
        registry.assess(
            EvidencePolicy(
                capability=EvidenceCapability.NEWS,
                min_independent_upstreams=1,
            ),
            [
                _result(
                    "akshare-eastmoney",
                    "eastmoney",
                    SourceStatus.FAILED,
                    error_message="第一次请求超时",
                ),
                _result(
                    "akshare-eastmoney",
                    "eastmoney",
                    SourceStatus.SUCCESS_EMPTY,
                ),
            ],
        )

"""多通道证据汇总与统一信封测试。"""

from datetime import UTC, datetime
from threading import Barrier
from typing import Any

import pytest

from src.data.evidence import (
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.evidence_service import DataEvidenceService
from src.data.models import NewsItem


class StubSource:
    """可返回结果、抛错或参与并发屏障的最小来源。"""

    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        outcome: SourceResult[NewsItem] | Exception,
        *,
        barrier: Barrier | None = None,
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.NEWS},
        )
        self._outcome = outcome
        self._barrier = barrier
        self.calls = 0

    def fetch(self, request: EvidenceRequest) -> SourceResult[NewsItem]:
        self.calls += 1
        if self._barrier is not None:
            self._barrier.wait(timeout=1)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _request() -> EvidenceRequest:
    return EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code="000001",
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 7, 29, tzinfo=UTC),
    )


def _policy(min_upstreams: int = 2) -> EvidencePolicy:
    return EvidencePolicy(
        capability=EvidenceCapability.NEWS,
        min_independent_upstreams=min_upstreams,
    )


def _item(title: str) -> NewsItem:
    return NewsItem(
        code="000001",
        title=title,
        date="2026-07-29",
        source="测试来源",
    )


def _result(
    source_id: str,
    upstream_id: str,
    status: SourceStatus,
    *,
    items: list[NewsItem] | None = None,
) -> SourceResult[NewsItem]:
    return SourceResult[NewsItem](
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.NEWS,
        status=status,
        items=items or [],
    )


def _service(*sources: StubSource, max_workers: int = 4) -> DataEvidenceService:
    registry = EvidenceSourceRegistry()
    for source in sources:
        registry.register(source)
    return DataEvidenceService(registry, max_workers=max_workers)


def test_collect_packages_independent_sources_in_registration_order() -> None:
    eastmoney = StubSource(
        "direct-eastmoney",
        "eastmoney",
        _result(
            "direct-eastmoney",
            "eastmoney",
            SourceStatus.SUCCESS_DATA,
            items=[_item("东方财富新闻")],
        ),
    )
    sina = StubSource(
        "direct-sina",
        "sina",
        _result(
            "direct-sina",
            "sina",
            SourceStatus.SUCCESS_DATA,
            items=[_item("新浪新闻")],
        ),
    )

    envelope = _service(eastmoney, sina).collect(_request(), _policy())

    assert envelope.complete is True
    assert envelope.request == _request()
    assert envelope.policy == _policy()
    assert [result.source_id for result in envelope.source_results] == [
        "direct-eastmoney",
        "direct-sina",
    ]
    assert [item.title for item in envelope.items] == [
        "东方财富新闻",
        "新浪新闻",
    ]
    assert envelope.assessment.successful_upstream_ids == {"eastmoney", "sina"}


def test_collect_runs_independent_channels_concurrently() -> None:
    barrier = Barrier(2)
    first = StubSource(
        "source-a",
        "upstream-a",
        _result("source-a", "upstream-a", SourceStatus.SUCCESS_EMPTY),
        barrier=barrier,
    )
    second = StubSource(
        "source-b",
        "upstream-b",
        _result("source-b", "upstream-b", SourceStatus.SUCCESS_EMPTY),
        barrier=barrier,
    )

    envelope = _service(first, second, max_workers=2).collect(
        _request(),
        _policy(),
    )

    assert envelope.complete is True
    assert first.calls == 1
    assert second.calls == 1


def test_collect_keeps_diagnostics_but_emits_one_item_set_per_upstream() -> None:
    wrapped = StubSource(
        "akshare-eastmoney",
        "eastmoney",
        _result(
            "akshare-eastmoney",
            "eastmoney",
            SourceStatus.SUCCESS_DATA,
            items=[_item("包装器版本")],
        ),
    )
    direct = StubSource(
        "direct-eastmoney",
        "eastmoney",
        _result(
            "direct-eastmoney",
            "eastmoney",
            SourceStatus.SUCCESS_DATA,
            items=[_item("直连重复版本")],
        ),
    )

    envelope = _service(wrapped, direct).collect(_request(), _policy())

    assert envelope.complete is False
    assert len(envelope.source_results) == 2
    assert [item.title for item in envelope.items] == ["包装器版本"]
    assert envelope.assessment.successful_upstream_ids == {"eastmoney"}
    assert envelope.assessment.missing_independent_upstreams == 1


def test_collect_turns_unhandled_source_exception_into_visible_failure() -> None:
    broken = StubSource(
        "broken-news",
        "broken-upstream",
        TimeoutError("source timed out"),
    )

    envelope = _service(broken).collect(_request(), _policy(1))

    assert envelope.complete is False
    assert envelope.items == []
    assert len(envelope.source_results) == 1
    failure = envelope.source_results[0]
    assert failure.status is SourceStatus.FAILED
    assert failure.error_code == "source_unhandled_exception"
    assert failure.error_message == "source timed out"
    assert envelope.assessment.failed_source_ids == {"broken-news"}


def test_collect_success_empty_is_complete_and_serializable() -> None:
    empty = StubSource(
        "direct-sina",
        "sina",
        _result("direct-sina", "sina", SourceStatus.SUCCESS_EMPTY),
    )

    envelope = _service(empty).collect(_request(), _policy(1))
    payload: dict[str, Any] = envelope.model_dump(mode="json")

    assert envelope.complete is True
    assert envelope.items == []
    assert payload["request"]["capability"] == "news"
    assert payload["source_results"][0]["status"] == "success_empty"
    assert payload["assessment"]["complete"] is True


def test_collect_rejects_policy_for_different_capability_before_fetch() -> None:
    source = StubSource(
        "direct-sina",
        "sina",
        _result("direct-sina", "sina", SourceStatus.SUCCESS_EMPTY),
    )
    mismatched = EvidencePolicy(
        capability=EvidenceCapability.KLINE,
        min_independent_upstreams=1,
    )

    with pytest.raises(ValueError, match="capability"):
        _service(source).collect(_request(), mismatched)

    assert source.calls == 0


def test_collect_without_registered_sources_returns_incomplete_envelope() -> None:
    envelope = _service().collect(_request(), _policy(1))

    assert envelope.complete is False
    assert envelope.source_results == []
    assert envelope.items == []
    assert envelope.assessment.missing_independent_upstreams == 1

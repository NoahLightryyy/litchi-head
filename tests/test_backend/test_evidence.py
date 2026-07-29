"""统一新闻证据聚合 API 契约测试。"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    SourceResult,
    SourceStatus,
)
from src.data.models import NewsItem, StockQuote


def _envelope() -> EvidenceEnvelope:
    request = EvidenceRequest(
        capability=EvidenceCapability.NEWS,
        stock_code="000001",
        stock_name="平安银行",
        start_at=datetime(2026, 7, 28, tzinfo=UTC),
        end_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    policy = EvidencePolicy(
        capability=EvidenceCapability.NEWS,
        min_independent_upstreams=2,
    )
    item = NewsItem(
        code="000001",
        title="平安银行发布半年度业绩快报",
        date="2026-07-29",
        source="东方财富",
        source_id="eastmoney-stock-search",
        publisher="证券时报",
        url="https://example.test/news/1",
        content_hash="a" * 64,
        association_reason="stock_name",
    )
    results = [
        SourceResult[NewsItem](
            source_id="eastmoney-stock-search",
            upstream_id="eastmoney",
            capability=EvidenceCapability.NEWS,
            status=SourceStatus.SUCCESS_DATA,
            items=[item],
        ),
        SourceResult[NewsItem](
            source_id="sina-finance-feed",
            upstream_id="sina",
            capability=EvidenceCapability.NEWS,
            status=SourceStatus.FAILED,
            error_code="upstream_request_failed",
            error_message="timeout",
        ),
    ]
    assessment = EvidenceAssessment(
        capability=EvidenceCapability.NEWS,
        complete=False,
        successful_upstream_ids={"eastmoney"},
        successful_source_ids={"eastmoney-stock-search"},
        failed_source_ids={"sina-finance-feed"},
        unusable_source_ids={"sina-finance-feed"},
        missing_independent_upstreams=1,
    )
    return EvidenceEnvelope(
        request=request,
        policy=policy,
        source_results=results,
        items=[item],
        assessment=assessment,
        complete=False,
    )


def _quote_envelope() -> EvidenceEnvelope:
    request = EvidenceRequest(
        capability=EvidenceCapability.REALTIME_QUOTE,
        stock_code="000001",
    )
    policy = EvidencePolicy(
        capability=EvidenceCapability.REALTIME_QUOTE,
        min_independent_upstreams=2,
        required_upstream_ids={"eastmoney", "sina"},
    )
    quote = StockQuote(
        code="000001",
        name="平安银行",
        price=11.28,
        change=0.01,
        change_pct=0.09,
        volume=100_458_200,
        fetched_at=datetime(2026, 7, 29, 2, 30, tzinfo=UTC),
    )
    results = [
        SourceResult[StockQuote](
            source_id="direct-eastmoney-quote",
            upstream_id="eastmoney",
            capability=EvidenceCapability.REALTIME_QUOTE,
            status=SourceStatus.SUCCESS_DATA,
            items=[quote],
        ),
        SourceResult[StockQuote](
            source_id="direct-sina-quote",
            upstream_id="sina",
            capability=EvidenceCapability.REALTIME_QUOTE,
            status=SourceStatus.SUCCESS_DATA,
            items=[quote],
        ),
    ]
    assessment = EvidenceAssessment(
        capability=EvidenceCapability.REALTIME_QUOTE,
        complete=True,
        successful_upstream_ids={"eastmoney", "sina"},
        successful_source_ids={
            "direct-eastmoney-quote",
            "direct-sina-quote",
        },
        missing_independent_upstreams=0,
    )
    return EvidenceEnvelope(
        request=request,
        policy=policy,
        source_results=results,
        items=[quote],
        assessment=assessment,
        complete=True,
    )


def test_quote_aggregate_returns_reconciled_envelope(client) -> None:
    service = Mock()
    service.collect.return_value = _quote_envelope()

    with patch("backend.routers.evidence.quote_evidence_service", service):
        response = client.post(
            "/api/v1/evidence/quotes/aggregate",
            json={"symbol": "000001"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["complete"] is True
    assert payload["items"][0]["price"] == 11.28
    assert payload["assessment"]["successful_upstream_ids"] == [
        "eastmoney",
        "sina",
    ]
    request, policy = service.collect.call_args.args
    assert request.capability is EvidenceCapability.REALTIME_QUOTE
    assert request.stock_code == "000001"
    assert policy.required_upstream_ids == {"eastmoney", "sina"}


def test_quote_aggregate_rejects_invalid_symbol(client) -> None:
    response = client.post(
        "/api/v1/evidence/quotes/aggregate",
        json={"symbol": "INVALID"},
    )

    assert response.status_code == 422


def test_news_aggregate_returns_partial_success_envelope(client) -> None:
    service = Mock()
    service.collect.return_value = _envelope()

    with (
        patch("backend.routers.evidence.news_evidence_service", service),
        patch(
            "backend.routers.evidence.resolve_stock_name",
            return_value="平安银行",
        ),
    ):
        response = client.post(
            "/api/v1/evidence/news/aggregate",
            json={
                "symbol": "000001",
                "start_time": "2026-07-28T00:00:00+08:00",
                "end_time": "2026-07-29T23:59:59+08:00",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["complete"] is False
    assert payload["assessment"]["missing_independent_upstreams"] == 1
    assert [result["status"] for result in payload["source_results"]] == [
        "success_data",
        "failed",
    ]
    assert payload["items"][0]["content"] == ""
    request, policy = service.collect.call_args.args
    assert request.stock_code == "000001"
    assert request.stock_name == "平安银行"
    assert policy.min_independent_upstreams == 2


def test_news_aggregate_rejects_invalid_symbol(client) -> None:
    response = client.post(
        "/api/v1/evidence/news/aggregate",
        json={
            "symbol": "INVALID",
            "start_time": "2026-07-28T00:00:00+08:00",
            "end_time": "2026-07-29T23:59:59+08:00",
        },
    )

    assert response.status_code == 422


def test_news_aggregate_rejects_reversed_time_range(client) -> None:
    response = client.post(
        "/api/v1/evidence/news/aggregate",
        json={
            "symbol": "000001",
            "start_time": "2026-07-30T00:00:00+08:00",
            "end_time": "2026-07-29T23:59:59+08:00",
        },
    )

    assert response.status_code == 422


def test_news_aggregate_requires_explicit_timezone(client) -> None:
    response = client.post(
        "/api/v1/evidence/news/aggregate",
        json={
            "symbol": "000001",
            "start_time": "2026-07-28T00:00:00",
            "end_time": "2026-07-29T23:59:59",
        },
    )

    assert response.status_code == 422

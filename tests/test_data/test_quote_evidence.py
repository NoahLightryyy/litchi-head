"""Realtime quote source adapters and fail-closed reconciliation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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
from src.data.models import StockQuote
from src.data.providers.quotes import EastmoneyQuoteSource, SinaQuoteSource
from src.data.quote_runtime import RealtimeQuoteEvidenceService

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 29, 10, 30, tzinfo=SHANGHAI)
REQUEST = EvidenceRequest(
    capability=EvidenceCapability.REALTIME_QUOTE,
    stock_code="000001",
)
POLICY = EvidencePolicy(
    capability=EvidenceCapability.REALTIME_QUOTE,
    min_independent_upstreams=2,
    required_upstream_ids={"eastmoney", "sina"},
)


def _quote(*, price: float = 11.28, quote_at: datetime = NOW) -> StockQuote:
    return StockQuote(
        code="000001",
        name="平安银行",
        price=price,
        change=0.01,
        change_pct=0.09,
        volume=100_458_200,
        amount=1_132_000_000,
        high=11.32,
        low=11.20,
        open_=11.25,
        prev_close=11.27,
        fetched_at=quote_at,
    )


class StubQuoteSource:
    def __init__(
        self,
        source_id: str,
        upstream_id: str,
        result: SourceResult[StockQuote],
    ) -> None:
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.REALTIME_QUOTE},
        )
        self._result = result

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        return self._result


def _result(
    source_id: str,
    upstream_id: str,
    *,
    quote: StockQuote | None = None,
    status: SourceStatus = SourceStatus.SUCCESS_DATA,
    error_message: str | None = None,
) -> SourceResult[StockQuote]:
    return SourceResult(
        source_id=source_id,
        upstream_id=upstream_id,
        capability=EvidenceCapability.REALTIME_QUOTE,
        status=status,
        items=[quote or _quote()] if status is SourceStatus.SUCCESS_DATA else [],
        error_message=error_message,
    )


def _service(
    eastmoney: SourceResult[StockQuote],
    sina: SourceResult[StockQuote],
    *,
    now: datetime = NOW,
) -> RealtimeQuoteEvidenceService:
    registry = EvidenceSourceRegistry()
    registry.register(StubQuoteSource("direct-eastmoney-quote", "eastmoney", eastmoney))
    registry.register(StubQuoteSource("direct-sina-quote", "sina", sina))
    return RealtimeQuoteEvidenceService(
        registry,
        now_provider=lambda: now,
    )


def test_eastmoney_source_normalizes_lots_to_shares_and_exchange_time() -> None:
    source = EastmoneyQuoteSource(
        fetcher=lambda code: {
            "data": {
                "f57": code,
                "f58": "平安银行",
                "f43": 1128,
                "f44": 1132,
                "f45": 1120,
                "f46": 1125,
                "f47": 1_004_582,
                "f48": 1_132_000_000,
                "f60": 1127,
                "f86": int(NOW.timestamp()),
                "f169": 1,
                "f170": 9,
            }
        }
    )

    result = source.fetch(REQUEST)

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 11.28
    assert result.items[0].volume == 100_458_200
    assert result.items[0].fetched_at == NOW


def test_sina_source_parses_shares_and_exchange_time() -> None:
    fields = [
        "平安银行",
        "11.25",
        "11.27",
        "11.28",
        "11.32",
        "11.20",
        "11.27",
        "11.28",
        "100458174",
        "1132000000",
        *("" for _ in range(20)),
        "2026-07-29",
        "10:30:00",
        "00",
    ]
    source = SinaQuoteSource(fetcher=lambda code: ",".join(fields))

    result = source.fetch(REQUEST)

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].price == 11.28
    assert result.items[0].volume == 100_458_174
    assert result.items[0].fetched_at == NOW


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        (
            EastmoneyQuoteSource(fetcher=lambda code: {"data": {"f57": code}}),
            "invalid_upstream_payload",
        ),
        (
            SinaQuoteSource(fetcher=lambda code: "broken"),
            "invalid_upstream_payload",
        ),
    ],
)
def test_malformed_quote_payload_is_failed_not_empty(
    source: EastmoneyQuoteSource | SinaQuoteSource,
    expected_code: str,
) -> None:
    result = source.fetch(REQUEST)

    assert result.status is SourceStatus.FAILED
    assert result.error_code == expected_code
    assert result.error_message


def test_two_fresh_aligned_sources_produce_one_canonical_quote() -> None:
    envelope = _service(
        _result("direct-eastmoney-quote", "eastmoney"),
        _result("direct-sina-quote", "sina"),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is True
    assert len(envelope.items) == 1
    assert envelope.items[0].code == "000001"
    assert envelope.assessment.successful_upstream_ids == {"eastmoney", "sina"}


@pytest.mark.parametrize(
    ("age_seconds", "expected_code"),
    [(11, "quote_suspect"), (31, "quote_stale")],
)
def test_quote_older_than_live_limit_fails_closed(
    age_seconds: int,
    expected_code: str,
) -> None:
    envelope = _service(
        _result(
            "direct-eastmoney-quote",
            "eastmoney",
            quote=_quote(quote_at=NOW - timedelta(seconds=age_seconds)),
        ),
        _result("direct-sina-quote", "sina"),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    eastmoney = envelope.source_results[0]
    assert eastmoney.status is SourceStatus.STALE
    assert eastmoney.error_code == expected_code


def test_source_timestamp_skew_over_three_seconds_is_conflicted() -> None:
    envelope = _service(
        _result("direct-eastmoney-quote", "eastmoney"),
        _result(
            "direct-sina-quote",
            "sina",
            quote=_quote(quote_at=NOW - timedelta(seconds=4)),
        ),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.status for result in envelope.source_results
    } == {SourceStatus.CONFLICTED}
    assert {
        result.error_code for result in envelope.source_results
    } == {"quote_timestamp_conflict"}


def test_price_difference_over_one_tick_is_conflicted() -> None:
    envelope = _service(
        _result("direct-eastmoney-quote", "eastmoney", quote=_quote(price=11.28)),
        _result("direct-sina-quote", "sina", quote=_quote(price=11.30)),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.status for result in envelope.source_results
    } == {SourceStatus.CONFLICTED}
    assert {
        result.error_code for result in envelope.source_results
    } == {"quote_price_conflict"}


def test_missing_source_timestamp_fails_closed() -> None:
    envelope = _service(
        _result(
            "direct-eastmoney-quote",
            "eastmoney",
            quote=_quote().model_copy(update={"fetched_at": None}),
        ),
        _result("direct-sina-quote", "sina"),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.source_results[0].status is SourceStatus.STALE
    assert envelope.source_results[0].error_code == "quote_timestamp_missing"


def test_outside_continuous_auction_is_display_only_and_blocks_debate_evidence() -> None:
    after_close = datetime(2026, 7, 29, 15, 30, tzinfo=SHANGHAI)
    envelope = _service(
        _result(
            "direct-eastmoney-quote",
            "eastmoney",
            quote=_quote(quote_at=after_close.replace(hour=15, minute=0)),
        ),
        _result(
            "direct-sina-quote",
            "sina",
            quote=_quote(quote_at=after_close.replace(hour=15, minute=0)),
        ),
        now=after_close,
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.error_code for result in envelope.source_results
    } == {"market_not_in_continuous_auction"}


def test_one_failed_upstream_keeps_explicit_failure_and_is_incomplete() -> None:
    envelope = _service(
        _result("direct-eastmoney-quote", "eastmoney"),
        _result(
            "direct-sina-quote",
            "sina",
            status=SourceStatus.FAILED,
            error_message="timeout",
        ),
    ).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert envelope.assessment.failed_source_ids == {"direct-sina-quote"}

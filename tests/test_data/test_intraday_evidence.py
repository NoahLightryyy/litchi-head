"""东方财富 + 腾讯一分钟行情的双源对账契约。"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.data.evidence import (
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSourceRegistry,
    SourceDescriptor,
    SourceResult,
    SourceStatus,
)
from src.data.intraday import IntradayBarState, IntradaySourceSeries
from src.data.intraday_runtime import IntradayEvidenceService
from src.data.providers.intraday import EastmoneyIntradaySource, TencentIntradaySource

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 29, 9, 30, 30, tzinfo=SHANGHAI)
REQUEST = EvidenceRequest(
    capability=EvidenceCapability.INTRADAY,
    stock_code="000001",
)
POLICY = EvidencePolicy(
    capability=EvidenceCapability.INTRADAY,
    min_independent_upstreams=2,
    required_upstream_ids={"eastmoney", "tencent"},
)


def _eastmoney_payload() -> dict[str, Any]:
    return {
        "data": {
            "code": "000001",
            "name": "平安银行",
            "trends": [
                "2026-07-29 09:30,11.19,11.19,11.19,11.19,4507,5043333.00,11.190",
                "2026-07-29 09:31,11.20,11.24,11.29,11.18,89493,100641918.00,11.243",
            ],
        }
    }


def _tencent_payload(
    *,
    first_close: str = "11.19",
    first_volume: str = "4507",
    include_latest: bool = True,
) -> dict[str, Any]:
    rows = [f"0930 {first_close} {first_volume} 5043333.00"]
    if include_latest:
        rows.append("0931 11.24 94000 105685251.00")
    return {
        "code": 0,
        "data": {
            "sz000001": {
                "data": {
                    "date": "20260729",
                    "data": rows,
                },
                "qt": {"sz000001": ["", "平安银行"]},
            }
        },
    }


def test_two_sources_normalize_incremental_and_cumulative_volume() -> None:
    eastmoney = EastmoneyIntradaySource(
        fetcher=lambda code: _eastmoney_payload(),
        now_provider=lambda: NOW,
    ).fetch(REQUEST)
    tencent = TencentIntradaySource(
        fetcher=lambda code: _tencent_payload(),
        now_provider=lambda: NOW,
    ).fetch(REQUEST)

    assert eastmoney.status is SourceStatus.SUCCESS_DATA
    assert eastmoney.items[0].bars[0].volume == 450_700
    assert eastmoney.items[0].checkpoints[-1].cumulative_volume == 9_400_000
    assert eastmoney.items[0].bars[0].state is IntradayBarState.FINAL
    assert eastmoney.items[0].bars[-1].state is IntradayBarState.PROVISIONAL
    assert tencent.status is SourceStatus.SUCCESS_DATA
    assert tencent.items[0].checkpoints[-1].cumulative_volume == 9_400_000
    assert tencent.items[0].bars == []


class StubIntradaySource:
    def __init__(self, source_id: str, upstream_id: str, series: IntradaySourceSeries):
        self.descriptor = SourceDescriptor(
            source_id=source_id,
            upstream_id=upstream_id,
            display_name=source_id,
            capabilities={EvidenceCapability.INTRADAY},
        )
        self._series = series

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        return SourceResult(
            source_id=self.descriptor.source_id,
            upstream_id=self.descriptor.upstream_id,
            capability=EvidenceCapability.INTRADAY,
            status=SourceStatus.SUCCESS_DATA,
            items=[self._series],
        )


def _series_pair(
    *,
    first_close: str = "11.19",
    first_volume: str = "4507",
    include_tencent_latest: bool = True,
    now: datetime = NOW,
) -> tuple[IntradaySourceSeries, IntradaySourceSeries]:
    eastmoney_result = EastmoneyIntradaySource(
        fetcher=lambda code: _eastmoney_payload(),
        now_provider=lambda: now,
    ).fetch(REQUEST)
    tencent_result = TencentIntradaySource(
        fetcher=lambda code: _tencent_payload(
            first_close=first_close,
            first_volume=first_volume,
            include_latest=include_tencent_latest,
        ),
        now_provider=lambda: now,
    ).fetch(REQUEST)
    return eastmoney_result.items[0], tencent_result.items[0]


def _service(
    eastmoney: IntradaySourceSeries,
    tencent: IntradaySourceSeries,
) -> IntradayEvidenceService:
    registry = EvidenceSourceRegistry()
    registry.register(
        StubIntradaySource("direct-eastmoney-intraday", "eastmoney", eastmoney)
    )
    registry.register(
        StubIntradaySource("direct-tencent-intraday", "tencent", tencent)
    )
    return IntradayEvidenceService(registry, now_provider=lambda: NOW)


def test_aligned_sources_publish_only_eastmoney_ohlc_as_canonical_bars() -> None:
    eastmoney, tencent = _series_pair()

    envelope = _service(eastmoney, tencent).collect(REQUEST, POLICY)

    assert envelope.complete is True
    assert len(envelope.items) == 2
    assert envelope.items[-1].state is IntradayBarState.PROVISIONAL
    assert envelope.assessment.successful_upstream_ids == {"eastmoney", "tencent"}


def test_finalized_close_difference_over_one_tick_fails_closed() -> None:
    eastmoney, tencent = _series_pair(first_close="11.21")

    envelope = _service(eastmoney, tencent).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.error_code for result in envelope.source_results
    } == {"intraday_price_conflict"}


def test_finalized_cumulative_volume_difference_over_transport_tolerance_fails_closed() -> None:
    eastmoney, tencent = _series_pair(first_volume="4708")

    envelope = _service(eastmoney, tencent).collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert {
        result.error_code for result in envelope.source_results
    } == {"intraday_volume_conflict"}


def test_finalized_volume_difference_at_empirical_tolerance_is_accepted() -> None:
    eastmoney, tencent = _series_pair(first_volume="4502")

    envelope = _service(eastmoney, tencent).collect(REQUEST, POLICY)

    assert envelope.complete is True


def test_source_missing_latest_finalized_minute_is_stale() -> None:
    later = datetime(2026, 7, 29, 9, 31, 30, tzinfo=SHANGHAI)
    eastmoney, tencent = _series_pair(
        include_tencent_latest=False,
        now=later,
    )
    service = _service(eastmoney, tencent)
    service._now_provider = lambda: later

    envelope = service.collect(REQUEST, POLICY)

    assert envelope.complete is False
    assert envelope.items == []
    assert envelope.source_results[0].status is SourceStatus.SUCCESS_DATA
    assert envelope.source_results[1].status is SourceStatus.STALE
    assert envelope.source_results[1].error_code == "intraday_coverage_lag"


def test_tencent_bse_accepts_rows_without_cumulative_amount() -> None:
    request = EvidenceRequest(
        capability=EvidenceCapability.INTRADAY,
        stock_code="920002",
    )
    payload = {
        "code": 0,
        "data": {
            "bj920002": {
                "data": {
                    "date": "20260729",
                    "data": ["0930 52.82 77"],
                },
                "qt": {"bj920002": ["", "万达轴承"]},
            }
        },
    }

    result = TencentIntradaySource(
        fetcher=lambda code: payload,
        now_provider=lambda: NOW,
    ).fetch(request)

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].checkpoints[0].cumulative_volume == 7_700
    assert result.items[0].checkpoints[0].cumulative_amount == 0.0

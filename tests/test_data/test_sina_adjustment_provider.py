"""KR-2B direct Sina QFQ-factor evidence contracts."""

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import cast

import pytest
from pydantic import ValidationError

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.kline import MarketCode
from src.data.kline_adjustment import (
    CumulativeQfqFactorPoint,
    QfqFactorSnapshot,
)
from src.data.providers.sina_adjustment import SinaQfqFactorSource

NOW = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
START = datetime(2026, 7, 31, 7, 59, 59, tzinfo=UTC)


def test_sina_qfq_factor_response_becomes_auditable_decimal_snapshot() -> None:
    raw = (
        b'var sz000001qfq={"total":3,"data":['
        b'{"d":"2026-06-12","f":"1.0000000000000000"},'
        b'{"d":"2025-10-15","f":"1.0329067641682000"},'
        b'{"d":"1900-01-01","f":"1.0329067641682000"}]};'
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.source_id == "direct-sina-qfq-factor"
    assert result.upstream_id == "sina"
    assert result.fetched_at == NOW
    assert len(result.items) == 1
    snapshot = result.items[0]
    assert snapshot.code == "000001"
    assert snapshot.market is MarketCode.SZSE
    assert snapshot.collected_at == NOW
    assert snapshot.adapter_version == "sina-qfq-factor-v1"
    assert snapshot.response_hash == sha256(raw).hexdigest()
    assert snapshot.response_bytes == len(raw)
    assert snapshot.factor_version == f"sha256:{sha256(raw).hexdigest()}"
    assert [point.effective_date for point in snapshot.points] == [
        date(2025, 10, 15),
        date(2026, 6, 12),
    ]
    assert [point.cumulative_divisor for point in snapshot.points] == [
        Decimal("1.0329067641682000"),
        Decimal("1.0000000000000000"),
    ]
    assert snapshot.base_divisor == Decimal("1.0329067641682000")
    assert snapshot.points[0].precision == Decimal("0.0000000000000001")


def test_sina_qfq_factor_rejects_total_count_mismatch() -> None:
    raw = (
        b'var sz000001qfq={"total":2,"data":['
        b'{"d":"2026-06-12","f":"1.0000000000000000"}]};'
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "total" in (result.error_message or "")


def test_sina_qfq_factor_accepts_current_signed_comment_wrapper() -> None:
    raw = (
        b'var sh600000qfq={"total":2,"data":['
        b'{"d":"2026-07-16","f":"1.0000000000000000"},'
        b'{"d":"1900-01-01","f":"1.0000000000000000"}]}'
        b"\n/* upstream-signature */"
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="600000",
        )
    )

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].response_hash == sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "rows",
    [
        (
            b'{"d":"2026-06-12","f":"1.0000000000000000"},'
            b'{"d":"2026-06-12","f":"1.0329067641682000"}'
        ),
        (
            b'{"d":"2025-10-15","f":"1.0329067641682000"},'
            b'{"d":"2026-06-12","f":"1.0000000000000000"}'
        ),
    ],
)
def test_sina_qfq_factor_requires_unique_strictly_descending_dates(
    rows: bytes,
) -> None:
    raw = (
        b'var sz000001qfq={"total":3,"data":['
        + rows
        + b',{"d":"1900-01-01","f":"1.0329067641682000"}]};'
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "descending" in (result.error_message or "")


@pytest.mark.parametrize(
    "rows",
    [
        b'{"d":"2026-06-12","f":"1.0000000000000000"}',
        (
            b'{"d":"1900-01-01","f":"1.0329067641682000"},'
            b'{"d":"2026-06-12","f":"1.0000000000000000"}'
        ),
    ],
)
def test_sina_qfq_factor_requires_one_trailing_base_sentinel(rows: bytes) -> None:
    total = rows.count(b'"d"')
    raw = (
        b'var sz000001qfq={"total":'
        + str(total).encode()
        + b',"data":['
        + rows
        + b"]};"
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert "sentinel" in (result.error_message or "")


@pytest.mark.parametrize(
    "raw",
    [
        (
            b'var sz000001qfq={"total":2,"data":['
            b'{"d":"2026-06-12","f":"1.1000000000000000"},'
            b'{"d":"1900-01-01","f":"1.1000000000000000"}]};'
        ),
        (
            b'var sz000001qfq={"total":3,"data":['
            b'{"d":"2026-06-12","f":"1.0000000000000000"},'
            b'{"d":"2025-10-15","f":"1.0329067641682000"},'
            b'{"d":"1900-01-01","f":"9.9999999999999999"}]};'
        ),
    ],
)
def test_sina_qfq_factor_requires_latest_and_base_anchor_consistency(
    raw: bytes,
) -> None:
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert "anchor" in (result.error_message or "")


def test_sina_qfq_factor_keeps_bse_fail_closed_before_network_access() -> None:
    requested_codes: list[str] = []

    def fetcher(code: str) -> bytes:
        requested_codes.append(code)
        return (
            b'var bj920016qfq={"total":1,"data":['
            b'{"d":"1900-01-01","f":"1.0000000000000000"}]};'
        )

    source = SinaQfqFactorSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="920016",
        )
    )

    assert result.status is SourceStatus.UNSUPPORTED
    assert result.error_code == "official_verification_unavailable"
    assert requested_codes == []


def test_sina_qfq_factor_distinguishes_transport_failure_from_bad_payload() -> None:
    def fetcher(code: str) -> bytes:
        raise RuntimeError(f"offline while requesting {code}")

    source = SinaQfqFactorSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "upstream_request_failed"
    assert "offline" in (result.error_message or "")


def test_sina_qfq_factor_represents_no_action_history_as_a_valid_snapshot() -> None:
    raw = (
        b'var sz000001qfq={"total":1,"data":['
        b'{"d":"1900-01-01","f":"1.0000000000000000"}]};'
    )
    source = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    )

    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.SUCCESS_DATA
    assert result.items[0].points == ()
    assert result.items[0].base_divisor == Decimal("1.0000000000000000")


def test_qfq_factor_snapshot_rejects_hash_identity_inconsistency() -> None:
    with pytest.raises(ValidationError, match="factor_version"):
        QfqFactorSnapshot(
            code="000001",
            market=MarketCode.SZSE,
            source_id="direct-sina-qfq-factor",
            upstream_id="sina",
            adapter_version="sina-qfq-factor-v1",
            collected_at=NOW,
            response_hash="a" * 64,
            response_bytes=100,
            factor_version=f"sha256:{'b' * 64}",
            base_divisor=Decimal("1.03"),
            base_precision=Decimal("0.01"),
            points=(
                CumulativeQfqFactorPoint(
                    effective_date=date(2025, 10, 15),
                    cumulative_divisor=Decimal("1.03"),
                    precision=Decimal("0.01"),
                ),
                    CumulativeQfqFactorPoint(
                        effective_date=date(2026, 6, 12),
                        cumulative_divisor=Decimal("1.00"),
                        precision=Decimal("0.01"),
                ),
            ),
        )



def test_qfq_factor_snapshot_rejects_point_order_inconsistency() -> None:
    with pytest.raises(ValidationError, match="ordered"):
        QfqFactorSnapshot(
            code="000001",
            market=MarketCode.SZSE,
            source_id="direct-sina-qfq-factor",
            upstream_id="sina",
            adapter_version="sina-qfq-factor-v1",
            collected_at=NOW,
            response_hash="a" * 64,
            response_bytes=100,
            factor_version=f"sha256:{'a' * 64}",
            base_divisor=Decimal("1.03"),
            base_precision=Decimal("0.01"),
            points=(
                CumulativeQfqFactorPoint(
                    effective_date=date(2026, 6, 12),
                    cumulative_divisor=Decimal("1.00"),
                    precision=Decimal("0.01"),
                ),
                CumulativeQfqFactorPoint(
                    effective_date=date(2025, 10, 15),
                    cumulative_divisor=Decimal("1.03"),
                    precision=Decimal("0.01"),
                ),
            ),
        )


def test_sina_qfq_factor_is_usable_only_as_cumulative_evidence() -> None:
    assert SinaQfqFactorSource.descriptor.discovery_only is False
    assert SinaQfqFactorSource.descriptor.capabilities == {
        EvidenceCapability.CUMULATIVE_QFQ_FACTOR
    }


@pytest.mark.parametrize("code", ["", "ABCDEF", "777777"])
def test_sina_qfq_factor_rejects_invalid_code_before_network(code: str) -> None:
    requested_codes: list[str] = []

    def fetcher(code: str) -> bytes:
        requested_codes.append(code)
        return b"not reached"

    result = SinaQfqFactorSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    ).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code=code,
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_request"
    assert requested_codes == []


def test_qfq_factor_snapshot_rejects_invalid_code_identity() -> None:
    with pytest.raises(ValidationError, match="code"):
        QfqFactorSnapshot(
            code="ABCDEF",
            market=MarketCode.SZSE,
            source_id="direct-sina-qfq-factor",
            upstream_id="sina",
            adapter_version="sina-qfq-factor-v1",
            collected_at=NOW,
            response_hash="a" * 64,
            response_bytes=100,
            factor_version=f"sha256:{'a' * 64}",
            base_divisor=Decimal("1"),
            base_precision=Decimal("0.01"),
            points=(),
        )


def test_qfq_factor_models_reject_precision_that_conflicts_with_decimals() -> None:
    with pytest.raises(ValidationError, match="precision"):
        CumulativeQfqFactorPoint(
            effective_date=date(2025, 10, 15),
            cumulative_divisor=Decimal("1.0300"),
            precision=Decimal("0.1"),
        )

    with pytest.raises(ValidationError, match="base_precision"):
        QfqFactorSnapshot(
            code="000001",
            market=MarketCode.SZSE,
            source_id="direct-sina-qfq-factor",
            upstream_id="sina",
            adapter_version="sina-qfq-factor-v1",
            collected_at=NOW,
            response_hash="a" * 64,
            response_bytes=100,
            factor_version=f"sha256:{'a' * 64}",
            base_divisor=Decimal("1.0300"),
            base_precision=Decimal("0.1"),
            points=(
                CumulativeQfqFactorPoint(
                    effective_date=date(2025, 10, 15),
                    cumulative_divisor=Decimal("1.0300"),
                    precision=Decimal("0.0001"),
                ),
                CumulativeQfqFactorPoint(
                    effective_date=date(2026, 6, 12),
                    cumulative_divisor=Decimal("1.0000"),
                    precision=Decimal("0.0001"),
                ),
            ),
        )


def test_sina_qfq_factor_rejects_decoded_text_as_raw_evidence() -> None:
    def fetcher(code: str) -> bytes:
        return cast(
            bytes,
            (
                'var sz000001qfq={"total":1,"data":['
                '{"d":"1900-01-01","f":"1.0000000000000000"}]};'
            ),
        )

    result = SinaQfqFactorSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    ).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"
    assert "bytes" in (result.error_message or "")


@pytest.mark.parametrize(
    "raw",
    [
        (
            b'var sz000001qfq={"total":1,"data":['
            b'{"d":"1900-01-01","f":1.0000000000000000}]};'
        ),
        (
            b'var sz000001qfq={"total":1,"data":['
            b'{"d":19000101,"f":"1.0000000000000000"}]};'
        ),
        (
            b'var sz000001qfq={"total":1,"total":2,"data":['
            b'{"d":"1900-01-01","f":"1.0000000000000000"}]};'
        ),
    ],
)
def test_sina_qfq_factor_rejects_schema_or_key_ambiguity(raw: bytes) -> None:
    result = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    ).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert result.error_code == "invalid_upstream_payload"


def test_sina_qfq_factor_rejects_event_before_base_sentinel() -> None:
    raw = (
        b'var sz000001qfq={"total":2,"data":['
        b'{"d":"1899-12-31","f":"1.0000000000000000"},'
        b'{"d":"1900-01-01","f":"1.0000000000000000"}]};'
    )
    result = SinaQfqFactorSource(
        fetcher=lambda code: raw,
        now_provider=lambda: NOW,
    ).fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.status is SourceStatus.FAILED
    assert "after" in (result.error_message or "")


def test_sina_qfq_factor_timestamps_evidence_after_fetch_completes() -> None:
    fetch_completed = False
    raw = (
        b'var sz000001qfq={"total":1,"data":['
        b'{"d":"1900-01-01","f":"1.0000000000000000"}]};'
    )

    def fetcher(code: str) -> bytes:
        nonlocal fetch_completed
        fetch_completed = True
        return raw

    source = SinaQfqFactorSource(
        fetcher=fetcher,
        now_provider=lambda: NOW if fetch_completed else START,
    )
    result = source.fetch(
        EvidenceRequest(
            capability=EvidenceCapability.CUMULATIVE_QFQ_FACTOR,
            stock_code="000001",
        )
    )

    assert result.fetched_at == NOW
    assert result.items[0].collected_at == NOW

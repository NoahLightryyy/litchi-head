"""KR-1B-3A immutable K-line audit persistence and replay contracts.

User journeys:
- As an investor, I can replay exactly the RAW evidence known at an earlier
  point in time without consulting today's network or state.
- As an auditor, I get an explicit failure when any persisted member or
  manifest is missing, changed, or only partially committed.
- As a data engineer, repeated writes are idempotent and newer evidence never
  overwrites an older auditable version.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    SourceStatus,
)
from src.data.kline import MarketCode, RawDailyBar
from src.data.kline_store import (
    KlineAuditStore,
    KlineAuditStoreError,
    KlineEvidenceSnapshot,
    KlineQueryChunkProof,
    KlineSourceAudit,
)

T1 = datetime(2026, 7, 30, 8, 0, tzinfo=UTC)
T2 = T1 + timedelta(hours=1)
START = date(2026, 7, 28)
END = date(2026, 7, 29)


def _bar(
    trade_date: date,
    *,
    close: str = "11.20",
    volume: int = 100_000,
) -> RawDailyBar:
    return RawDailyBar(
        code="000001",
        market=MarketCode.SZSE,
        trade_date=trade_date,
        open=Decimal("11.10"),
        high=Decimal("11.30"),
        low=Decimal("11.00"),
        close=Decimal(close),
        volume=volume,
        volume_precision=1,
    )


def _chunk(
    source: str,
    *,
    fetched_at: datetime = T1,
) -> KlineQueryChunkProof:
    response_hash = "a" * 64 if source == "sina" else "b" * 64
    return KlineQueryChunkProof(
        query_start=START,
        query_end=END,
        fetched_at=fetched_at,
        response_hash=response_hash,
        response_bytes=1024,
        row_count=2,
        complete=True,
    )


def _source(
    source_id: str,
    upstream_id: str,
    *,
    fetched_at: datetime = T1,
    bars: tuple[RawDailyBar, ...] | None = None,
) -> KlineSourceAudit:
    return KlineSourceAudit(
        source_id=source_id,
        upstream_id=upstream_id,
        adapter_version="1",
        status=SourceStatus.SUCCESS_DATA,
        fetched_at=fetched_at,
        raw_bars=bars or (_bar(START), _bar(END, close="11.28")),
        query_chunks=(_chunk(upstream_id, fetched_at=fetched_at),),
    )


def _snapshot(
    *,
    collected_at: datetime = T1,
    final_close: str = "11.28",
    complete: bool = True,
    reverse_sources: bool = False,
) -> KlineEvidenceSnapshot:
    sources = (
        _source("direct-sina-raw-daily", "sina", fetched_at=collected_at),
        _source(
            "direct-tencent-raw-daily",
            "tencent",
            fetched_at=collected_at,
        ),
    )
    if reverse_sources:
        sources = tuple(reversed(sources))
    assessment = EvidenceAssessment(
        capability=EvidenceCapability.KLINE,
        complete=complete,
        successful_upstream_ids={"sina", "tencent"} if complete else set(),
        successful_source_ids=(
            {"direct-sina-raw-daily", "direct-tencent-raw-daily"} if complete else set()
        ),
        failed_source_ids=set() if complete else {"direct-sina-raw-daily"},
        unusable_source_ids=set() if complete else {"direct-sina-raw-daily"},
        missing_required_upstream_ids=(set() if complete else {"sina", "tencent"}),
        missing_independent_upstreams=0 if complete else 2,
    )
    return KlineEvidenceSnapshot(
        schema_version=1,
        request=EvidenceRequest(
            capability=EvidenceCapability.KLINE,
            stock_code="000001",
            start_at=datetime(2026, 7, 28, tzinfo=UTC),
            end_at=datetime(2026, 7, 29, 23, 59, tzinfo=UTC),
        ),
        policy=EvidencePolicy(
            capability=EvidenceCapability.KLINE,
            min_independent_upstreams=2,
            required_upstream_ids={"sina", "tencent"},
        ),
        collected_at=collected_at,
        source_audits=sources
        if complete
        else (
            KlineSourceAudit(
                source_id="direct-sina-raw-daily",
                upstream_id="sina",
                adapter_version="1",
                status=SourceStatus.FAILED,
                fetched_at=collected_at,
                error_code="upstream_request_failed",
                error_message="network unavailable",
                query_chunks=(),
                raw_bars=(),
            ),
        ),
        canonical_bars=((_bar(START), _bar(END, close=final_close)) if complete else ()),
        assessment=assessment,
        authority_hashes=(
            "calendar:" + "c" * 64,
            "lifecycle:" + "d" * 64,
            "checkpoint:" + "e" * 64,
            "status-window:" + "f" * 64,
        ),
    )


def test_snapshot_hash_is_canonical_across_source_order() -> None:
    assert _snapshot().snapshot_id == _snapshot(reverse_sources=True).snapshot_id


def test_store_survives_restart_and_round_trips_all_audit_fields(
    tmp_path: Path,
) -> None:
    expected = _snapshot()
    first = KlineAuditStore(tmp_path / "kline-audit")

    snapshot_id = first.persist(expected)
    replayed = KlineAuditStore(tmp_path / "kline-audit").replay(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
        as_of=T1,
    )

    assert snapshot_id == expected.snapshot_id
    assert replayed == expected
    assert {audit.upstream_id for audit in replayed.source_audits} == {
        "sina",
        "tencent",
    }
    assert replayed.authority_hashes == expected.authority_hashes


def test_repeated_identical_snapshot_is_idempotent(tmp_path: Path) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    snapshot = _snapshot()

    assert store.persist(snapshot) == store.persist(snapshot)
    assert store.snapshot_ids(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
    ) == (snapshot.snapshot_id,)


def test_logically_identical_reordered_snapshot_is_idempotent(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    first = _snapshot()
    reordered = _snapshot(reverse_sources=True)

    assert store.persist(first) == store.persist(reordered)
    assert store.snapshot_ids(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
    ) == (first.snapshot_id,)


def test_snapshot_rejects_query_proof_fetched_after_source() -> None:
    snapshot = _snapshot()
    invalid_source = snapshot.source_audits[0].model_copy(
        update={"query_chunks": (_chunk("sina", fetched_at=T2),)}
    )

    with pytest.raises(ValueError, match="chunk fetched_at"):
        KlineEvidenceSnapshot.model_validate(
            {
                **snapshot.model_dump(mode="python", exclude={"snapshot_id"}),
                "source_audits": (
                    invalid_source,
                    snapshot.source_audits[1],
                ),
            }
        )


def test_snapshot_rejects_assessment_that_contradicts_sources() -> None:
    snapshot = _snapshot()
    failed = KlineSourceAudit(
        source_id="direct-sina-raw-daily",
        upstream_id="sina",
        adapter_version="1",
        status=SourceStatus.FAILED,
        fetched_at=T1,
        error_message="network unavailable",
    )

    with pytest.raises(ValueError, match="assessment"):
        KlineEvidenceSnapshot.model_validate(
            {
                **snapshot.model_dump(mode="python", exclude={"snapshot_id"}),
                "source_audits": (failed,),
            }
        )


def test_snapshot_rejects_duplicate_source_id_across_upstreams() -> None:
    snapshot = _snapshot()
    colliding = snapshot.source_audits[1].model_copy(
        update={"source_id": snapshot.source_audits[0].source_id}
    )

    with pytest.raises(ValueError, match="duplicate source"):
        KlineEvidenceSnapshot.model_validate(
            {
                **snapshot.model_dump(mode="python", exclude={"snapshot_id"}),
                "source_audits": (
                    snapshot.source_audits[0],
                    colliding,
                ),
            }
        )


def test_as_of_replay_never_leaks_a_future_snapshot(tmp_path: Path) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    first = _snapshot()
    second = _snapshot(collected_at=T2, final_close="11.29")
    store.persist(first)
    store.persist(second)

    between = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
        as_of=T1 + timedelta(minutes=30),
    )
    after = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
        as_of=T2,
    )

    assert between.snapshot_id == first.snapshot_id
    assert after.snapshot_id == second.snapshot_id
    with pytest.raises(KlineAuditStoreError, match="as_of"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T1 - timedelta(seconds=1),
        )


def test_replay_rejects_tampered_selector_that_exposes_future_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kline-audit"
    store = KlineAuditStore(root)
    future = _snapshot(collected_at=T2, final_close="11.29")
    store.persist(future)
    with sqlite3.connect(root / "manifest.sqlite3") as connection:
        connection.execute(
            """
            UPDATE kline_snapshots
            SET collected_at = ?
            WHERE snapshot_id = ?
            """,
            (T1.isoformat(), future.snapshot_id),
        )
        connection.commit()

    with pytest.raises(KlineAuditStoreError, match="selector|as_of"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T1,
        )


def test_replay_rejects_naive_as_of(tmp_path: Path) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    with pytest.raises(ValueError, match="timezone-aware"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=datetime(2026, 7, 30, 8, 0),
        )


def test_tampered_or_missing_parquet_member_fails_closed(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    snapshot = _snapshot()
    store.persist(snapshot)
    member = store.member_paths(snapshot.snapshot_id)[0]
    original = member.read_bytes()

    member.write_bytes(original + b"tampered")
    with pytest.raises(KlineAuditStoreError, match="hash"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T1,
        )

    member.unlink()
    with pytest.raises(KlineAuditStoreError, match="missing"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T1,
        )


def test_tampered_manifest_fails_closed_without_fallback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kline-audit"
    store = KlineAuditStore(root)
    old = _snapshot()
    latest = _snapshot(collected_at=T2, final_close="11.29")
    store.persist(old)
    store.persist(latest)
    with sqlite3.connect(root / "manifest.sqlite3") as connection:
        connection.execute(
            """
            UPDATE kline_snapshots
            SET manifest_json = manifest_json || ' '
            WHERE snapshot_id = ?
            """,
            (latest.snapshot_id,),
        )
        connection.commit()

    with pytest.raises(KlineAuditStoreError, match="manifest"):
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T2,
        )


def test_repeated_persist_rejects_an_already_tampered_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "kline-audit"
    store = KlineAuditStore(root)
    snapshot = _snapshot()
    store.persist(snapshot)
    with sqlite3.connect(root / "manifest.sqlite3") as connection:
        connection.execute(
            """
            UPDATE kline_snapshots
            SET manifest_json = manifest_json || ' '
            WHERE snapshot_id = ?
            """,
            (snapshot.snapshot_id,),
        )
        connection.commit()

    with pytest.raises(KlineAuditStoreError, match="manifest"):
        store.persist(snapshot)


def test_interrupted_write_never_publishes_a_partial_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    old = _snapshot()
    store.persist(old)
    latest = _snapshot(collected_at=T2, final_close="11.29")

    def fail_commit(*_: object, **__: object) -> None:
        raise OSError("simulated manifest failure")

    monkeypatch.setattr(store, "_commit_snapshot", fail_commit)
    with pytest.raises(KlineAuditStoreError, match="commit"):
        store.persist(latest)

    assert (
        store.replay(
            code="000001",
            market=MarketCode.SZSE,
            start=START,
            end=END,
            as_of=T2,
        ).snapshot_id
        == old.snapshot_id
    )


def test_incomplete_diagnostic_snapshot_is_preserved_without_canonical_bars(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    incomplete = _snapshot(complete=False)

    store.persist(incomplete)
    replayed = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=START,
        end=END,
        as_of=T1,
    )

    assert not replayed.assessment.complete
    assert replayed.canonical_bars == ()
    assert replayed.source_audits[0].status is SourceStatus.FAILED
    assert replayed.source_audits[0].error_code == "upstream_request_failed"

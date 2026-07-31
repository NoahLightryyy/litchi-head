"""KR-1B-3B per-source long-window proof and audit-runtime contracts.

User journeys:
- As an investor, I never receive a recent-only Sina tail as if it covered an
  older requested history.
- As an auditor, I can inspect every bounded Tencent query and exact response
  summary used to assemble a long window.
- As a downstream system, every complete or failed-closed collection is
  persisted before it can be replayed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.kline import MarketCode
from src.data.kline_calendar import official_a_share_calendar_2026
from src.data.kline_runtime import (
    DEFAULT_KLINE_AUDIT_ROOT,
    RawDailyKlineEvidenceRuntime,
)
from src.data.kline_store import KlineAuditStore
from src.data.providers.kline import (
    SinaRawDailyKlineSource,
    TencentRawDailyKlineSource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=SHANGHAI)
FETCHED_1 = datetime(2026, 7, 30, 1, 0, tzinfo=UTC)
FETCHED_2 = FETCHED_1 + timedelta(seconds=1)
SHORT_REQUEST = EvidenceRequest(
    capability=EvidenceCapability.KLINE,
    stock_code="000001",
    start_at=datetime(2026, 7, 28, tzinfo=SHANGHAI),
    end_at=datetime(2026, 7, 29, 23, 59, tzinfo=SHANGHAI),
)
LONG_REQUEST = EvidenceRequest(
    capability=EvidenceCapability.KLINE,
    stock_code="000001",
    start_at=datetime(2010, 1, 1, tzinfo=SHANGHAI),
    end_at=datetime(2026, 7, 29, 23, 59, tzinfo=SHANGHAI),
)


def _sina_rows(days: list[date]) -> str:
    rows = ",".join(
        (
            f'{{"day":"{day.isoformat()}","open":"11.10",'
            '"high":"11.30","low":"11.00","close":"11.20",'
            '"volume":"100000"}'
        )
        for day in days
    )
    return f"/*<script>location.href='//sina.com';</script>*/\nvar _sz000001_240_1023=([{rows}]);"


def _tencent_payload(days: list[date]) -> dict[str, Any]:
    return {
        "code": 0,
        "msg": "",
        "data": {
            "sz000001": {
                "day": [
                    [
                        day.isoformat(),
                        "11.10",
                        "11.20",
                        "11.30",
                        "11.00",
                        "1000",
                    ]
                    for day in days
                ]
            }
        },
    }


def _short_sina_payload() -> str:
    return _sina_rows([date(2026, 7, 28), date(2026, 7, 29)])


def _short_tencent_payload() -> dict[str, Any]:
    return _tencent_payload([date(2026, 7, 28), date(2026, 7, 29)])


def _truncated_sina_payload() -> str:
    first = date(2023, 1, 1)
    return _sina_rows([first + timedelta(days=offset) for offset in range(1023)])


def test_sina_recent_only_tail_is_stale_with_incomplete_query_proof() -> None:
    audit = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: _truncated_sina_payload(),
        now_provider=lambda: NOW,
    ).fetch_audited(LONG_REQUEST)

    assert audit.status is SourceStatus.STALE
    assert audit.error_code == "kline_source_window_not_covered"
    assert len(audit.raw_bars) == 1023
    assert len(audit.query_chunks) == 1
    assert audit.query_chunks[0].complete is False
    assert audit.query_chunks[0].query_start == date(2010, 1, 1)
    assert audit.query_chunks[0].query_end == date(2026, 7, 29)


def test_sina_under_cap_recent_tail_still_cannot_prove_old_start() -> None:
    first = date(2023, 1, 1)
    payload = _sina_rows([first + timedelta(days=offset) for offset in range(1000)])
    audit = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: payload,
        now_provider=lambda: NOW,
    ).fetch_audited(LONG_REQUEST)

    assert audit.status is SourceStatus.STALE
    assert audit.query_chunks[0].complete is False


def test_sina_short_window_has_stable_response_summary() -> None:
    audit = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: _short_sina_payload(),
        now_provider=lambda: NOW,
    ).fetch_audited(SHORT_REQUEST)

    assert audit.status is SourceStatus.SUCCESS_DATA
    assert audit.adapter_version
    assert audit.query_chunks[0].complete is True
    assert audit.query_chunks[0].row_count == 2
    assert audit.query_chunks[0].response_bytes > 0
    assert len(audit.query_chunks[0].response_hash) == 64


def test_sina_invalid_later_row_preserves_earlier_valid_raw() -> None:
    payload = (
        "var _sz000001_240_1023=(["
        '{"day":"2026-07-28","open":"11.10","high":"11.30",'
        '"low":"11.00","close":"11.20","volume":"100000"},'
        '{"day":"2026-07-29","open":"invalid","high":"11.30",'
        '"low":"11.00","close":"11.20","volume":"100000"}'
        "]);"
    )

    audit = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: payload,
        now_provider=lambda: NOW,
    ).fetch_audited(SHORT_REQUEST)

    assert audit.status is SourceStatus.FAILED
    assert audit.error_code == "invalid_upstream_payload"
    assert [bar.trade_date for bar in audit.raw_bars] == [date(2026, 7, 28)]
    assert len(audit.query_chunks) == 1
    assert audit.query_chunks[0].complete is False


def test_tencent_long_window_is_split_into_contiguous_bounded_queries() -> None:
    calls: list[tuple[date, date]] = []

    def fetcher(
        code: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        calls.append((start, end))
        return _tencent_payload([start])

    audit = TencentRawDailyKlineSource(
        fetcher=fetcher,
        now_provider=lambda: NOW,
    ).fetch_audited(LONG_REQUEST)

    assert audit.status is SourceStatus.SUCCESS_DATA
    assert len(calls) > 1
    assert calls[0][0] == date(2010, 1, 1)
    assert calls[-1][1] == date(2026, 7, 29)
    assert all(
        next_start == current_end + timedelta(days=1)
        for (_, current_end), (next_start, _) in zip(calls, calls[1:])
    )
    assert all((end - start).days < 1023 for start, end in calls)
    assert all(chunk.complete for chunk in audit.query_chunks)
    assert [(chunk.query_start, chunk.query_end) for chunk in audit.query_chunks] == calls


def test_tencent_wire_response_hash_and_size_use_exact_received_bytes() -> None:
    body = json.dumps(
        _short_tencent_payload(),
        ensure_ascii=False,
        indent=2,
    ).encode()

    def fetcher(code: str, start: date, end: date) -> Any:
        return body

    audit = TencentRawDailyKlineSource(
        fetcher=fetcher,
        now_provider=lambda: FETCHED_1,
    ).fetch_audited(SHORT_REQUEST)

    assert audit.status is SourceStatus.SUCCESS_DATA
    assert audit.query_chunks[0].response_bytes == len(body)
    assert audit.query_chunks[0].response_hash == hashlib.sha256(body).hexdigest()


def test_tencent_second_chunk_failure_preserves_prior_raw_and_exact_proof() -> None:
    malformed = {"code": 0, "data": {}}
    timestamps = iter((FETCHED_1, FETCHED_2))
    call_count = 0

    def fetcher(
        code: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _tencent_payload([start])
        return malformed

    audit = TencentRawDailyKlineSource(
        fetcher=fetcher,
        now_provider=lambda: next(timestamps),
    ).fetch_audited(LONG_REQUEST)
    malformed_bytes = json.dumps(
        malformed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert audit.status is SourceStatus.FAILED
    assert [bar.trade_date for bar in audit.raw_bars] == [date(2010, 1, 1)]
    assert len(audit.query_chunks) == 2
    assert audit.query_chunks[0].complete is True
    assert audit.query_chunks[0].fetched_at == FETCHED_1
    assert audit.query_chunks[1].complete is False
    assert audit.query_chunks[1].fetched_at == FETCHED_2
    assert audit.query_chunks[1].response_hash == hashlib.sha256(malformed_bytes).hexdigest()
    assert audit.fetched_at == FETCHED_2


def test_tencent_second_chunk_transport_failure_preserves_prior_raw() -> None:
    timestamps = iter((FETCHED_1, FETCHED_2))
    call_count = 0

    def fetcher(
        code: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _tencent_payload([start])
        raise TimeoutError("second chunk timeout")

    audit = TencentRawDailyKlineSource(
        fetcher=fetcher,
        now_provider=lambda: next(timestamps),
    ).fetch_audited(LONG_REQUEST)

    assert audit.status is SourceStatus.FAILED
    assert audit.error_code == "upstream_request_failed"
    assert [bar.trade_date for bar in audit.raw_bars] == [date(2010, 1, 1)]
    assert len(audit.query_chunks) == 1
    assert audit.query_chunks[0].fetched_at == FETCHED_1
    assert audit.fetched_at == FETCHED_2


def test_runtime_persists_complete_audit_for_restart_replay(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    runtime = RawDailyKlineEvidenceRuntime(
        store=store,
        sina_source=SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: _short_sina_payload(),
            now_provider=lambda: NOW,
        ),
        tencent_source=TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: _short_tencent_payload(),
            now_provider=lambda: NOW,
        ),
        calendar=official_a_share_calendar_2026(),
        now_provider=lambda: NOW,
    )

    envelope, snapshot_id = runtime.collect_and_persist(SHORT_REQUEST)
    replayed = KlineAuditStore(tmp_path / "kline-audit").replay(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 7, 28),
        end=date(2026, 7, 29),
        as_of=NOW,
    )

    assert envelope.complete is True
    assert replayed.snapshot_id == snapshot_id
    assert {audit.upstream_id for audit in replayed.source_audits} == {
        "sina",
        "tencent",
    }
    assert all(audit.query_chunks for audit in replayed.source_audits)
    assert any(authority.startswith("calendar:") for authority in replayed.authority_hashes)


def test_runtime_without_authoritative_calendar_fails_closed(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    runtime = RawDailyKlineEvidenceRuntime(
        store=store,
        sina_source=SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: _sina_rows([date(2026, 7, 29)]),
            now_provider=lambda: NOW,
        ),
        tencent_source=TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: _tencent_payload([date(2026, 7, 29)]),
            now_provider=lambda: NOW,
        ),
        calendar=None,
        now_provider=lambda: NOW,
    )

    envelope, snapshot_id = runtime.collect_and_persist(SHORT_REQUEST)
    replayed = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 7, 28),
        end=date(2026, 7, 29),
        as_of=NOW,
    )

    assert envelope.complete is False
    assert replayed.snapshot_id == snapshot_id
    assert replayed.canonical_bars == ()
    assert replayed.authority_hashes == ()
    assert {audit.error_code for audit in replayed.source_audits} == {
        "calendar_coverage_missing",
        "kline_source_window_not_covered",
    }


def test_runtime_isolates_unexpected_source_failure_and_persists_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    sina = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: _short_sina_payload(),
        now_provider=lambda: NOW,
    )
    tencent = TencentRawDailyKlineSource(
        fetcher=lambda code, start, end: _short_tencent_payload(),
        now_provider=lambda: NOW,
    )

    def crash(request: EvidenceRequest) -> Any:
        raise RuntimeError("unexpected adapter crash")

    monkeypatch.setattr(sina, "fetch_audited", crash)
    runtime = RawDailyKlineEvidenceRuntime(
        store=store,
        sina_source=sina,
        tencent_source=tencent,
        calendar=official_a_share_calendar_2026(),
        now_provider=lambda: NOW,
    )

    envelope, snapshot_id = runtime.collect_and_persist(SHORT_REQUEST)
    replayed = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 7, 28),
        end=date(2026, 7, 29),
        as_of=NOW,
    )
    failed = next(audit for audit in replayed.source_audits if audit.upstream_id == "sina")

    assert envelope.complete is False
    assert replayed.snapshot_id == snapshot_id
    assert failed.status is SourceStatus.FAILED
    assert failed.error_code == "unexpected_adapter_failure"


def test_runtime_adapter_recovery_survives_persistently_failing_clock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    sina = SinaRawDailyKlineSource(
        fetcher=lambda code, start, end: _short_sina_payload(),
        now_provider=lambda: NOW,
    )
    tencent = TencentRawDailyKlineSource(
        fetcher=lambda code, start, end: _short_tencent_payload(),
        now_provider=lambda: NOW,
    )

    def crash(request: EvidenceRequest) -> Any:
        raise RuntimeError("unexpected adapter crash")

    def failed_clock() -> datetime:
        raise RuntimeError("clock unavailable")

    monkeypatch.setattr(sina, "fetch_audited", crash)
    runtime = RawDailyKlineEvidenceRuntime(
        store=store,
        sina_source=sina,
        tencent_source=tencent,
        calendar=None,
        now_provider=failed_clock,
    )

    envelope, snapshot_id = runtime.collect_and_persist(SHORT_REQUEST)
    replayed = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2026, 7, 28),
        end=date(2026, 7, 29),
        as_of=envelope.collected_at,
    )

    assert envelope.complete is False
    assert replayed.snapshot_id == snapshot_id
    assert next(
        audit for audit in replayed.source_audits if audit.upstream_id == "sina"
    ).error_code == "unexpected_adapter_failure"


def test_default_kline_audit_root_is_absolute() -> None:
    assert DEFAULT_KLINE_AUDIT_ROOT.is_absolute()


def test_runtime_persists_truncated_sina_raw_and_diagnostics(
    tmp_path: Path,
) -> None:
    store = KlineAuditStore(tmp_path / "kline-audit")
    runtime = RawDailyKlineEvidenceRuntime(
        store=store,
        sina_source=SinaRawDailyKlineSource(
            fetcher=lambda code, start, end: _truncated_sina_payload(),
            now_provider=lambda: NOW,
        ),
        tencent_source=TencentRawDailyKlineSource(
            fetcher=lambda code, start, end: _tencent_payload([]),
            now_provider=lambda: NOW,
        ),
        calendar=None,
        now_provider=lambda: NOW,
    )

    envelope, snapshot_id = runtime.collect_and_persist(LONG_REQUEST)
    replayed = store.replay(
        code="000001",
        market=MarketCode.SZSE,
        start=date(2010, 1, 1),
        end=date(2026, 7, 29),
        as_of=NOW,
    )
    sina = next(audit for audit in replayed.source_audits if audit.upstream_id == "sina")

    assert envelope.complete is False
    assert replayed.snapshot_id == snapshot_id
    assert replayed.canonical_bars == ()
    assert sina.status is SourceStatus.STALE
    assert len(sina.raw_bars) == 1023
    assert sina.error_code == "kline_source_window_not_covered"

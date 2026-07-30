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

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.data.evidence import EvidenceCapability, EvidenceRequest, SourceStatus
from src.data.kline import MarketCode
from src.data.kline_runtime import RawDailyKlineEvidenceRuntime
from src.data.kline_store import KlineAuditStore
from src.data.providers.kline import (
    SinaRawDailyKlineSource,
    TencentRawDailyKlineSource,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=SHANGHAI)
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
        calendar=None,
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

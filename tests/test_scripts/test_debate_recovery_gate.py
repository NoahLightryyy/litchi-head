"""辩论 session 恢复门禁工具测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.debate_recovery_gate import (
    load_completed_session,
    render_markdown,
    run_sqlite_recovery_gate,
)


def _result_payload(session_id: str = "deb_gate_001") -> dict[str, object]:
    return {
        "session_id": session_id,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "question": "估值和风险是否匹配？",
        "analyses": [
            {
                "agent_name": "master.buffett",
                "skill_id": "buffett",
                "skill_name": "巴菲特",
                "rating": "中性",
                "score": 72,
                "summary": "估值需要安全边际。",
                "analysis": "品牌壁垒稳固，但需要结合现金流和估值判断。" * 30,
                "key_evidence": ["品牌壁垒", "现金流"],
                "confidence": 0.7,
                "direction": "Neutral",
            }
        ],
        "vote_summary": {
            "total_votes": 1,
            "rating_distribution": {"中性": 1},
            "average_score": 72,
            "weighted_score": 72,
            "consensus": "中性",
            "confidence": 0.7,
            "direction_distribution": {"Neutral": 1},
        },
        "total_latency_ms": 8_000,
    }


def test_load_completed_session_uses_debate_result_contract(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "result.json"
    snapshot_path.write_text(
        json.dumps(_result_payload(), ensure_ascii=False),
        encoding="utf-8",
    )

    record = load_completed_session(snapshot_path)

    assert record.session_id == "deb_gate_001"
    assert record.status == "completed"
    assert record.result is not None
    assert record.result.stock_code == "600519"


def test_load_completed_session_rejects_invalid_export(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "result.json"
    snapshot_path.write_text('{"session_id": "missing-fields"}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid debate result"):
        load_completed_session(snapshot_path)


@pytest.mark.asyncio
async def test_sqlite_gate_reopens_and_verifies_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "result.json"
    snapshot_path.write_text(
        json.dumps(_result_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    record = load_completed_session(snapshot_path)

    report = await run_sqlite_recovery_gate(tmp_path / "sessions.db", record)

    assert report.backend == "sqlite-wal-full"
    assert report.recovered is True
    assert report.hash_matches is True
    assert report.snapshot.canonical_bytes > 1_000
    assert report.database_bytes > 0
    assert report.write_ms >= 0
    assert report.reopen_read_ms >= 0


@pytest.mark.asyncio
async def test_gate_reused_database_is_idempotent(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "result.json"
    snapshot_path.write_text(
        json.dumps(_result_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    record = load_completed_session(snapshot_path)
    database_path = tmp_path / "sessions.db"

    first = await run_sqlite_recovery_gate(database_path, record)
    second = await run_sqlite_recovery_gate(database_path, record)

    assert first.snapshot.sha256 == second.snapshot.sha256
    assert second.session_count == 1


@pytest.mark.asyncio
async def test_markdown_report_states_evidence_boundary(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "result.json"
    snapshot_path.write_text(
        json.dumps(_result_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    report = await run_sqlite_recovery_gate(
        tmp_path / "sessions.db",
        load_completed_session(snapshot_path),
    )

    markdown = render_markdown(report)

    assert "sqlite-wal-full" in markdown
    assert "哈希一致" in markdown
    assert "不代表生产 QPS" in markdown


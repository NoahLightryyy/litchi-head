"""辩论 session 持久化与中断恢复门禁。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.debate.models import AgentAnalysis, DebateResult, VoteSummary
from src.debate.session_store import (
    DebateSessionRecord,
    SessionStoreError,
    SqliteDebateSessionStore,
    measure_session_snapshot,
)


def _debate_result(session_id: str = "deb_recovery_001") -> DebateResult:
    analyses = [
        AgentAnalysis(
            agent_name=f"master.{name}",
            skill_id=name,
            skill_name=display_name,
            rating="看涨",
            score=80 + index,
            summary="基本面和现金流保持稳健。",
            analysis="基于估值、盈利质量和风险边界形成的完整分析。" * 20,
            key_evidence=["ROE 稳定", "经营现金流为正", "估值处于历史中位"],
            risk_warning="宏观波动可能压低短期估值。",
            confidence=0.78,
            direction="Bullish",
        )
        for index, (name, display_name) in enumerate(
            [
                ("buffett", "巴菲特"),
                ("munger", "芒格"),
                ("graham", "格雷厄姆"),
                ("lynch", "彼得·林奇"),
                ("dalio", "达利欧"),
            ]
        )
    ]
    return DebateResult(
        session_id=session_id,
        stock_code="000001",
        stock_name="平安银行",
        question="请评估未来一个季度的风险收益比",
        analyses=analyses,
        vote_summary=VoteSummary(
            total_votes=5,
            rating_distribution={"看涨": 5},
            average_score=82.0,
            weighted_score=82.0,
            consensus="看涨",
            confidence=0.78,
            direction_distribution={"Bullish": 5},
        ),
        total_latency_ms=12_345.0,
    )


def _completed_record(session_id: str = "deb_recovery_001") -> DebateSessionRecord:
    result = _debate_result(session_id)
    return DebateSessionRecord(
        session_id=session_id,
        stock_code=result.stock_code,
        question=result.question,
        status="completed",
        progress=100,
        result=result,
    )


def test_completed_session_requires_result() -> None:
    with pytest.raises(ValidationError, match="completed"):
        DebateSessionRecord(
            session_id="deb_invalid",
            stock_code="000001",
            question="测试",
            status="completed",
            progress=100,
        )


def test_failed_session_requires_visible_error() -> None:
    with pytest.raises(ValidationError, match="failed"):
        DebateSessionRecord(
            session_id="deb_failed",
            stock_code="000001",
            question="测试",
            status="failed",
            progress=0,
        )


@pytest.mark.asyncio
async def test_sqlite_session_survives_store_recreation(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    original = _completed_record()

    first_process = SqliteDebateSessionStore(database_path)
    await first_process.save(original)

    restarted_process = SqliteDebateSessionStore(database_path)
    recovered = await restarted_process.get(original.session_id)

    assert recovered == original
    assert recovered is not None
    assert recovered.result == original.result


@pytest.mark.asyncio
async def test_terminal_session_cannot_be_reopened(tmp_path: Path) -> None:
    store = SqliteDebateSessionStore(tmp_path / "sessions.db")
    completed = _completed_record()
    await store.save(completed)

    reopened = completed.model_copy(
        update={"status": "running", "progress": 50, "result": None}
    )
    with pytest.raises(SessionStoreError, match="terminal"):
        await store.save(reopened)


@pytest.mark.asyncio
async def test_repeated_completed_write_is_idempotent(tmp_path: Path) -> None:
    store = SqliteDebateSessionStore(tmp_path / "sessions.db")
    completed = _completed_record()

    await store.save(completed)
    await store.save(completed)

    assert await store.count() == 1
    assert await store.get(completed.session_id) == completed


@pytest.mark.asyncio
async def test_corrupt_payload_is_reported_not_hidden(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SqliteDebateSessionStore(database_path)
    completed = _completed_record()
    await store.save(completed)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE debate_sessions SET payload_json = ? WHERE session_id = ?",
            ("{broken-json", completed.session_id),
        )

    with pytest.raises(SessionStoreError, match="corrupt"):
        await store.get(completed.session_id)


@pytest.mark.asyncio
async def test_store_uses_recovery_pragmas_and_unique_session_id(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    store = SqliteDebateSessionStore(database_path)
    await store.save(_completed_record())

    with sqlite3.connect(database_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
        synchronous = connection.execute("PRAGMA synchronous").fetchone()
        indexes = connection.execute("PRAGMA index_list(debate_sessions)").fetchall()

    assert journal_mode == ("wal",)
    assert synchronous == (2,)
    assert any(index[2] == 1 for index in indexes)


def test_snapshot_measurement_uses_real_debate_contract() -> None:
    record = _completed_record()

    measurement = measure_session_snapshot(record)

    assert measurement.session_id == record.session_id
    assert measurement.schema_version == 1
    assert measurement.canonical_bytes > 1_000
    assert measurement.result_bytes > 1_000
    assert len(measurement.sha256) == 64


@pytest.mark.asyncio
async def test_store_closes_every_sqlite_connection(tmp_path: Path) -> None:
    real_connect = sqlite3.connect
    opened: list[TrackingConnection] = []

    class TrackingConnection(sqlite3.Connection):
        was_closed = False

        def close(self) -> None:
            self.was_closed = True
            super().close()

    def tracking_connect(*args: object, **kwargs: object) -> TrackingConnection:
        kwargs["factory"] = TrackingConnection
        connection = real_connect(*args, **kwargs)
        assert isinstance(connection, TrackingConnection)
        opened.append(connection)
        return connection

    store = SqliteDebateSessionStore(tmp_path / "sessions.db")
    with patch(
        "src.debate.session_store.sqlite3.connect",
        side_effect=tracking_connect,
    ):
        await store.save(_completed_record())
        await store.get("deb_recovery_001")
        await store.count()

    assert opened
    assert all(connection.was_closed for connection in opened)

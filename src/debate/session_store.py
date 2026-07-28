"""Durable debate session contract and SQLite recovery prototype."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.debate.models import DebateResult

SessionStatus = Literal["queued", "running", "completed", "failed"]
_TERMINAL_STATUSES = frozenset({"completed", "failed"})
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"queued", "running", "failed"}),
    "running": frozenset({"running", "completed", "failed"}),
}


class SessionStoreError(RuntimeError):
    """Raised when durable session data cannot be written or trusted."""


class DebateSessionRecord(BaseModel):
    """Versioned durable envelope for one debate session."""

    session_id: str = Field(min_length=1)
    stock_code: str = Field(min_length=1)
    question: str = ""
    status: SessionStatus
    progress: int = Field(ge=0, le=100)
    result: DebateResult | None = None
    error: str | None = None
    schema_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> DebateSessionRecord:
        if self.status == "completed":
            if self.result is None or self.progress != 100:
                raise ValueError("completed session requires result and progress=100")
            if self.result.session_id != self.session_id:
                raise ValueError("completed result session_id must match envelope")
        if self.status == "failed" and not self.error:
            raise ValueError("failed session requires a visible error")
        return self


class SessionSnapshotMeasurement(BaseModel):
    """Deterministic size and integrity evidence for a session envelope."""

    session_id: str
    schema_version: int
    canonical_bytes: int
    result_bytes: int
    sha256: str


def _canonical_json(record: DebateSessionRecord) -> str:
    payload = record.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def measure_session_snapshot(record: DebateSessionRecord) -> SessionSnapshotMeasurement:
    """Measure the real DebateResult contract without synthetic padding."""
    canonical = _canonical_json(record).encode("utf-8")
    result_json = (
        json.dumps(
            record.result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if record.result is not None
        else b""
    )
    return SessionSnapshotMeasurement(
        session_id=record.session_id,
        schema_version=record.schema_version,
        canonical_bytes=len(canonical),
        result_bytes=len(result_json),
        sha256=hashlib.sha256(canonical).hexdigest(),
    )


class SqliteDebateSessionStore:
    """SQLite WAL prototype for durable, idempotent debate session recovery."""

    def __init__(self, database_path: str | Path):
        self._database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS debate_sessions (
                session_id TEXT PRIMARY KEY,
                stock_code TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL CHECK (progress BETWEEN 0 AND 100),
                schema_version INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_debate_sessions_status_updated
            ON debate_sessions(status, updated_at)
            """
        )
        return connection

    async def save(self, record: DebateSessionRecord) -> DebateSessionRecord:
        """Persist one session atomically; terminal records are immutable."""
        validated = DebateSessionRecord.model_validate(record.model_dump(mode="python"))
        await asyncio.to_thread(self._save_sync, validated)
        return validated

    def _save_sync(self, record: DebateSessionRecord) -> None:
        canonical = _canonical_json(record)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing = connection.execute(
                        """
                        SELECT status, progress, payload_sha256
                        FROM debate_sessions
                        WHERE session_id = ?
                        """,
                        (record.session_id,),
                    ).fetchone()
                    if existing is not None and existing[0] in _TERMINAL_STATUSES:
                        if existing[2] == digest:
                            return
                        raise SessionStoreError(
                            f"terminal session is immutable: {record.session_id}"
                        )
                    if existing is not None:
                        previous_status = str(existing[0])
                        previous_progress = int(existing[1])
                        allowed = _ALLOWED_TRANSITIONS.get(previous_status, frozenset())
                        if record.status not in allowed:
                            raise SessionStoreError(
                                "invalid session transition: "
                                f"{previous_status} -> {record.status}"
                            )
                        if record.progress < previous_progress:
                            raise SessionStoreError(
                                "session progress cannot move backwards: "
                                f"{previous_progress} -> {record.progress}"
                            )
                    connection.execute(
                        """
                        INSERT INTO debate_sessions (
                            session_id, stock_code, status, progress, schema_version,
                            payload_json, payload_sha256, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            stock_code = excluded.stock_code,
                            status = excluded.status,
                            progress = excluded.progress,
                            schema_version = excluded.schema_version,
                            payload_json = excluded.payload_json,
                            payload_sha256 = excluded.payload_sha256,
                            updated_at = excluded.updated_at
                        """,
                        (
                            record.session_id,
                            record.stock_code,
                            record.status,
                            record.progress,
                            record.schema_version,
                            canonical,
                            digest,
                            record.created_at.isoformat(),
                            record.updated_at.isoformat(),
                        ),
                    )
        except SessionStoreError:
            raise
        except sqlite3.Error as exc:
            raise SessionStoreError(
                f"failed to persist session: {record.session_id}"
            ) from exc

    async def get(self, session_id: str) -> DebateSessionRecord | None:
        """Recover and integrity-check one session."""
        return await asyncio.to_thread(self._get_sync, session_id)

    def _get_sync(self, session_id: str) -> DebateSessionRecord | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT payload_json, payload_sha256
                    FROM debate_sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise SessionStoreError(f"failed to read session: {session_id}") from exc
        if row is None:
            return None

        payload_json, expected_digest = row
        actual_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if actual_digest != expected_digest:
            raise SessionStoreError(f"corrupt session checksum: {session_id}")
        try:
            return DebateSessionRecord.model_validate_json(payload_json)
        except (ValueError, TypeError) as exc:
            raise SessionStoreError(f"corrupt session payload: {session_id}") from exc

    async def count(self) -> int:
        """Return the number of durable sessions."""
        return await asyncio.to_thread(self._count_sync)

    def _count_sync(self) -> int:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT COUNT(*) FROM debate_sessions"
                ).fetchone()
        except sqlite3.Error as exc:
            raise SessionStoreError("failed to count sessions") from exc
        return int(row[0]) if row is not None else 0


__all__ = [
    "DebateSessionRecord",
    "SessionSnapshotMeasurement",
    "SessionStatus",
    "SessionStoreError",
    "SqliteDebateSessionStore",
    "measure_session_snapshot",
]

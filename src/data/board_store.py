"""Durable latest complete board display snapshots; never a decision data source."""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

from src.data.providers.eastmoney_boards import BoardMembersSnapshot, BoardSnapshot

Snapshot = BoardSnapshot | BoardMembersSnapshot


class BoardStoreError(RuntimeError):
    """Persistence or integrity failure; callers must not treat it as empty data."""


class StoredBoardSnapshot(BaseModel):
    snapshot_id: str
    snapshot: BoardSnapshot | BoardMembersSnapshot
    last_attempt_at: datetime
    consecutive_failures: int
    last_error_code: str | None


class BoardSnapshotStore:
    """One atomically replaced success per key plus independent failure metadata."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._schema_lock = Lock()

    def _connect(self) -> sqlite3.Connection:
        # First category polls may race on a brand-new WAL database.
        with self._schema_lock:
            return self._open_connection()

    def _open_connection(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("""CREATE TABLE IF NOT EXISTS board_display_v1 (
                key TEXT PRIMARY KEY, payload TEXT, digest TEXT, fetched_at TEXT,
                last_attempt_at TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0,
                error_code TEXT)""")
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def key(snapshot: Snapshot) -> str:
        if isinstance(snapshot, BoardMembersSnapshot):
            return f"members:{snapshot.kind}:{snapshot.board_code}"
        return f"boards:{snapshot.kind}"

    @staticmethod
    def _validate(snapshot: Snapshot) -> None:
        values = snapshot.members if isinstance(snapshot, BoardMembersSnapshot) else snapshot.quotes
        if not values or len({item.code for item in values}) != len(values):
            raise BoardStoreError("empty or duplicate snapshot cannot replace success")
        if snapshot.fetched_at.utcoffset() is None or any(
            item.as_of.utcoffset() is None for item in values
        ):
            raise BoardStoreError("snapshot timestamps must have time zones")

    def record_success(self, snapshot: Snapshot) -> None:
        snapshot = type(snapshot).model_validate_json(snapshot.model_dump_json())
        self._validate(snapshot)
        # Cache flags describe a read operation, never the stored source fact.
        payload = snapshot.model_copy(update={"cached": False}).model_dump_json()
        digest = hashlib.sha256(payload.encode()).hexdigest()
        at = snapshot.fetched_at.astimezone(UTC).isoformat()
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("""INSERT INTO board_display_v1
                    (key,payload,digest,fetched_at,last_attempt_at,failures,error_code)
                    VALUES (?,?,?,?,?,0,NULL)
                    ON CONFLICT(key) DO UPDATE SET
                    payload=excluded.payload,digest=excluded.digest,fetched_at=excluded.fetched_at,
                    last_attempt_at=MAX(board_display_v1.last_attempt_at,excluded.last_attempt_at),
                    failures=CASE WHEN excluded.last_attempt_at >= board_display_v1.last_attempt_at
                        THEN 0 ELSE board_display_v1.failures END,
                    error_code=CASE
                        WHEN excluded.last_attempt_at >= board_display_v1.last_attempt_at
                        THEN NULL ELSE board_display_v1.error_code END
                    WHERE board_display_v1.fetched_at IS NULL
                    OR excluded.fetched_at > board_display_v1.fetched_at""",
                    (self.key(snapshot), payload, digest, at, at))
        except (sqlite3.Error, OSError) as exc:
            raise BoardStoreError("board snapshot persistence failed") from exc

    def record_failure(self, key: str, *, attempted_at: datetime) -> None:
        if attempted_at.utcoffset() is None:
            raise BoardStoreError("attempt time must have a time zone")
        at = attempted_at.astimezone(UTC).isoformat()
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("""INSERT INTO board_display_v1
                    (key,last_attempt_at,failures,error_code) VALUES (?,?,1,'upstream_failed')
                    ON CONFLICT(key) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,
                    failures=board_display_v1.failures+1,error_code='upstream_failed'
                    WHERE excluded.last_attempt_at > board_display_v1.last_attempt_at""", (key, at))
        except (sqlite3.Error, OSError) as exc:
            raise BoardStoreError("board failure metadata persistence failed") from exc

    def load(self, key: str) -> StoredBoardSnapshot | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute("""
                    SELECT payload,digest,last_attempt_at,failures,error_code
                    FROM board_display_v1 WHERE key=?""", (key,)).fetchone()
            if row is None or row[0] is None:
                return None
            payload, digest, at, failures, error = row
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise BoardStoreError("board snapshot checksum mismatch")
            model = BoardMembersSnapshot if key.startswith("members:") else BoardSnapshot
            snapshot = model.model_validate_json(payload)
            self._validate(snapshot)
            if self.key(snapshot) != key:
                raise BoardStoreError("board snapshot identity mismatch")
            return StoredBoardSnapshot(snapshot_id=digest, snapshot=snapshot,
                                       last_attempt_at=datetime.fromisoformat(at),
                                       consecutive_failures=failures, last_error_code=error)
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise BoardStoreError("board snapshot restore failed") from exc

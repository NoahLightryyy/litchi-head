"""SQLite-backed immutable ledger for user-reported actions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.retro.user_actions import UserActionCreate, UserActionEvent


class UserActionLedgerError(RuntimeError):
    """Persistent ledger access failed."""


class UserActionConflictError(UserActionLedgerError):
    """An idempotency key was reused with different facts."""


class UserActionLedger:
    """Append-only action events, isolated and queried by ``user_id``."""

    def __init__(self, database: str | Path = "data/user_profiles/actions.sqlite3") -> None:
        self._database = Path(database)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def append(
        self,
        *,
        user_id: str,
        action: UserActionCreate,
    ) -> tuple[UserActionEvent, bool]:
        """Append once; return the original event for an identical retry."""
        await self._ensure_schema()
        try:
            return await asyncio.to_thread(self._append_sync, user_id, action)
        except UserActionConflictError:
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise UserActionLedgerError("user action ledger write failed") from exc

    async def list_events(
        self,
        *,
        user_id: str,
        stock_code: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[UserActionEvent], int]:
        await self._ensure_schema()
        try:
            return await asyncio.to_thread(
                self._list_sync,
                user_id,
                stock_code,
                session_id,
                limit,
                offset,
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise UserActionLedgerError("user action ledger read failed") from exc

    async def get_event(self, *, user_id: str, event_id: str) -> UserActionEvent | None:
        """Return one event only when it belongs to ``user_id``."""
        await self._ensure_schema()
        try:
            return await asyncio.to_thread(self._get_sync, user_id, event_id)
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise UserActionLedgerError("user action ledger read failed") from exc

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            try:
                await asyncio.to_thread(self._initialize_sync)
            except (OSError, sqlite3.Error) as exc:
                raise UserActionLedgerError("user action ledger initialization failed") from exc
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize_sync(self) -> None:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_action_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    client_action_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(user_id, client_action_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_action_lookup
                ON user_action_events(user_id, recorded_at DESC, event_id DESC)
                """
            )

    @staticmethod
    def _fingerprint(action: UserActionCreate) -> str:
        canonical = action.model_dump(mode="json", exclude_none=False)
        for field in ("quantity", "execution_price"):
            value = getattr(action, field)
            if value is not None:
                canonical[field] = format(value.normalize(), "f")
        payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _append_sync(
        self,
        user_id: str,
        action: UserActionCreate,
    ) -> tuple[UserActionEvent, bool]:
        fingerprint = self._fingerprint(action)
        with self._connect() as connection:
            # Serialize the lookup+insert pair so concurrent retries replay the
            # first durable event instead of surfacing a transient UNIQUE error.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_fingerprint, payload_json
                FROM user_action_events
                WHERE user_id = ? AND client_action_id = ?
                """,
                (user_id, action.client_action_id),
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise UserActionConflictError(
                        "client_action_id already exists with different facts"
                    )
                return UserActionEvent.model_validate_json(existing["payload_json"]), True

            recorded_at = datetime.now(UTC)
            event = UserActionEvent(
                **action.model_dump(),
                event_id=self._event_id(user_id, action.client_action_id),
                user_id=user_id,
                recorded_at=recorded_at,
            )
            connection.execute(
                """
                INSERT INTO user_action_events (
                    event_id, user_id, client_action_id, session_id, stock_code,
                    occurred_at, recorded_at, request_fingerprint, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    user_id,
                    event.client_action_id,
                    event.session_id,
                    event.stock_code,
                    event.occurred_at.isoformat(),
                    event.recorded_at.isoformat(),
                    fingerprint,
                    event.model_dump_json(),
                ),
            )
            return event, False

    @staticmethod
    def _event_id(user_id: str, client_action_id: str) -> str:
        digest = hashlib.sha256(f"{user_id}\0{client_action_id}".encode()).hexdigest()
        return f"ua_{digest[:24]}"

    def _list_sync(
        self,
        user_id: str,
        stock_code: str | None,
        session_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[UserActionEvent], int]:
        conditions = ["user_id = ?"]
        params: list[object] = [user_id]
        if stock_code is not None:
            conditions.append("stock_code = ?")
            params.append(stock_code)
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        where = " AND ".join(conditions)
        with self._connect() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) FROM user_action_events WHERE {where}",  # noqa: S608
                params,
            ).fetchone()[0])
            rows = connection.execute(
                f"""
                SELECT payload_json FROM user_action_events
                WHERE {where}
                ORDER BY recorded_at DESC, event_id DESC
                LIMIT ? OFFSET ?
                """,  # noqa: S608
                [*params, limit, offset],
            ).fetchall()
        return [UserActionEvent.model_validate_json(row["payload_json"]) for row in rows], total

    def _get_sync(self, user_id: str, event_id: str) -> UserActionEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM user_action_events
                WHERE user_id = ? AND event_id = ?
                """,
                (user_id, event_id),
            ).fetchone()
        if row is None:
            return None
        return UserActionEvent.model_validate_json(row["payload_json"])


__all__ = [
    "UserActionConflictError",
    "UserActionLedger",
    "UserActionLedgerError",
]

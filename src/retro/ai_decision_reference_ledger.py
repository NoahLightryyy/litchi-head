"""Append-only persistence for AI-decision verification references."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from src.retro.ai_decision_reference import AiDecisionReference


class AiDecisionReferenceLedgerError(RuntimeError):
    """The reference ledger could not be read or trusted."""


class AiDecisionReferenceConflictError(AiDecisionReferenceLedgerError):
    """A deterministic reference ID was reused with different facts."""


class AiDecisionReferenceLedger:
    """Persist immutable verification facts with per-user isolation."""

    def __init__(self, database: str | Path = "data/user_profiles/actions.sqlite3") -> None:
        self._database = Path(database)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def append(self, reference: AiDecisionReference) -> tuple[AiDecisionReference, bool]:
        await self._ensure_schema()
        try:
            return await asyncio.to_thread(self._append_sync, reference)
        except AiDecisionReferenceConflictError:
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise AiDecisionReferenceLedgerError("AI decision reference write failed") from exc

    async def list_references(
        self,
        *,
        user_id: str,
        event_id: str | None = None,
    ) -> list[AiDecisionReference]:
        await self._ensure_schema()
        try:
            return await asyncio.to_thread(self._list_sync, user_id, event_id)
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise AiDecisionReferenceLedgerError("AI decision reference read failed") from exc

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            try:
                await asyncio.to_thread(self._initialize_sync)
            except (OSError, sqlite3.Error) as exc:
                raise AiDecisionReferenceLedgerError(
                    "AI decision reference ledger initialization failed"
                ) from exc
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize_sync(self) -> None:
        self._database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_decision_references (
                    reference_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    decision_id TEXT,
                    checked_at TEXT NOT NULL,
                    facts_fingerprint TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_reference_user_event
                ON ai_decision_references(user_id, event_id, checked_at DESC)
                """
            )

    @staticmethod
    def _facts_fingerprint(reference: AiDecisionReference) -> str:
        facts = reference.model_dump(mode="json", exclude={"checked_at"})
        payload = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _append_sync(
        self,
        reference: AiDecisionReference,
    ) -> tuple[AiDecisionReference, bool]:
        fingerprint = self._facts_fingerprint(reference)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT facts_fingerprint, payload_json, payload_sha256
                FROM ai_decision_references WHERE reference_id = ?
                """,
                (reference.reference_id,),
            ).fetchone()
            if existing is not None:
                if existing["facts_fingerprint"] != fingerprint:
                    raise AiDecisionReferenceConflictError(
                        "reference_id already exists with different verification facts"
                    )
                return self._decode_row(existing), True
            payload_json = reference.model_dump_json()
            payload_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO ai_decision_references (
                    reference_id, user_id, event_id, decision_id, checked_at,
                    facts_fingerprint, payload_json, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reference.reference_id,
                    reference.user_id,
                    reference.event_id,
                    reference.decision_id,
                    reference.checked_at.isoformat(),
                    fingerprint,
                    payload_json,
                    payload_sha256,
                ),
            )
            return reference, False

    def _list_sync(self, user_id: str, event_id: str | None) -> list[AiDecisionReference]:
        query = (
            "SELECT facts_fingerprint, payload_json, payload_sha256 "
            "FROM ai_decision_references WHERE user_id = ?"
        )
        params: list[object] = [user_id]
        if event_id is not None:
            query += " AND event_id = ?"
            params.append(event_id)
        query += " ORDER BY checked_at DESC, reference_id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decode_row(row) for row in rows]

    def _decode_row(self, row: sqlite3.Row) -> AiDecisionReference:
        payload_json = str(row["payload_json"])
        actual_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if actual_sha256 != row["payload_sha256"]:
            raise AiDecisionReferenceLedgerError("corrupt AI decision reference checksum")
        reference = AiDecisionReference.model_validate_json(payload_json)
        if self._facts_fingerprint(reference) != row["facts_fingerprint"]:
            raise AiDecisionReferenceLedgerError("corrupt AI decision reference facts")
        return reference


__all__ = [
    "AiDecisionReferenceConflictError",
    "AiDecisionReferenceLedger",
    "AiDecisionReferenceLedgerError",
]

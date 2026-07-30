"""Immutable SQLite-manifest + Parquet storage for K-line audit snapshots."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from pydantic import BaseModel, Field, computed_field, model_validator

from src.data.evidence import (
    EvidenceAssessment,
    EvidenceCapability,
    EvidencePolicy,
    EvidenceRequest,
    SourceStatus,
)
from src.data.kline import (
    MarketCode,
    RawDailyBar,
    market_code_for,
    raw_daily_bar_conflict,
    select_canonical_raw_daily_bar,
)

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_AUTHORITY_HASH_PATTERN = r"^[a-z][a-z0-9-]*:[0-9a-f]{64}$"
AuthorityHash = Annotated[str, Field(pattern=_AUTHORITY_HASH_PATTERN)]


class KlineAuditStoreError(RuntimeError):
    """Persisted K-line evidence is unavailable, incomplete, or corrupted."""


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python", exclude={"snapshot_id"}))
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, datetime):
        return _aware(value, "canonical datetime").isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class KlineQueryChunkProof(BaseModel):
    """One bounded upstream query and its immutable response summary."""

    query_start: date
    query_end: date
    fetched_at: datetime
    response_hash: str = Field(pattern=_SHA256_PATTERN)
    response_bytes: int = Field(ge=0)
    row_count: int = Field(ge=0)
    complete: bool

    @model_validator(mode="after")
    def validate_chunk(self) -> "KlineQueryChunkProof":
        if self.query_start > self.query_end:
            raise ValueError("query chunk start must not exceed end")
        self.fetched_at = _aware(self.fetched_at, "chunk fetched_at")
        return self


class KlineSourceAudit(BaseModel):
    """K-line-specific source result plus response and coverage provenance."""

    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    status: SourceStatus
    fetched_at: datetime
    raw_bars: tuple[RawDailyBar, ...] = ()
    query_chunks: tuple[KlineQueryChunkProof, ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_source_audit(self) -> "KlineSourceAudit":
        self.fetched_at = _aware(self.fetched_at, "source fetched_at")
        if any(chunk.fetched_at > self.fetched_at for chunk in self.query_chunks):
            raise ValueError("query chunk fetched_at must not exceed source fetched_at")
        if self.status is SourceStatus.SUCCESS_DATA:
            if not self.raw_bars:
                raise ValueError("successful K-line source requires RAW bars")
            if not self.query_chunks or any(not chunk.complete for chunk in self.query_chunks):
                raise ValueError("successful K-line source requires complete query chunks")
        elif (
            self.status in {SourceStatus.SUCCESS_EMPTY, SourceStatus.UNSUPPORTED} and self.raw_bars
        ):
            raise ValueError("empty or unsupported K-line source cannot contain RAW bars")
        if self.status is SourceStatus.FAILED and not self.error_message:
            raise ValueError("failed K-line source requires error_message")
        self.raw_bars = tuple(sorted(self.raw_bars, key=lambda bar: bar.trade_date))
        self.query_chunks = tuple(
            sorted(
                self.query_chunks,
                key=lambda chunk: (
                    chunk.query_start,
                    chunk.query_end,
                    chunk.response_hash,
                ),
            )
        )
        return self


class KlineEvidenceSnapshot(BaseModel):
    """One immutable collection result and all evidence known at collection time."""

    schema_version: int = Field(ge=1)
    request: EvidenceRequest
    policy: EvidencePolicy
    collected_at: datetime
    source_audits: tuple[KlineSourceAudit, ...]
    canonical_bars: tuple[RawDailyBar, ...] = ()
    assessment: EvidenceAssessment
    authority_hashes: tuple[AuthorityHash, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> "KlineEvidenceSnapshot":
        self.collected_at = _aware(self.collected_at, "snapshot collected_at")
        if (
            self.request.capability is not EvidenceCapability.KLINE
            or self.policy.capability is not EvidenceCapability.KLINE
            or self.assessment.capability is not EvidenceCapability.KLINE
        ):
            raise ValueError("K-line snapshot contracts must use KLINE capability")
        if self.request.start_at is None or self.request.end_at is None:
            raise ValueError("K-line snapshot requires a bounded request")
        if any(audit.fetched_at > self.collected_at for audit in self.source_audits):
            raise ValueError("source fetched_at must not exceed collected_at")
        source_ids = {audit.source_id for audit in self.source_audits}
        if len(source_ids) != len(self.source_audits):
            raise ValueError("K-line snapshot has duplicate source_id")
        start = self.request.start_at.date()
        end = self.request.end_at.date()
        for audit in self.source_audits:
            chunks = audit.query_chunks
            if any(chunk.query_start < start or chunk.query_end > end for chunk in chunks):
                raise ValueError("K-line chunk coverage exceeds the request window")
            if audit.raw_bars and (
                not chunks
                or any(
                    not any(
                        chunk.query_start <= bar.trade_date <= chunk.query_end for chunk in chunks
                    )
                    for bar in audit.raw_bars
                )
            ):
                raise ValueError("K-line RAW bar is outside chunk coverage")
            if audit.status is SourceStatus.SUCCESS_DATA and (
                not chunks
                or chunks[0].query_start != start
                or chunks[-1].query_end != end
                or any(
                    current.query_end + timedelta(days=1) != following.query_start
                    for current, following in zip(chunks, chunks[1:])
                )
            ):
                raise ValueError("successful K-line source has incomplete chunk coverage")
        expected_market = market_code_for(self.request.stock_code)
        bars = [
            *self.canonical_bars,
            *(bar for audit in self.source_audits for bar in audit.raw_bars),
        ]
        if any(
            bar.code != self.request.stock_code
            or bar.market is not expected_market
            or not start <= bar.trade_date <= end
            for bar in bars
        ):
            raise ValueError("K-line snapshot RAW identity or date is invalid")
        if self.assessment.complete:
            if not self.canonical_bars:
                raise ValueError("complete K-line snapshot requires canonical bars")
        elif self.canonical_bars:
            raise ValueError("incomplete K-line snapshot cannot expose canonical bars")
        if len(set(self.authority_hashes)) != len(self.authority_hashes):
            raise ValueError("authority hashes must not contain duplicates")
        successful = {
            audit.source_id
            for audit in self.source_audits
            if audit.status is SourceStatus.SUCCESS_DATA
        }
        successful_upstreams = {
            audit.upstream_id
            for audit in self.source_audits
            if audit.status is SourceStatus.SUCCESS_DATA
        }
        failed = {
            audit.source_id for audit in self.source_audits if audit.status is SourceStatus.FAILED
        }
        unusable = {
            audit.source_id
            for audit in self.source_audits
            if audit.status is not SourceStatus.SUCCESS_DATA
        }
        missing_required = self.policy.required_upstream_ids - successful_upstreams
        missing_independent = max(
            0,
            self.policy.min_independent_upstreams - len(successful_upstreams),
        )
        assessment = self.assessment
        if (
            assessment.successful_source_ids != successful
            or assessment.successful_upstream_ids != successful_upstreams
            or assessment.failed_source_ids != failed
            or assessment.unusable_source_ids != unusable
            or assessment.discovery_only_source_ids
            or assessment.missing_required_upstream_ids != missing_required
            or assessment.missing_independent_upstreams != missing_independent
            or assessment.complete is not (not missing_required and missing_independent == 0)
        ):
            raise ValueError("K-line assessment contradicts source audits or policy")
        if self.assessment.complete:
            successful_audits = tuple(
                audit
                for audit in self.source_audits
                if audit.status is SourceStatus.SUCCESS_DATA
            )
            canonical_dates = {bar.trade_date for bar in self.canonical_bars}
            if len(canonical_dates) != len(self.canonical_bars):
                raise ValueError("complete K-line canonical dates must not contain duplicates")
            source_series: list[dict[date, RawDailyBar]] = []
            for audit in successful_audits:
                source_dates = [bar.trade_date for bar in audit.raw_bars]
                if (
                    len(set(source_dates)) != len(source_dates)
                    or set(source_dates) != canonical_dates
                ):
                    raise ValueError(
                        "each successful K-line source must cover every canonical date once"
                    )
                source_series.append({bar.trade_date: bar for bar in audit.raw_bars})
            for trade_date in sorted(canonical_dates):
                reference = source_series[0][trade_date]
                for candidate in (series[trade_date] for series in source_series[1:]):
                    conflict = raw_daily_bar_conflict(reference, candidate)
                    if conflict is not None:
                        raise ValueError(
                            f"successful K-line source conflict: {conflict[0]}"
                        )
            canonical_by_date = {
                bar.trade_date: bar for bar in self.canonical_bars
            }
            if any(
                canonical_by_date[trade_date]
                != select_canonical_raw_daily_bar(
                    (
                        audit.source_id,
                        source_series[index][trade_date],
                    )
                    for index, audit in enumerate(successful_audits)
                )
                for trade_date in canonical_dates
            ):
                raise ValueError(
                    "complete K-line canonical bars must follow deterministic RAW selection"
                )
            if not any(
                authority.startswith("calendar:") for authority in self.authority_hashes
            ):
                raise ValueError("complete K-line snapshot requires calendar authority")
        self.source_audits = tuple(
            sorted(
                self.source_audits,
                key=lambda audit: (audit.source_id, audit.upstream_id),
            )
        )
        self.canonical_bars = tuple(sorted(self.canonical_bars, key=lambda bar: bar.trade_date))
        self.authority_hashes = tuple(sorted(self.authority_hashes))
        return self

    @computed_field
    @property
    def snapshot_id(self) -> str:
        """Logical content hash, independent of physical member paths."""
        payload = self.model_dump(mode="python", exclude={"snapshot_id"})
        payload["authority_hashes"] = sorted(payload["authority_hashes"])
        payload["canonical_bars"] = sorted(
            payload["canonical_bars"],
            key=lambda bar: (
                bar["trade_date"],
                bar["code"],
                str(bar["market"]),
            ),
        )
        for source in payload["source_audits"]:
            source["raw_bars"] = sorted(
                source["raw_bars"],
                key=lambda bar: bar["trade_date"],
            )
            source["query_chunks"] = sorted(
                source["query_chunks"],
                key=lambda chunk: (
                    chunk["query_start"],
                    chunk["query_end"],
                    chunk["response_hash"],
                ),
            )
        payload["source_audits"] = sorted(
            payload["source_audits"],
            key=lambda source: (
                source["source_id"],
                source["upstream_id"],
            ),
        )
        return _sha256(_canonical_json(payload).encode("utf-8"))


class _Member(BaseModel):
    member_key: str
    relative_path: str
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    row_count: int = Field(ge=0)


class KlineAuditStore:
    """Append-only K-line snapshot store with point-in-time replay."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._database_path = self._root / "manifest.sqlite3"
        self._members_root = self._root / "members"

    def _connect(self) -> sqlite3.Connection:
        self._root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS kline_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                market TEXT NOT NULL,
                requested_start TEXT NOT NULL,
                requested_end TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                committed_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_kline_snapshot_replay
            ON kline_snapshots (
                code, market, requested_start, requested_end, collected_at
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS kline_snapshot_members (
                snapshot_id TEXT NOT NULL,
                member_key TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                PRIMARY KEY (snapshot_id, member_key),
                FOREIGN KEY (snapshot_id)
                    REFERENCES kline_snapshots(snapshot_id)
            )
            """
        )
        return connection

    @staticmethod
    def _bars_frame(bars: tuple[RawDailyBar, ...]) -> pd.DataFrame:
        rows = [
            bar.model_dump(mode="json") for bar in sorted(bars, key=lambda item: item.trade_date)
        ]
        return pd.DataFrame(rows)

    @staticmethod
    def _publish_member(temporary: Path, target: Path) -> None:
        """Publish a member durably before its SQL manifest can be committed."""
        if os.name == "nt":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            move_file = kernel32.MoveFileExW
            move_file.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_wchar_p,
                ctypes.c_uint32,
            ]
            move_file.restype = ctypes.c_int
            if not move_file(str(temporary), str(target), 0x1 | 0x8):
                raise ctypes.WinError(ctypes.get_last_error())
            return
        os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _write_member(
        self,
        member_key: str,
        bars: tuple[RawDailyBar, ...],
    ) -> _Member:
        self._members_root.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=".writing-",
            suffix=".parquet",
            dir=self._members_root,
        )
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            self._bars_frame(bars).to_parquet(
                temporary,
                engine="pyarrow",
                index=False,
            )
            with temporary.open("rb+") as stream:
                os.fsync(stream.fileno())
                stream.seek(0)
                raw = stream.read()
            content_hash = _sha256(raw)
            target = self._members_root / f"{content_hash}.parquet"
            if target.exists():
                if _sha256(target.read_bytes()) != content_hash:
                    raise KlineAuditStoreError("existing K-line member hash is invalid")
                temporary.unlink()
            else:
                self._publish_member(temporary, target)
            return _Member(
                member_key=member_key,
                relative_path=target.relative_to(self._root).as_posix(),
                content_hash=content_hash,
                row_count=len(bars),
            )
        finally:
            if temporary.exists():
                temporary.unlink()

    def _build_manifest(
        self,
        snapshot: KlineEvidenceSnapshot,
        members: tuple[_Member, ...],
    ) -> dict[str, Any]:
        metadata = snapshot.model_dump(
            mode="json",
            exclude={"snapshot_id"},
        )
        for source in metadata["source_audits"]:
            source["raw_bars"] = []
        metadata["canonical_bars"] = []
        return {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot": metadata,
            "members": [
                member.model_dump(mode="json")
                for member in sorted(members, key=lambda item: item.member_key)
            ],
        }

    def _commit_snapshot(
        self,
        *,
        snapshot: KlineEvidenceSnapshot,
        manifest_json: str,
        manifest_hash: str,
        members: tuple[_Member, ...],
    ) -> None:
        request = snapshot.request
        if request.start_at is None or request.end_at is None:
            raise KlineAuditStoreError("bounded K-line request invariant was lost")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT manifest_json, manifest_hash
                    FROM kline_snapshots
                    WHERE snapshot_id = ?
                    """,
                    (snapshot.snapshot_id,),
                ).fetchone()
                if existing is not None:
                    existing_json = str(existing["manifest_json"])
                    existing_hash = str(existing["manifest_hash"])
                    if (
                        _sha256(existing_json.encode("utf-8")) != existing_hash
                        or existing_hash != manifest_hash
                    ):
                        raise KlineAuditStoreError("existing K-line snapshot manifest is corrupted")
                    return
                connection.execute(
                    """
                    INSERT INTO kline_snapshots (
                        snapshot_id, code, market, requested_start,
                        requested_end, collected_at, manifest_json,
                        manifest_hash, committed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        request.stock_code,
                        self._market(snapshot).value,
                        request.start_at.date().isoformat(),
                        request.end_at.date().isoformat(),
                        snapshot.collected_at.isoformat(),
                        manifest_json,
                        manifest_hash,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO kline_snapshot_members (
                        snapshot_id, member_key, relative_path,
                        content_hash, row_count
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot.snapshot_id,
                            member.member_key,
                            member.relative_path,
                            member.content_hash,
                            member.row_count,
                        )
                        for member in members
                    ],
                )

    @staticmethod
    def _market(snapshot: KlineEvidenceSnapshot) -> MarketCode:
        bars = [
            *snapshot.canonical_bars,
            *(bar for source in snapshot.source_audits for bar in source.raw_bars),
        ]
        if bars:
            return bars[0].market
        return market_code_for(snapshot.request.stock_code)

    def persist(self, snapshot: KlineEvidenceSnapshot) -> str:
        """Write immutable members first and publish the SQL manifest last."""
        try:
            snapshot = KlineEvidenceSnapshot.model_validate(
                snapshot.model_dump(
                    mode="python",
                    exclude={"snapshot_id"},
                )
            )
            members: list[_Member] = []
            for source in sorted(
                snapshot.source_audits,
                key=lambda item: (item.source_id, item.upstream_id),
            ):
                if source.raw_bars:
                    members.append(
                        self._write_member(
                            f"source:{source.source_id}",
                            source.raw_bars,
                        )
                    )
            if snapshot.canonical_bars:
                members.append(
                    self._write_member(
                        "canonical",
                        snapshot.canonical_bars,
                    )
                )
            member_tuple = tuple(members)
            manifest = self._build_manifest(snapshot, member_tuple)
            manifest_json = _canonical_json(manifest)
            manifest_hash = _sha256(manifest_json.encode("utf-8"))
            self._commit_snapshot(
                snapshot=snapshot,
                manifest_json=manifest_json,
                manifest_hash=manifest_hash,
                members=member_tuple,
            )
            return snapshot.snapshot_id
        except KlineAuditStoreError:
            raise
        except Exception as exc:
            raise KlineAuditStoreError("failed to commit K-line audit snapshot") from exc

    def _row_for_replay(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
        as_of: datetime,
    ) -> sqlite3.Row:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM kline_snapshots
                    WHERE code = ?
                      AND market = ?
                      AND requested_start = ?
                      AND requested_end = ?
                      AND collected_at <= ?
                    ORDER BY collected_at DESC, snapshot_id DESC
                    LIMIT 1
                    """,
                    (
                        code,
                        market.value,
                        start.isoformat(),
                        end.isoformat(),
                        as_of.isoformat(),
                    ),
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise KlineAuditStoreError("K-line audit manifest index is unavailable") from exc
        if row is None:
            raise KlineAuditStoreError("no K-line audit snapshot is available for as_of")
        return row

    def _read_member(self, member: _Member) -> tuple[RawDailyBar, ...]:
        path = self._root / member.relative_path
        try:
            if not path.is_file():
                raise KlineAuditStoreError("K-line audit member is missing")
            raw = path.read_bytes()
        except KlineAuditStoreError:
            raise
        except OSError as exc:
            raise KlineAuditStoreError("K-line audit member is unavailable") from exc
        if _sha256(raw) != member.content_hash:
            raise KlineAuditStoreError("K-line audit member hash mismatch")
        try:
            frame = pd.read_parquet(path, engine="pyarrow")
            records = [
                {key: None if pd.isna(value) else value for key, value in record.items()}
                for record in frame.to_dict(orient="records")
            ]
            bars = tuple(RawDailyBar.model_validate(record) for record in records)
        except Exception as exc:
            raise KlineAuditStoreError("K-line audit member cannot be decoded") from exc
        if len(bars) != member.row_count:
            raise KlineAuditStoreError("K-line audit member row count mismatch")
        return bars

    def replay(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
        as_of: datetime,
    ) -> KlineEvidenceSnapshot:
        """Replay the newest committed snapshot known no later than ``as_of``."""
        as_of_utc = _aware(as_of, "as_of")
        row = self._row_for_replay(
            code=code,
            market=market,
            start=start,
            end=end,
            as_of=as_of_utc,
        )
        manifest_json = str(row["manifest_json"])
        if _sha256(manifest_json.encode("utf-8")) != str(row["manifest_hash"]):
            raise KlineAuditStoreError("K-line audit manifest hash mismatch")
        try:
            manifest = json.loads(manifest_json)
            if not isinstance(manifest, Mapping):
                raise TypeError("manifest must be an object")
            members = tuple(_Member.model_validate(item) for item in manifest["members"])
            bars_by_key = {member.member_key: self._read_member(member) for member in members}
            metadata = manifest["snapshot"]
            if not isinstance(metadata, dict):
                raise TypeError("snapshot metadata must be an object")
            for source in metadata["source_audits"]:
                key = f"source:{source['source_id']}"
                source["raw_bars"] = list(bars_by_key.get(key, ()))
            metadata["canonical_bars"] = list(bars_by_key.get("canonical", ()))
            snapshot = KlineEvidenceSnapshot.model_validate(metadata)
        except KlineAuditStoreError:
            raise
        except Exception as exc:
            raise KlineAuditStoreError("K-line audit manifest cannot be decoded") from exc
        if (
            snapshot.snapshot_id != str(row["snapshot_id"])
            or manifest.get("snapshot_id") != snapshot.snapshot_id
        ):
            raise KlineAuditStoreError("K-line audit manifest identity mismatch")
        request = snapshot.request
        if request.start_at is None or request.end_at is None:
            raise KlineAuditStoreError("K-line audit request bounds are missing")
        selector_matches = (
            str(row["code"]) == code == request.stock_code
            and str(row["market"]) == market.value
            and self._market(snapshot) is market
            and str(row["requested_start"])
            == start.isoformat()
            == request.start_at.date().isoformat()
            and str(row["requested_end"]) == end.isoformat() == request.end_at.date().isoformat()
            and str(row["collected_at"]) == snapshot.collected_at.isoformat()
        )
        if not selector_matches or snapshot.collected_at > as_of_utc:
            raise KlineAuditStoreError("K-line audit selector or as_of integrity mismatch")
        return snapshot

    def member_paths(self, snapshot_id: str) -> tuple[Path, ...]:
        """Return committed member paths for diagnostics and integrity checks."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT relative_path
                FROM kline_snapshot_members
                WHERE snapshot_id = ?
                ORDER BY member_key
                """,
                (snapshot_id,),
            ).fetchall()
        if not rows:
            raise KlineAuditStoreError("K-line audit snapshot has no members")
        return tuple(self._root / str(row["relative_path"]) for row in rows)

    def snapshot_ids(
        self,
        *,
        code: str,
        market: MarketCode,
        start: date,
        end: date,
    ) -> tuple[str, ...]:
        """List immutable versions for one logical request window."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT snapshot_id
                FROM kline_snapshots
                WHERE code = ?
                  AND market = ?
                  AND requested_start = ?
                  AND requested_end = ?
                ORDER BY collected_at, snapshot_id
                """,
                (
                    code,
                    market.value,
                    start.isoformat(),
                    end.isoformat(),
                ),
            ).fetchall()
        return tuple(str(row["snapshot_id"]) for row in rows)


__all__ = [
    "KlineAuditStore",
    "KlineAuditStoreError",
    "KlineEvidenceSnapshot",
    "KlineQueryChunkProof",
    "KlineSourceAudit",
]

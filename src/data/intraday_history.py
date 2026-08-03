"""分时历史的影子回填、可信会话持久化与同期量能基线。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, Field, computed_field, model_validator

from src.data.intraday import (
    IntradayBarState,
    IntradayCheckpoint,
    IntradaySourceSeries,
    TimeOfDayVolumeBaseline,
)
from src.data.kline import MarketCode

SHANGHAI = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


def _regular_session_clocks() -> tuple[time, ...]:
    return tuple(
        time(hour, minute)
        for hour, start, end in (
            (9, 30, 59),
            (10, 0, 59),
            (11, 0, 30),
            (13, 0, 59),
            (14, 0, 59),
            (15, 0, 0),
        )
        for minute in range(start, end + 1)
    )


REGULAR_SESSION_CLOCKS = _regular_session_clocks()
_REGULAR_SESSION_CLOCK_SET = set(REGULAR_SESSION_CLOCKS)


class IntradayHistoryTrust(str, Enum):
    """历史会话是否已经得到独立分钟上游核验。"""

    SHADOW = "single_source_shadow"
    VERIFIED = "dual_source_verified"


class IntradayHistoryStoreError(RuntimeError):
    """分时历史无法被安全提交或回放。"""


class IntradayHistoricalSession(BaseModel):
    """一个完整常规交易时段的累计量曲线及其证据等级。"""

    code: str = Field(pattern=r"^\d{6}$")
    market: MarketCode
    trade_date: date
    checkpoints: tuple[IntradayCheckpoint, ...] = Field(min_length=1)
    trust: IntradayHistoryTrust
    source_ids: tuple[str, ...] = Field(min_length=1)
    fetched_at: datetime
    response_hashes: tuple[str, ...] = Field(min_length=1)
    price_adjustment: Literal["unadjusted", "unverified_raw"] = "unadjusted"
    volume_unit: Literal["shares"] = "shares"

    @model_validator(mode="after")
    def validate_session(self) -> "IntradayHistoricalSession":
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must include timezone")
        if self.trust is IntradayHistoryTrust.VERIFIED and len(set(self.source_ids)) < 2:
            raise ValueError("verified history requires two independent sources")
        if any(len(value) != 64 for value in self.response_hashes):
            raise ValueError("response hashes must be SHA-256 hex digests")
        ordered = sorted(self.checkpoints, key=lambda point: point.timestamp)
        clocks = {
            point.timestamp.astimezone(SHANGHAI).time().replace(tzinfo=None) for point in ordered
        }
        if clocks != _REGULAR_SESSION_CLOCK_SET or len(ordered) != len(REGULAR_SESSION_CLOCKS):
            raise ValueError("history requires the complete regular-session minute set")
        previous_volume = -1
        previous_amount = -1.0
        for point in ordered:
            local = point.timestamp.astimezone(SHANGHAI)
            if point.code != self.code or local.date() != self.trade_date:
                raise ValueError("checkpoint identity must match historical session")
            if point.state is not IntradayBarState.FINAL:
                raise ValueError("historical session checkpoints must be final")
            if (
                point.cumulative_volume < previous_volume
                or point.cumulative_amount < previous_amount
            ):
                raise ValueError("historical cumulative values must not decrease")
            previous_volume = point.cumulative_volume
            previous_amount = point.cumulative_amount
        if ordered[-1].cumulative_volume <= 0:
            raise ValueError("historical session requires positive completed volume")
        self.checkpoints = tuple(ordered)
        self.source_ids = tuple(sorted(set(self.source_ids)))
        return self

    @computed_field
    @property
    def session_id(self) -> str:
        payload = self.model_dump(mode="json", exclude={"session_id"})
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class IntradayHistoryStore:
    """内容寻址 Parquet 成员与 SQLite 不可变清单。"""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._members = self._root / "members"
        self._database = self._root / "manifest.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self._root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS intraday_sessions (
                session_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                trust TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                member_path TEXT NOT NULL,
                member_hash TEXT NOT NULL,
                row_count INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_intraday_baseline "
            "ON intraday_sessions(code, trust, trade_date)"
        )
        return connection

    def persist(self, session: IntradayHistoricalSession) -> str:
        partition = (
            self._members
            / f"market={session.market.value}"
            / f"code={session.code}"
            / f"trade_date={session.trade_date.isoformat()}"
        )
        partition.mkdir(parents=True, exist_ok=True)
        rows = [point.model_dump(mode="json") for point in session.checkpoints]
        handle, temporary_name = tempfile.mkstemp(suffix=".parquet", dir=partition)
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            pd.DataFrame(rows).to_parquet(temporary, engine="pyarrow", index=False)
            raw = temporary.read_bytes()
            member_hash = hashlib.sha256(raw).hexdigest()
            member = partition / f"{member_hash}.parquet"
            if member.exists():
                if hashlib.sha256(member.read_bytes()).hexdigest() != member_hash:
                    raise IntradayHistoryStoreError("existing intraday member hash mismatch")
                temporary.unlink()
            else:
                os.replace(temporary, member)
            metadata = session.model_dump(mode="json", exclude={"checkpoints", "session_id"})
            manifest_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
            manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT OR IGNORE INTO intraday_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session.session_id,
                        session.code,
                        session.trade_date.isoformat(),
                        session.trust.value,
                        session.fetched_at.isoformat(),
                        manifest_json,
                        manifest_hash,
                        member.relative_to(self._root).as_posix(),
                        member_hash,
                        len(session.checkpoints),
                    ),
                )
            return session.session_id
        except IntradayHistoryStoreError:
            raise
        except Exception as exc:
            raise IntradayHistoryStoreError("failed to persist intraday history") from exc
        finally:
            if temporary.exists():
                temporary.unlink()

    def session_dates(self, code: str, *, trust: IntradayHistoryTrust) -> tuple[date, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT trade_date FROM intraday_sessions "
                "WHERE code = ? AND trust = ? ORDER BY trade_date",
                (code, trust.value),
            ).fetchall()
        return tuple(date.fromisoformat(str(row["trade_date"])) for row in rows)

    def _read(self, row: sqlite3.Row) -> tuple[IntradayCheckpoint, ...]:
        manifest_json = str(row["manifest_json"])
        if hashlib.sha256(manifest_json.encode()).hexdigest() != str(row["manifest_hash"]):
            raise IntradayHistoryStoreError("intraday manifest hash mismatch")
        try:
            metadata = json.loads(manifest_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise IntradayHistoryStoreError("intraday manifest cannot be decoded") from exc
        path = self._root / str(row["member_path"])
        if not path.is_file():
            raise IntradayHistoryStoreError("intraday member is missing")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != str(row["member_hash"]):
            raise IntradayHistoryStoreError("intraday member hash mismatch")
        try:
            frame = pd.read_parquet(path, engine="pyarrow")
            records: list[dict[str, Any]] = frame.to_dict(orient="records")
            points = tuple(IntradayCheckpoint.model_validate(record) for record in records)
        except Exception as exc:
            raise IntradayHistoryStoreError("intraday member cannot be decoded") from exc
        if len(points) != int(row["row_count"]):
            raise IntradayHistoryStoreError("intraday member row count mismatch")
        try:
            session = IntradayHistoricalSession.model_validate(
                {**metadata, "checkpoints": points}
            )
        except Exception as exc:
            raise IntradayHistoryStoreError("intraday manifest cannot be decoded") from exc
        selector_matches = (
            str(row["session_id"]) == session.session_id
            and str(row["code"]) == session.code
            and str(row["trade_date"]) == session.trade_date.isoformat()
            and str(row["trust"]) == session.trust.value
            and str(row["fetched_at"]) == session.fetched_at.isoformat()
        )
        if not selector_matches:
            raise IntradayHistoryStoreError("intraday manifest selector mismatch")
        return session.checkpoints

    def baseline(self, code: str, *, as_of: datetime) -> TimeOfDayVolumeBaseline | None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must include timezone")
        local = as_of.astimezone(SHANGHAI)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM intraday_sessions WHERE code = ? AND trust = ? "
                "AND trade_date < ? ORDER BY trade_date DESC, fetched_at DESC",
                (code, IntradayHistoryTrust.VERIFIED.value, local.date().isoformat()),
            ).fetchall()
        unique: dict[str, sqlite3.Row] = {}
        for row in rows:
            unique.setdefault(str(row["trade_date"]), row)
        selected = list(unique.values())[:20]
        if not selected:
            return None
        clock = local.time().replace(second=0, microsecond=0, tzinfo=None)
        values: list[int] = []
        for row in selected:
            points = self._read(row)
            match = next(
                (
                    point
                    for point in points
                    if point.timestamp.astimezone(SHANGHAI).time().replace(tzinfo=None) == clock
                ),
                None,
            )
            if match is None:
                raise IntradayHistoryStoreError("verified session is missing baseline minute")
            values.append(match.cumulative_volume)
        return TimeOfDayVolumeBaseline(
            as_of_minute=clock.strftime("%H:%M"),
            sample_days=len(values),
            expected_cumulative_volume=float(median(values)),
        )

    def member_paths(self, code: str) -> tuple[Path, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT member_path FROM intraday_sessions "
                "WHERE code = ? ORDER BY member_path",
                (code,),
            ).fetchall()
        return tuple(self._root / str(row["member_path"]) for row in rows)


class IntradayBackfillSource(Protocol):
    def fetch(self, code: str) -> tuple[IntradayHistoricalSession, ...]: ...


class IntradayHistoryPreparation(BaseModel):
    baseline: TimeOfDayVolumeBaseline | None
    limitations: tuple[str, ...] = ()


class IntradayHistoryCoordinator:
    """把单源回填限制在影子层，并把完整双源会话写入正式层。"""

    def __init__(
        self,
        store: IntradayHistoryStore,
        *,
        backfill_source: IntradayBackfillSource | None = None,
    ) -> None:
        self._store = store
        self._backfill_source = backfill_source
        self._refreshed: set[tuple[str, date]] = set()

    def prepare(
        self,
        code: str,
        *,
        as_of: datetime,
        verified_series: tuple[tuple[str, IntradaySourceSeries], ...],
    ) -> IntradayHistoryPreparation:
        limitations: list[str] = []
        local_date = as_of.astimezone(SHANGHAI).date()
        refresh_key = (code, local_date)
        if self._backfill_source is not None and refresh_key not in self._refreshed:
            try:
                for session in self._backfill_source.fetch(code):
                    self._store.persist(session)
                self._refreshed.add(refresh_key)
            except Exception:
                logger.exception("intraday shadow backfill failed: code=%s", code)
                limitations.append("relative_volume_shadow_backfill_failed")

        if len(verified_series) >= 2:
            try:
                _, canonical = next(
                    (item for item in verified_series if item[1].ohlc_supported),
                    verified_series[0],
                )
                canonical_date = canonical.checkpoints[0].timestamp.astimezone(SHANGHAI).date()
                hashes = tuple(
                    hashlib.sha256(series.model_dump_json().encode()).hexdigest()
                    for _, series in verified_series
                )
                self._store.persist(
                    IntradayHistoricalSession(
                        code=code,
                        market=_market_for_code(code),
                        trade_date=canonical_date,
                        checkpoints=tuple(canonical.checkpoints),
                        trust=IntradayHistoryTrust.VERIFIED,
                        source_ids=tuple(item[0] for item in verified_series),
                        fetched_at=as_of,
                        response_hashes=hashes,
                    )
                )
            except ValueError:
                # 盘中曲线尚不完整是正常状态；完整日的缺口由分时证据门禁处理。
                pass
            except Exception:
                logger.exception("verified intraday persistence failed: code=%s", code)
                limitations.append("relative_volume_history_store_unavailable")

        try:
            baseline = self._store.baseline(code, as_of=as_of)
            shadow_dates = self._store.session_dates(
                code,
                trust=IntradayHistoryTrust.SHADOW,
            )
            if shadow_dates and (baseline is None or baseline.sample_days < 20):
                limitations.append("relative_volume_backfill_shadow_only")
        except Exception:
            logger.exception("intraday baseline replay failed: code=%s", code)
            baseline = None
            limitations.append("relative_volume_history_store_unavailable")
        return IntradayHistoryPreparation(
            baseline=baseline,
            limitations=tuple(dict.fromkeys(limitations)),
        )


def _market_for_code(code: str) -> MarketCode:
    from src.data.kline import market_code_for

    return market_code_for(code)


__all__ = [
    "IntradayHistoricalSession",
    "IntradayHistoryCoordinator",
    "IntradayHistoryPreparation",
    "IntradayHistoryStore",
    "IntradayHistoryStoreError",
    "IntradayHistoryTrust",
    "REGULAR_SESSION_CLOCKS",
]

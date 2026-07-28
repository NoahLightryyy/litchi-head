"""Measure and verify durable recovery for an exported DebateResult."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ValidationError

if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from src.debate.models import DebateResult  # noqa: E402
from src.debate.session_store import (  # noqa: E402
    DebateSessionRecord,
    SessionSnapshotMeasurement,
    SqliteDebateSessionStore,
    measure_session_snapshot,
)


class RecoveryGateReport(BaseModel):
    """Evidence emitted after closing and reopening the session store."""

    backend: str
    snapshot: SessionSnapshotMeasurement
    recovered: bool
    hash_matches: bool
    session_count: int
    database_bytes: int
    write_ms: float
    reopen_read_ms: float


def load_completed_session(snapshot_path: str | Path) -> DebateSessionRecord:
    """Validate an exported DebateResult and wrap it in the durable envelope."""
    path = Path(snapshot_path)
    try:
        result = DebateResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise ValueError(f"invalid debate result export: {path}") from exc
    return DebateSessionRecord(
        session_id=result.session_id,
        stock_code=result.stock_code,
        question=result.question,
        status="completed",
        progress=100,
        result=result,
    )


def _database_size(database_path: Path) -> int:
    related_paths = (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    )
    return sum(path.stat().st_size for path in related_paths if path.exists())


async def run_sqlite_recovery_gate(
    database_path: str | Path,
    record: DebateSessionRecord,
) -> RecoveryGateReport:
    """Write, release all connections, reopen, then verify the canonical hash."""
    path = Path(database_path)
    expected = measure_session_snapshot(record)

    writer = SqliteDebateSessionStore(path)
    started = time.perf_counter()
    await writer.save(record)
    write_ms = (time.perf_counter() - started) * 1000

    restarted_reader = SqliteDebateSessionStore(path)
    started = time.perf_counter()
    recovered = await restarted_reader.get(record.session_id)
    reopen_read_ms = (time.perf_counter() - started) * 1000

    recovered_measurement = (
        measure_session_snapshot(recovered) if recovered is not None else None
    )
    return RecoveryGateReport(
        backend="sqlite-wal-full",
        snapshot=expected,
        recovered=recovered is not None,
        hash_matches=(
            recovered_measurement is not None
            and recovered_measurement.sha256 == expected.sha256
        ),
        session_count=await restarted_reader.count(),
        database_bytes=_database_size(path),
        write_ms=round(write_ms, 4),
        reopen_read_ms=round(reopen_read_ms, 4),
    )


def render_markdown(report: RecoveryGateReport) -> str:
    """Render a concise evidence report with an explicit scope boundary."""
    return "\n".join(
        [
            "# Debate session recovery gate",
            "",
            f"- Backend: `{report.backend}`",
            f"- Session: `{report.snapshot.session_id}`",
            f"- Schema version: `{report.snapshot.schema_version}`",
            f"- Canonical snapshot: `{report.snapshot.canonical_bytes}` bytes",
            f"- Result payload: `{report.snapshot.result_bytes}` bytes",
            f"- Database files: `{report.database_bytes}` bytes",
            f"- Write: `{report.write_ms:.4f}` ms",
            f"- Reopen read: `{report.reopen_read_ms:.4f}` ms",
            f"- Recovered: `{'是' if report.recovered else '否'}`",
            f"- 哈希一致: `{'是' if report.hash_matches else '否'}`",
            "",
            "> 这是单份导出结果的恢复证据，不代表生产 QPS 或并发承诺。",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and recover an exported DebateResult through SQLite WAL."
    )
    parser.add_argument("snapshot", type=Path, help="DebateResult JSON export")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/benchmarks/debate-recovery.db"),
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    record = load_completed_session(args.snapshot)
    report = asyncio.run(run_sqlite_recovery_gate(args.database, record))
    if args.format == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(render_markdown(report))
    return 0 if report.recovered and report.hash_matches else 1


if __name__ == "__main__":
    raise SystemExit(main())

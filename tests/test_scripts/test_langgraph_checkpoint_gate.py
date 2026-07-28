"""LangGraph SQLite checkpoint restart gate tests."""

from __future__ import annotations

from pathlib import Path

from scripts.langgraph_checkpoint_gate import run_sqlite_checkpoint_gate


def test_sqlite_checkpoint_resumes_after_reopening_database(tmp_path: Path) -> None:
    report = run_sqlite_checkpoint_gate(
        tmp_path / "checkpoints.db",
        thread_id="restart-gate-001",
    )

    assert report.interrupted_state == ["collect"]
    assert report.resumed_state == ["collect", "analyze"]
    assert report.collect_executions == 1
    assert report.analyze_executions == 1
    assert report.skipped_completed_node is True
    assert report.database_bytes > 0


def test_checkpoint_threads_are_isolated(tmp_path: Path) -> None:
    database_path = tmp_path / "checkpoints.db"

    first = run_sqlite_checkpoint_gate(database_path, thread_id="thread-a")
    second = run_sqlite_checkpoint_gate(database_path, thread_id="thread-b")

    assert first.thread_id == "thread-a"
    assert second.thread_id == "thread-b"
    assert first.resumed_state == ["collect", "analyze"]
    assert second.resumed_state == ["collect", "analyze"]

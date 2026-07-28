"""Prove that a LangGraph run resumes from a durable SQLite checkpoint."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


class CheckpointGateState(TypedDict):
    """Minimal state used to prove exact node-level continuation."""

    completed_nodes: list[str]


class CheckpointGateReport(BaseModel):
    """Evidence from a stop, connection close, reopen, and resume cycle."""

    backend: str
    thread_id: str
    interrupted_state: list[str]
    resumed_state: list[str]
    collect_executions: int
    analyze_executions: int
    skipped_completed_node: bool
    database_bytes: int


def _build_graph(
    checkpointer: SqliteSaver,
    executions: dict[str, int],
    *,
    interrupt_after_collect: bool,
) -> CompiledStateGraph:
    def collect(state: CheckpointGateState) -> CheckpointGateState:
        executions["collect"] += 1
        return {"completed_nodes": [*state["completed_nodes"], "collect"]}

    def analyze(state: CheckpointGateState) -> CheckpointGateState:
        executions["analyze"] += 1
        return {"completed_nodes": [*state["completed_nodes"], "analyze"]}

    builder = StateGraph(CheckpointGateState)
    builder.add_node("collect", collect)
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", "analyze")
    builder.add_edge("analyze", END)
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_after=["collect"] if interrupt_after_collect else None,
    )


def run_sqlite_checkpoint_gate(
    database_path: str | Path,
    *,
    thread_id: str,
) -> CheckpointGateReport:
    """Stop after one node, release SQLite, then continue without rerunning it."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    executions = {"collect": 0, "analyze": 0}

    first_connection = sqlite3.connect(path, check_same_thread=False)
    try:
        interrupted_graph = _build_graph(
            SqliteSaver(first_connection),
            executions,
            interrupt_after_collect=True,
        )
        interrupted = interrupted_graph.invoke(
            {"completed_nodes": []},
            config,
        )
    finally:
        first_connection.close()

    second_connection = sqlite3.connect(path, check_same_thread=False)
    try:
        resumed_graph = _build_graph(
            SqliteSaver(second_connection),
            executions,
            interrupt_after_collect=False,
        )
        resumed = resumed_graph.invoke(None, config)
    finally:
        second_connection.close()

    interrupted_nodes = list(interrupted["completed_nodes"])
    resumed_nodes = list(resumed["completed_nodes"])
    return CheckpointGateReport(
        backend="langgraph-sqlite",
        thread_id=thread_id,
        interrupted_state=interrupted_nodes,
        resumed_state=resumed_nodes,
        collect_executions=executions["collect"],
        analyze_executions=executions["analyze"],
        skipped_completed_node=(
            executions["collect"] == 1
            and executions["analyze"] == 1
            and resumed_nodes == ["collect", "analyze"]
        ),
        database_bytes=path.stat().st_size,
    )

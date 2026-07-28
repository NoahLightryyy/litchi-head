"""Run one debate and persist a raw result plus aggregate evidence report."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

if __package__ in (None, ""):
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from src.debate.models import DebateInput, DebateResult  # noqa: E402
from src.utils.cost_tracker import SessionCostSummary, cost_tracker  # noqa: E402


class DebateRunner(Protocol):
    async def run(self, debate_input: DebateInput) -> DebateResult: ...


class DebateEvidenceReport(BaseModel):
    """Aggregate, non-secret evidence derived from one real debate export."""

    evidence_kind: Literal["real_llm_export"] = "real_llm_export"
    captured_at: datetime
    session_id: str
    stock_code: str
    stock_name: str
    result_bytes: int
    total_latency_ms: float
    analyst_count: int
    master_count: int
    rebuttal_count: int
    has_independent_review: bool
    analyst_latency_ms: float
    master_latency_ms: float
    review_latency_ms: float
    llm: SessionCostSummary


class DebateEvidenceBundle(BaseModel):
    """Paths and aggregate report produced by one capture."""

    result_path: Path
    report_path: Path
    report: DebateEvidenceReport


def _result_json(result: DebateResult) -> str:
    return json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def summarize_debate_result(
    result: DebateResult,
    cost_summary: SessionCostSummary,
) -> DebateEvidenceReport:
    """Build aggregate evidence without copying prompts or API credentials."""
    analyst_reports = result.analyst_reports or {}
    rebuttals = result.review_round.rebuttals if result.review_round is not None else []
    independent_review_latency = (
        result.review_report.latency_ms if result.review_report is not None else 0.0
    )
    return DebateEvidenceReport(
        captured_at=datetime.now(timezone.utc),
        session_id=result.session_id,
        stock_code=result.stock_code,
        stock_name=result.stock_name,
        result_bytes=len(_result_json(result).encode("utf-8")),
        total_latency_ms=result.total_latency_ms,
        analyst_count=len(analyst_reports),
        master_count=len(result.analyses),
        rebuttal_count=len(rebuttals),
        has_independent_review=result.review_report is not None,
        analyst_latency_ms=round(
            sum(report.latency_ms for report in analyst_reports.values()),
            4,
        ),
        master_latency_ms=round(
            sum(analysis.latency_ms for analysis in result.analyses),
            4,
        ),
        review_latency_ms=round(
            sum(rebuttal.latency_ms for rebuttal in rebuttals)
            + independent_review_latency,
            4,
        ),
        llm=cost_summary,
    )


def _write_atomic(path: Path, content: str) -> None:
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


async def capture_debate_evidence(
    debate_input: DebateInput,
    *,
    output_dir: str | Path,
    orchestrator: DebateRunner | None = None,
    cost_summary_getter: Callable[[str], SessionCostSummary] | None = None,
) -> DebateEvidenceBundle:
    """Run, validate, and atomically export one debate and its measurements."""
    if orchestrator is None:
        from src.debate.orchestrator import DebateOrchestrator  # noqa: PLC0415

        orchestrator = DebateOrchestrator()
    if cost_summary_getter is None:
        cost_summary_getter = cost_tracker.session_summary

    result = await orchestrator.run(debate_input)
    if result.session_id != debate_input.session_id:
        raise ValueError(
            "session_id mismatch: "
            f"input={debate_input.session_id}, result={result.session_id}"
        )

    report = summarize_debate_result(
        result,
        cost_summary_getter(debate_input.session_id),
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / f"{debate_input.session_id}.result.json"
    report_path = directory / f"{debate_input.session_id}.evidence.json"

    _write_atomic(result_path, _result_json(result))
    _write_atomic(report_path, report.model_dump_json(indent=2))
    return DebateEvidenceBundle(
        result_path=result_path,
        report_path=report_path,
        report=report,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture one real debate evidence bundle.")
    parser.add_argument("--stock-code", default="000001")
    parser.add_argument("--stock-name", default="平安银行")
    parser.add_argument(
        "--question",
        default="请基于当前可验证数据，评估未来一个季度的风险收益比与主要不确定性。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/benchmarks/real-debate"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    debate_input = DebateInput(
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        question=args.question,
    )
    bundle = asyncio.run(
        capture_debate_evidence(
            debate_input,
            output_dir=args.output_dir,
        )
    )
    print(bundle.report.model_dump_json(indent=2))
    print(f"result_path={bundle.result_path}")
    print(f"report_path={bundle.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

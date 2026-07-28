"""真实辩论证据采样工具测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scripts.capture_debate_evidence import (
    DebateEvidenceBundle,
    capture_debate_evidence,
    main,
    summarize_debate_result,
)
from src.debate.models import AgentAnalysis, DebateInput, DebateResult, VoteSummary
from src.utils.cost_tracker import SessionCostSummary


def _result(session_id: str = "deb_capture_001") -> DebateResult:
    return DebateResult(
        session_id=session_id,
        stock_code="000001",
        stock_name="平安银行",
        question="测试问题",
        analyses=[
            AgentAnalysis(
                agent_name="master.buffett",
                skill_id="buffett",
                skill_name="巴菲特",
                rating="中性",
                score=70,
                summary="摘要",
                analysis="完整分析",
                confidence=0.7,
                latency_ms=120,
                direction="Neutral",
            )
        ],
        vote_summary=VoteSummary(
            total_votes=1,
            consensus="中性",
            confidence=0.7,
        ),
        analyst_reports={},
        total_latency_ms=500,
    )


def _cost(session_id: str = "deb_capture_001") -> SessionCostSummary:
    return SessionCostSummary(
        session_id=session_id,
        call_count=3,
        prompt_tokens=1_000,
        prompt_cache_hit_tokens=200,
        prompt_cache_miss_tokens=800,
        completion_tokens=300,
        cost_yuan=0.001404,
        models={"deepseek-chat"},
    )


def test_summary_uses_result_and_cost_contracts() -> None:
    report = summarize_debate_result(_result(), _cost())

    assert report.session_id == "deb_capture_001"
    assert report.result_bytes > 100
    assert report.master_count == 1
    assert report.analyst_count == 0
    assert report.llm.call_count == 3
    assert report.evidence_kind == "real_llm_export"


@pytest.mark.asyncio
async def test_capture_writes_result_and_report_atomically(tmp_path: Path) -> None:
    result = _result()

    class FakeOrchestrator:
        async def run(self, debate_input: DebateInput) -> DebateResult:
            assert debate_input.session_id == result.session_id
            return result

    bundle = await capture_debate_evidence(
        DebateInput(
            stock_code="000001",
            stock_name="平安银行",
            question="测试问题",
            session_id=result.session_id,
        ),
        output_dir=tmp_path,
        orchestrator=FakeOrchestrator(),
        cost_summary_getter=lambda _session_id: _cost(),
    )

    result_payload = json.loads(bundle.result_path.read_text(encoding="utf-8"))
    report_payload = json.loads(bundle.report_path.read_text(encoding="utf-8"))

    assert result_payload["session_id"] == result.session_id
    assert report_payload["session_id"] == result.session_id
    assert report_payload["llm"]["call_count"] == 3
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_capture_rejects_orchestrator_session_mismatch(tmp_path: Path) -> None:
    class WrongSessionOrchestrator:
        async def run(self, debate_input: DebateInput) -> DebateResult:
            return _result("different-session")

    debate_input = DebateInput(
        stock_code="000001",
        session_id="expected-session",
    )
    with pytest.raises(ValueError, match="session_id mismatch"):
        await capture_debate_evidence(
            debate_input,
            output_dir=tmp_path,
            orchestrator=WrongSessionOrchestrator(),
            cost_summary_getter=lambda session_id: _cost(session_id),
        )

    assert list(tmp_path.iterdir()) == []


def test_cli_prints_aggregate_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = summarize_debate_result(_result(), _cost())
    bundle = DebateEvidenceBundle(
        result_path=tmp_path / "result.json",
        report_path=tmp_path / "report.json",
        report=report,
    )
    with patch(
        "scripts.capture_debate_evidence.capture_debate_evidence",
        new=AsyncMock(return_value=bundle),
    ):
        exit_code = main(
            [
                "--stock-code",
                "000001",
                "--stock-name",
                "平安银行",
                "--output-dir",
                str(tmp_path),
            ]
        )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"evidence_kind":"real_llm_export"' in output.replace(" ", "")
    assert f"result_path={bundle.result_path}" in output


def test_direct_script_entrypoint_can_load_project_imports() -> None:
    project_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "capture_debate_evidence.py"),
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Capture one real debate evidence bundle" in completed.stdout

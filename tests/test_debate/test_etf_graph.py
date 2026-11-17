"""ETF graph reuse and instrument identity isolation, with no paid inference."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.debate.evidence_gate import EvidenceIncompleteError
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    DebateInput,
    DebateResult,
    EvidenceLimitation,
    IndependentReview,
    InstrumentResearchContext,
    RebuttalAnalysis,
)
from src.debate.orchestrator import DebateOrchestrator
from src.debate.session_store import (
    DebateSessionRecord,
    SessionStoreError,
    SqliteDebateSessionStore,
)


def context():
    return InstrumentResearchContext(
        stock_code="560780",
        stock_name="半导体设备ETF广发",
        brief="ETF真实价格0.749；基金主题材料。",
        evidence_limitations=[
            EvidenceLimitation(
                capability="etf_research",
                collected_at=datetime.now(UTC),
                research_note="净值和完整持仓未取得，不计算折溢价。",
            )
        ],
    )


@pytest.mark.asyncio
async def test_etf_runs_all_debate_rounds_without_stock_collection():
    collector = MagicMock()
    orch = DebateOrchestrator(
        data_collector=collector,
        quote_evidence_service=None,
        prepared_research=context(),
        skill_ids=["buffett", "munger"],
    )
    collector.reset_mock()  # Constructor only checks dependency truthiness.
    analysis = AgentAnalysis(
        agent_name="master.test",
        skill_id="test",
        skill_name="测试",
        rating="中性",
        score=50,
        summary="测试",
        analysis="ETF主题研究",
        key_evidence=["0.749"],
    )

    async def master_result(**kwargs):
        skill = kwargs["skill"]
        return analysis.model_copy(update={
            "agent_name": f"master.{skill.skill_id}", "skill_id": skill.skill_id,
        })

    with (
        patch(
            "src.debate.graph_nodes._run_single_analyst",
            new_callable=AsyncMock,
            return_value=AnalystReport(analyst_type="technical"),
        ) as analyst,
        patch(
            "src.debate.graph_nodes._run_single_master",
            new_callable=AsyncMock,
            side_effect=master_result,
        ) as master,
        patch(
            "src.debate.graph_nodes._run_review_for_master",
            new_callable=AsyncMock,
            return_value=RebuttalAnalysis(agent_name="master.test"),
        ) as review,
        patch(
            "src.debate.graph_nodes._run_independent_review",
            new_callable=AsyncMock,
            return_value=IndependentReview(),
        ) as independent,
    ):
        result = await orch.run(
            DebateInput(
                instrument_type="etf",
                stock_code="560780",
                stock_name="半导体设备ETF广发",
                question="ETF研究",
            )
        )
    assert result.instrument_type == "etf" and len(result.analyses) == 2
    assert (
        analyst.await_count > 0
        and master.await_count == 2
        and review.await_count == 2
        and independent.await_count == 1
    )
    assert collector.mock_calls == []
    assert result.evidence_limitations and result.trade_recommendation is None
    assert all(
        call.kwargs["market_data"]["instrument_type"] == "etf" for call in master.await_args_list
    )


@pytest.mark.asyncio
async def test_missing_or_wrong_etf_context_blocks_before_model():
    for prepared in (None, context().model_copy(update={"stock_code": "512480"})):
        orch = DebateOrchestrator(
            data_collector=MagicMock(),
            quote_evidence_service=None,
            prepared_research=prepared,
            skill_ids=["buffett"],
        )
        with patch("src.debate.graph_nodes._run_single_analyst", new_callable=AsyncMock) as model:
            with pytest.raises(EvidenceIncompleteError):
                await orch.run(
                    DebateInput(
                        instrument_type="etf", stock_code="560780", stock_name="半导体设备ETF广发"
                    )
                )
        model.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_kind_filter_before_pagination_and_immutable_identity(tmp_path):
    store = SqliteDebateSessionStore(tmp_path / "sessions.db")
    for kind in ("stock", "etf"):
        await store.save(
            DebateSessionRecord(
                session_id=kind,
                stock_code="560780",
                instrument_type=kind,
                status="running",
                progress=0,
            )
        )
    assert [
        r.session_id for r in await store.list_records("560780", instrument_type="stock", limit=1)
    ] == ["stock"]
    assert [
        r.session_id for r in await store.list_records("560780", instrument_type="etf", limit=1)
    ] == ["etf"]
    with pytest.raises(SessionStoreError, match="identity"):
        await store.save(
            DebateSessionRecord(
                session_id="stock",
                stock_code="560780",
                instrument_type="etf",
                status="running",
                progress=10,
            )
        )
    # Legacy payloads default to stock; an ETF envelope cannot carry a stock result.
    assert DebateInput(stock_code="000001").instrument_type == "stock"
    with pytest.raises(ValidationError, match="instrument_type"):
        DebateSessionRecord(
            session_id="x",
            stock_code="560780",
            instrument_type="etf",
            status="completed",
            progress=100,
            result=DebateResult(session_id="x", stock_code="560780", stock_name="ETF", question=""),
        )

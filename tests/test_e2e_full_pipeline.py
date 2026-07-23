"""端到端全链路测试 —— 验证 9 层辩论流程完整跑通

测试策略（不调用真实 LLM）：
- 所有 LLM 调用通过 mock_llm fixture 模拟（返回空结构实例）
- master_round 额外 mock _run_single_master 确保返回有效 AgentAnalysis
- risk/trader/pm 模块通过 llm_service mock 自动覆盖
- 验证每层输出结构正确、不崩、不抛异常

被测流程：
  collect_data → analyst_round(4) → master_round(5)
  → review_round(D1) → review_report(D3) → aggregate
  → risk_round(R1×3) → trader_round(T1) → pm_round(PM)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import AgentAnalysis, DebateInput, DebateResult
from src.debate.orchestrator import DebateOrchestrator


@pytest.fixture
def mock_collector():
    """Mock DataCollector 返回空数据（避免网络调用）"""
    col = MagicMock()
    col.get_realtime_quotes.return_value = []
    col.get_klines.return_value = []
    col.get_news.return_value = []
    col.get_financials.return_value = []
    return col


@pytest.fixture
def mock_agent_analysis():
    """预设的有效 AgentAnalysis，供 master_round mock 使用"""
    return AgentAnalysis(
        agent_name="master.test",
        skill_id="test",
        skill_name="测试大师",
        rating="看涨",
        score=80,
        summary="测试摘要",
        analysis="测试分析内容",
        key_evidence=["证据1"],
        confidence=0.8,
        direction="Bullish",
    )


@pytest.mark.slow
class TestE2EFullPipeline:
    """端到端全链路 9 层测试（~300s 合计，标记为 slow）"""

    @pytest.mark.asyncio
    async def test_full_pipeline_basic(
        self, mock_collector, mock_llm, mock_agent_analysis
    ):
        """基础链路：collect_data → analyst → master → review → review_report → aggregate

        验证 6 层基础流程（不含风控/交易员/PM 层）
        """
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger", "graham"],
            enable_risk=False,
            enable_trader=False,
        )

        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_agent_analysis,
        ):
            result = await orch.run(
                DebateInput(
                    stock_code="000001",
                    stock_name="平安银行",
                    question="测试全链路",
                )
            )

        assert isinstance(result, DebateResult)
        assert result.stock_code == "000001"
        assert result.total_latency_ms >= 0

        # 分析师层 (analyst_round)
        assert result.analyst_reports is not None
        assert len(result.analyst_reports) == 4

        # 大师层 (master_round)
        assert len(result.analyses) == 3
        for a in result.analyses:
            assert a.success is True
            assert a.score > 0

        # 交叉审阅层 (review_round / D1)
        # mock_llm 可能返回空 RebuttalAnalysis → run() 中可能被跳过
        # 不强制断言存在，但流程不崩即可

        # 独立评审层 (review_report / D3)
        # mock_llm 返回空 IndependentReview → overall_quality=0.0 → run() 中跳过
        # 不强制断言存在，但流程不崩即可

        # 投票聚合层 (aggregate)
        vs = result.vote_summary
        assert vs.total_votes == 3
        assert vs.average_score > 0
        assert vs.consensus != ""
        assert vs.confidence > 0
        assert vs.direction_distribution != {}

    @pytest.mark.asyncio
    async def test_full_pipeline_with_all_layers(
        self, mock_collector, mock_llm, mock_agent_analysis
    ):
        """全 9 层链路：基础层 + R1 风控 + T1 交易员 + PM 裁决"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger"],
            enable_risk=True,
            enable_trader=True,
        )

        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_agent_analysis,
        ):
            result = await orch.run(
                DebateInput(stock_code="600519", stock_name="贵州茅台")
            )

        assert isinstance(result, DebateResult)
        assert len(result.analyses) == 2

        # 分析师层
        assert result.analyst_reports is not None
        assert len(result.analyst_reports) == 4

        # 投票层
        assert result.vote_summary.total_votes == 2

        # ── R1 风控层 ──
        # mock_llm 返回空 RiskRoundResult → 风控层可能为空 dict
        # 只要流程不崩就算通过

        # ── T1 交易员层 ──
        # mock_llm 返回空 TraderRoundResult → 同上

        # ── PM 裁决层 ──
        # mock_llm 返回空 TradeRecommendation → 同上

        assert result.total_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_memory(
        self, mock_collector, mock_llm, mock_agent_analysis
    ):
        """带 memory store + reflection 的全链路

        验证记忆系统与全链路集成不阻塞：
        - memory_store.search 被调用（历史决策 + 反思查询）
        - memory_store.put 被调用（结果保存）
        """
        mock_memory = MagicMock()
        mock_memory.search.return_value = []
        mock_memory.put.return_value = None

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_memory,
            skill_ids=["buffett", "munger"],
            enable_risk=True,
            enable_trader=True,
            enable_reflection=True,
        )

        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_agent_analysis,
        ):
            result = await orch.run(
                DebateInput(
                    stock_code="000001",
                    stock_name="平安银行",
                    session_id="e2e-memory-test",
                )
            )

        assert isinstance(result, DebateResult)
        assert len(result.analyses) == 2

        # memory_store.search 应被调用过（历史决策 + 反思查询）
        assert mock_memory.search.call_count >= 2
        # memory_store.put 应被调用过（结果保存）
        assert mock_memory.put.call_count >= 1

    @pytest.mark.asyncio
    async def test_pipeline_error_resilience(self, mock_collector, mock_agent_analysis):
        """全链路容错性：数据采集失败、部分大师分析失败时流程不崩溃"""
        # DataCollector 网络异常
        mock_collector.get_realtime_quotes.side_effect = ConnectionError("网络不可用")
        mock_collector.get_klines.side_effect = ConnectionError("网络不可用")
        mock_collector.get_news.side_effect = ConnectionError("网络不可用")

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger"],
            enable_risk=True,
            enable_trader=True,
        )

        # 1 位大师成功、1 位失败
        failed_analysis = AgentAnalysis(
            agent_name="master.munger",
            skill_id="munger",
            skill_name="芒格",
            rating="中性",
            score=0,
            summary="",
            analysis="",
            confidence=0.0,
            success=False,
            error="分析超时",
        )

        call_count = [0]

        def _side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_agent_analysis
            return failed_analysis

        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            side_effect=_side_effect,
        ):
            result = await orch.run(
                DebateInput(stock_code="000001", stock_name="平安银行")
            )

        assert isinstance(result, DebateResult)
        assert len(result.analyses) == 2  # 返回 2 位（1 成功 1 失败）
        assert result.vote_summary.total_votes == 1  # aggregate 只统计成功的
        assert result.vote_summary.average_score > 0
        assert result.total_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_pipeline_to_summary_dict(
        self, mock_collector, mock_llm, mock_agent_analysis
    ):
        """全链路结果 to_summary_dict 可用"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger"],
            enable_risk=True,
            enable_trader=True,
        )

        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_agent_analysis,
        ):
            result = await orch.run(DebateInput(stock_code="000001"))

        summary = result.to_summary_dict()
        assert isinstance(summary, dict)
        assert summary["股票代码"] == "000001"
        assert summary["参与大师数"] == 2
        assert summary["共识"] != ""
        assert summary["平均评分"] > 0
        assert summary["总耗时(ms)"] >= 0
        assert summary.get("分析师报告数") == 4
        # mock_llm 返回空数据 → 风控/交易/PM 层可能有默认值或为空
        # 只要不抛异常即通过

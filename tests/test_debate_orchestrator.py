"""辩论编排器单元测试

Mock 策略：
- DataCollector → mock 返回预置行情/K线数据
- MasterAgent → mock llm_service.invoke_structured 返回模拟分析
- 不调用真实 API
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import AgentAnalysis, DebateInput, DebateResult
from src.debate.orchestrator import (
    DebateOrchestrator,
    DebateState,
    aggregate_node,
    collect_data_node,
    make_master_round_node,
)
from src.memory.skill_disk import SkillDisk


@pytest.fixture
def sample_debate_input() -> DebateInput:
    return DebateInput(
        stock_code="000001",
        stock_name="平安银行",
        question="是否值得投资？",
    )


@pytest.fixture
def mock_collector() -> MagicMock:
    """Mock DataCollector 返回空列表（避免网络调用）"""
    col = MagicMock()
    col.get_realtime_quotes.return_value = []
    col.get_klines.return_value = []
    col.get_news.return_value = []
    return col



# ═══════════════════════════════════════════════════════════════════
# 图结构测试
# ═══════════════════════════════════════════════════════════════════


class TestGraphConstruction:
    """验证辩论编排器的 LangGraph 图构建"""

    def test_create_orchestrator(self, mock_collector):
        """Orchestrator 创建"""
        orch = DebateOrchestrator(data_collector=mock_collector)
        assert orch is not None
        assert orch.data_collector is mock_collector

    def test_build_graph_has_nodes(self, mock_collector):
        """验证图包含所有必需节点"""
        orch = DebateOrchestrator(data_collector=mock_collector)
        graph = orch._build_graph()
        # 编译后验证节点存在
        app = graph.compile()
        # get_graph() 应返回非空图
        graph_def = app.get_graph()
        assert graph_def is not None

    def test_default_masters_loaded(self, mock_collector):
        """默认大师自动加载"""
        orch = DebateOrchestrator(data_collector=mock_collector)
        assert len(orch.master_skills) > 0
        skill_ids = [s.skill_id for s in orch.master_skills]
        assert "buffett" in skill_ids
        assert "munger" in skill_ids
        assert "graham" in skill_ids

    def test_custom_masters(self, mock_collector):
        """自定义大师列表"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "dalio"],
        )
        assert len(orch.master_skills) == 2
        assert orch.master_skills[0].skill_id == "buffett"
        assert orch.master_skills[1].skill_id == "dalio"


# ═══════════════════════════════════════════════════════════════════
# 节点函数测试
# ═══════════════════════════════════════════════════════════════════


class TestCollectDataNode:
    """collect_data_node 验证"""

    def test_collect_data_success(self, mock_collector):
        """成功采集数据"""
        state: DebateState = {
            "session_id": "test-s1",
            "debate_input": {
                "stock_code": "000001",
                "stock_name": "平安银行",
            },
            "current_round": 0,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = collect_data_node(state, mock_collector)
        assert "market_data" in result
        assert mock_collector.get_realtime_quotes.called

    def test_collect_data_failure(self):
        """采集失败时降级"""
        failing = MagicMock()
        failing.get_realtime_quotes.side_effect = ConnectionError("网络不可用")
        failing.get_klines.side_effect = ConnectionError("网络不可用")
        failing.get_news.side_effect = ConnectionError("网络不可用")

        state: DebateState = {
            "session_id": "test-s2",
            "debate_input": {"stock_code": "000001"},
            "current_round": 0,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = collect_data_node(state, failing)
        # 即使失败也不应抛异常，应返回空数据
        assert "market_data" in result
        md = result["market_data"]
        assert md.get("quotes") == []
        assert md.get("klines") == []

    def test_collect_data_node_has_brief(self, mock_collector):
        """market_data 包含 brief 和 quote 字段"""
        state: DebateState = {
            "session_id": "test-brief",
            "debate_input": {
                "stock_code": "000001",
                "stock_name": "平安银行",
            },
            "current_round": 0,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = collect_data_node(state, mock_collector)
        md = result["market_data"]
        assert "brief" in md, "缺少 brief 字段"
        assert isinstance(md["brief"], str), "brief 应为字符串"
        assert len(md["brief"]) > 0, "brief 不应为空"
        # mock collector 返回空列表 → 简报应为"暂无可用数据"
        assert "暂无可用数据" in md["brief"]
        # quote 应为 None（空数据时）
        assert md["quote"] is None


class TestMasterRoundNode:
    """make_master_round_node 验证"""

    @pytest.fixture
    def buffett_skill(self):
        disk = SkillDisk()
        return disk.load("buffett")

    @pytest.mark.asyncio
    async def test_master_node_success(self, buffett_skill):
        """大师分析成功"""
        state: DebateState = {
            "session_id": "test-s3",
            "debate_input": {
                "stock_code": "000001",
                "question": "是否值得投资？",
                "stock_name": "",
            },
            "current_round": 1,
            "analyses": {},
            "market_data": {"quotes": [], "klines": [], "news": []},
            "vote_summary": {},
            "errors": [],
        }

        # mock _run_single_master 返回预设的分析结果
        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=85,
            summary="看好",
            analysis="分析内容",
            key_evidence=["证据1", "证据2"],
            confidence=0.85,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_analysis,
        ):
            node_fn = make_master_round_node([buffett_skill])
            result = await node_fn(state)

            assert "analyses" in result
            assert "master.buffett" in result["analyses"]
            analysis = result["analyses"]["master.buffett"]
            assert isinstance(analysis, AgentAnalysis)
            assert analysis.skill_id == "buffett"
            assert analysis.success is True
            assert analysis.rating == "看涨"
            assert analysis.score == 85

    @pytest.mark.asyncio
    async def test_master_node_failure(self, buffett_skill):
        """大师分析失败不阻塞"""
        state: DebateState = {
            "session_id": "test-s4",
            "debate_input": {
                "stock_code": "000001",
                "question": "测试问题",
                "stock_name": "",
            },
            "current_round": 1,
            "analyses": {},
            "market_data": {"quotes": [], "klines": [], "news": []},
            "vote_summary": {},
            "errors": [],
        }

        # mock _run_single_master 返回失败分析
        failed_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="中性",
            score=0,
            summary="",
            analysis="",
            key_evidence=[],
            confidence=0.0,
            success=False,
            error="分析超时",
            latency_ms=120000.0,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=failed_analysis,
        ):
            node_fn = make_master_round_node([buffett_skill])
            result = await node_fn(state)

            assert "analyses" in result
            analysis = result["analyses"]["master.buffett"]
            assert analysis.success is False
            assert analysis.error == "分析超时"
            assert analysis.rating == "中性"
            assert analysis.score == 0


class TestAggregateNode:
    """aggregate_node 验证"""

    @pytest.mark.asyncio
    async def test_aggregate_all_success(self):
        """所有大师都成功"""
        state: DebateState = {
            "session_id": "test-aggr-1",
            "debate_input": {},
            "current_round": 1,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="...",
                    key_evidence=[],
                    confidence=0.85,
                    latency_ms=1000.0,
                ),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=60,
                    summary="中性",
                    analysis="...",
                    key_evidence=[],
                    confidence=0.60,
                    latency_ms=1500.0,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = await aggregate_node(state)
        assert "vote_summary" in result
        vs = result["vote_summary"]
        assert vs.total_votes == 2
        assert vs.consensus == "看涨"  # 众数（虽然2个不同，取第一个）
        assert vs.average_score == 72.5  # (85+60)/2

    @pytest.mark.asyncio
    async def test_aggregate_with_failures(self):
        """失败的大师被排除"""
        state: DebateState = {
            "session_id": "test-aggr-2",
            "debate_input": {},
            "current_round": 1,
            "analyses": {
                "master.buffett": AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="...",
                    key_evidence=[],
                    confidence=0.85,
                    latency_ms=1000.0,
                ),
                "master.fail": AgentAnalysis(
                    agent_name="master.fail",
                    skill_id="fail",
                    skill_name="失败大师",
                    rating="中性",
                    score=0,
                    summary="",
                    analysis="",
                    key_evidence=[],
                    confidence=0.0,
                    success=False,
                    error="超时",
                    latency_ms=120000.0,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "errors": ["master.fail 执行失败"],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.total_votes == 1  # 只统计成功的
        assert vs.average_score == 85.0

    @pytest.mark.asyncio
    async def test_aggregate_all_failed(self):
        """全部失败时返回空汇总"""
        state: DebateState = {
            "session_id": "test-aggr-3",
            "debate_input": {},
            "current_round": 1,
            "analyses": {
                "master.fail1": AgentAnalysis(
                    agent_name="master.fail1",
                    skill_id="f1",
                    skill_name="失败1",
                    rating="中性",
                    score=0,
                    summary="",
                    analysis="",
                    key_evidence=[],
                    confidence=0.0,
                    success=False,
                    error="超时",
                    latency_ms=120000.0,
                ),
            },
            "market_data": {},
            "vote_summary": {},
            "errors": ["全部失败"],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.total_votes == 0
        assert vs.consensus == "中性"
        assert vs.average_score == 0.0

    @pytest.mark.asyncio
    async def test_aggregate_empty(self):
        """无分析结果"""
        state: DebateState = {
            "session_id": "test-aggr-4",
            "debate_input": {},
            "current_round": 1,
            "analyses": {},
            "market_data": {},
            "vote_summary": {},
            "errors": [],
        }
        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.total_votes == 0


# ═══════════════════════════════════════════════════════════════════
# 完整编排器运行测试
# ═══════════════════════════════════════════════════════════════════


class TestDebateOrchestratorRun:
    """DebateOrchestrator.run() 完整流程"""

    @pytest.mark.asyncio
    async def test_full_flow(self, mock_collector):
        """完整三节点流程"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett", "munger"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
            key_evidence=["证据"],
            confidence=0.8,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_analysis,
        ):
            inp = DebateInput(
                stock_code="000001",
                stock_name="平安银行",
                question="测试",
            )
            result = await orch.run(inp)

            assert isinstance(result, DebateResult)
            assert result.stock_code == "000001"
            assert len(result.analyses) == 2
            assert result.vote_summary.total_votes == 2
            assert result.total_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_with_default_masters(self, mock_collector):
        """使用默认 5 位大师运行"""
        orch = DebateOrchestrator(data_collector=mock_collector)

        mock_analysis = AgentAnalysis(
            agent_name="master.test",
            skill_id="test",
            skill_name="测试大师",
            rating="看涨",
            score=75,
            summary="测试",
            analysis="测试分析",
            key_evidence=[],
            confidence=0.75,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_analysis,
        ):
            inp = DebateInput(stock_code="600519")
            result = await orch.run(inp)

            assert len(result.analyses) == 5  # 5 位默认大师
            assert result.vote_summary.total_votes == 5

    @pytest.mark.asyncio
    async def test_run_single_master(self, mock_collector):
        """单大师运行"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=90,
            summary="非常看好",
            analysis="详细分析",
            key_evidence=["优势明显"],
            risk_warning="注意回调风险",
            confidence=0.9,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_analysis,
        ):
            result = await orch.run(DebateInput(stock_code="000001"))

            assert len(result.analyses) == 1
            analysis = result.analyses[0]
            assert analysis.rating == "看涨"
            assert analysis.risk_warning == "注意回调风险"
            assert result.vote_summary.consensus == "看涨"

    @pytest.mark.asyncio
    async def test_run_summary_dict(self, mock_collector):
        """to_summary_dict 可用"""
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=85,
            summary="看好",
            analysis="分析",
            key_evidence=["证据"],
            confidence=0.85,
        )
        with patch(
            "src.debate.orchestrator._run_single_master",
            new_callable=AsyncMock,
            return_value=mock_analysis,
        ):
            result = await orch.run(DebateInput(stock_code="000001"))
            summary = result.to_summary_dict()
            assert summary["共识"] == "看涨"
            assert summary["参与大师数"] == 1

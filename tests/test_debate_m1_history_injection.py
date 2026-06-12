"""M1 历史决策注入测试

测试策略：
- _format_history_context 格式化逻辑（空列表/不相关/相关）
- DebateOrchestrator 接受 memory_store 参数
- history_context 注入到 _run_single_master 的 enhanced prompt
- _save_decision_to_memory 保存正确数据
- MemoryStore 失败不阻塞辩论流程
- 全流程集成测试（mock MemoryStore + LLM 层）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import (
    AgentAnalysis,
    DebateInput,
    DebateResult,
    IndependentReview,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.orchestrator import (
    DebateOrchestrator,
    _format_history_context,
    _run_single_master,
)
from src.memory.skill_disk import SkillDisk
from src.memory.store import MemoryItem


# ═══════════════════════════════════════════════════════════════════
# Phase 1: _format_history_context 格式化逻辑
# ═══════════════════════════════════════════════════════════════════


class TestFormatHistoryContext:
    """_format_history_context 格式化函数验证"""

    def test_empty_items(self):
        """空列表返回空字符串"""
        result = _format_history_context([], "000001")
        assert result == ""

    def test_no_relevant_items(self):
        """没有匹配股票代码的历史记录时返回空字符串"""
        items = [
            MemoryItem(
                key="600519",
                value={
                    "stock_code": "600519",
                    "question": "茅台值得投资吗？",
                    "consensus": "看涨",
                },
            ),
            MemoryItem(
                key="000002",
                value={
                    "stock_code": "000002",
                    "question": "万科如何？",
                    "consensus": "中性",
                },
            ),
        ]
        result = _format_history_context(items, "000001")
        assert result == ""

    def test_single_relevant_item(self):
        """一条匹配的历史记录应输出格式化文本"""
        items = [
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "question": "是否值得投资？",
                    "timestamp": "2026-06-10T10:00:00",
                    "consensus": "看涨",
                    "average_score": 72.5,
                    "confidence": 0.75,
                    "total_votes": 3,
                    "analyses_summary": [
                        {
                            "agent_name": "master.buffett",
                            "skill_name": "巴菲特",
                            "rating": "看涨",
                            "score": 85,
                            "summary": "看好平安银行零售转型",
                        },
                    ],
                },
            ),
        ]
        result = _format_history_context(items, "000001")
        assert "历史决策参考" in result
        assert "平安银行" in result
        assert "看涨" in result
        assert "72.5" in result
        assert "巴菲特" in result
        assert "85分" in result
        assert "历史决策 #1" in result

    def test_multiple_items_ordered_by_recency(self):
        """多条记录应逆序显示（最新在前）"""
        items = [
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "question": "问题A",
                    "timestamp": "2026-06-01",
                    "consensus": "看涨",
                    "average_score": 70.0,
                    "confidence": 0.6,
                    "total_votes": 2,
                },
            ),
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "question": "问题B",
                    "timestamp": "2026-06-10",
                    "consensus": "看跌",
                    "average_score": 40.0,
                    "confidence": 0.8,
                    "total_votes": 4,
                },
            ),
        ]
        result = _format_history_context(items, "000001")
        # 最新（2026-06-10）应该先出现
        first_hit = result.index("历史决策 #1")
        second_hit = result.index("历史决策 #2")
        assert first_hit < second_hit
        # 最新的是 "问题B"
        assert result.index("问题B") < result.index("问题A")

    def test_mixed_relevant_and_irrelevant(self):
        """混合相关和不相关的股票代码"""
        items = [
            MemoryItem(
                key="600519",
                value={"stock_code": "600519", "consensus": "看涨"},
            ),
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "question": "平安如何？",
                    "consensus": "中性",
                },
            ),
        ]
        result = _format_history_context(items, "000001")
        assert "历史决策参考" in result
        assert "平安" in result
        assert "600519" not in result  # 不相关的股票不应出现

    def test_items_with_string_value(self):
        """值为字符串时安全处理"""
        items = [
            MemoryItem(key="000001", value="not a dict"),
        ]
        result = _format_history_context(items, "000001")
        assert result == ""

    def test_items_with_empty_value(self):
        """值为空字典时安全处理"""
        items = [
            MemoryItem(key="000001", value={}),
        ]
        result = _format_history_context(items, "000001")
        assert result == ""


# ═══════════════════════════════════════════════════════════════════
# Phase 2: DebateOrchestrator 接受 memory_store
# ═══════════════════════════════════════════════════════════════════


class TestOrchestratorWithMemoryStore:
    """DebateOrchestrator 与 MemoryStore 集成"""

    def test_accepts_memory_store(self):
        """Orchestrator 接受 memory_store 参数"""
        mock_store = MagicMock()
        orch = DebateOrchestrator(memory_store=mock_store)
        assert orch.memory_store is mock_store

    def test_memory_store_defaults_to_none(self):
        """不传 memory_store 时默认为 None（向后兼容）"""
        orch = DebateOrchestrator()
        assert orch.memory_store is None

    def test_with_mock_collector_and_store(self):
        """同时传入 data_collector 和 memory_store"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        mock_store = MagicMock()
        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
            skill_ids=["buffett"],
        )
        assert orch.data_collector is mock_collector
        assert orch.memory_store is mock_store
        assert len(orch.master_skills) == 1


# ═══════════════════════════════════════════════════════════════════
# Phase 3: history_context 注入到 _run_single_master
# ═══════════════════════════════════════════════════════════════════


class TestHistoryInjection:
    """history_context 注入到大师 prompt 验证"""

    @pytest.fixture
    def buffett_skill(self):
        disk = SkillDisk()
        return disk.load("buffett")

    @pytest.mark.asyncio
    async def test_history_injected_into_enhanced_prompt(self, buffett_skill):
        """history_context 出现在增强问题中"""
        history_text = "\n📜 测试历史决策\n共识：看涨"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"analysis": {
            "rating": "看涨",
            "score": 80,
            "summary": "测试",
            "analysis": "测试分析",
            "key_evidence": [],
        }}
        mock_result.confidence = 0.8

        with patch(
            "src.debate.orchestrator.MasterAgent",
            new_callable=MagicMock,
        ) as MockMaster:
            mock_agent = AsyncMock()
            mock_agent.run_safe.return_value = mock_result
            MockMaster.return_value = mock_agent

            result = await _run_single_master(
                skill=buffett_skill,
                session_id="test-s1",
                question="测试问题",
                stock_code="000001",
                stock_name="平安银行",
                market_data={"brief": "测试市场简报"},
                history_context=history_text,
            )

            assert result.success is True
            # 验证 history_context 被传递给 MasterAgent
            call_kwargs = MockMaster.call_args.kwargs
            assert call_kwargs["skill"] is buffett_skill

            # 验证 run_safe 的 input_data 中包含 history_context
            run_ctx = mock_agent.run_safe.call_args[0][0]
            question_with_history = run_ctx.input_data["question"]
            assert "📜 测试历史决策" in question_with_history
            assert "共识：看涨" in question_with_history
            # 原始问题也在其中
            assert "测试问题" in question_with_history
            # 市场数据也在其中
            assert "测试市场简报" in question_with_history

    @pytest.mark.asyncio
    async def test_empty_history_no_change(self, buffett_skill):
        """空 history_context 不影响 prompt"""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"analysis": {
            "rating": "中性",
            "score": 50,
            "summary": "测试",
            "analysis": "测试分析",
            "key_evidence": [],
        }}
        mock_result.confidence = 0.5

        with patch(
            "src.debate.orchestrator.MasterAgent",
            new_callable=MagicMock,
        ) as MockMaster:
            mock_agent = AsyncMock()
            mock_agent.run_safe.return_value = mock_result
            MockMaster.return_value = mock_agent

            _ = await _run_single_master(
                skill=buffett_skill,
                session_id="test-s2",
                question="纯测试问题",
                stock_code="000001",
                stock_name="平安银行",
                market_data={"brief": "数据"},
                history_context="",
            )

            run_ctx = mock_agent.run_safe.call_args[0][0]
            question = run_ctx.input_data["question"]
            assert "📜" not in question  # 没有历史注入
            assert "纯测试问题" in question

    @pytest.mark.asyncio
    async def test_history_injected_via_orchestrator_run(self):
        """完整流程中 history_context 通过 state 传递"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        # 创建一个 mock MemoryStore，返回历史记录
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "question": "上次分析",
                    "timestamp": "2026-06-01",
                    "consensus": "看涨",
                    "average_score": 75.0,
                    "confidence": 0.8,
                    "total_votes": 3,
                    "analyses_summary": [],
                },
            ),
        ])

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
            key_evidence=[],
            confidence=0.8,
        )

        # mock _run_single_master 验证 history_context 被传递
        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ) as mock_run,
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(stock_code="000001", stock_name="平安银行")
            result = await orch.run(inp)

            # 验证 _run_single_master 被调用时传入了 history_context
            call_kwargs = mock_run.call_args.kwargs
            assert "history_context" in call_kwargs
            assert "历史决策参考" in call_kwargs["history_context"]
            assert "上次分析" in call_kwargs["history_context"]
            assert result.stock_code == "000001"
            assert len(result.analyses) == 1


# ═══════════════════════════════════════════════════════════════════
# Phase 4: _save_decision_to_memory 验证
# ═══════════════════════════════════════════════════════════════════


class TestSaveDecisionToMemory:
    """_save_decision_to_memory 保存逻辑验证"""

    @pytest.mark.asyncio
    async def test_saves_correct_data(self):
        """保存的数据结构正确"""
        mock_store = MagicMock()
        mock_store.put = AsyncMock()

        orch = DebateOrchestrator(memory_store=mock_store)

        result = DebateResult(
            session_id="test-s1",
            stock_code="000001",
            stock_name="平安银行",
            question="是否值得投资？",
            analyses=[
                AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=85,
                    summary="看好",
                    analysis="详细分析",
                    key_evidence=["护城河"],
                    confidence=0.85,
                ),
            ],
            vote_summary=VoteSummary(
                total_votes=1,
                rating_distribution={"看涨": 1},
                average_score=85.0,
                weighted_score=85.0,
                consensus="看涨",
                confidence=0.85,
            ),
        )

        await orch._save_decision_to_memory(result)

        mock_store.put.assert_called_once()
        call_args = mock_store.put.call_args
        assert call_args.kwargs["key"] == "000001"
        assert call_args.kwargs["namespace"] == ("episodic", "debate")

        value = call_args.kwargs["value"]
        assert value["stock_code"] == "000001"
        assert value["consensus"] == "看涨"
        assert value["average_score"] == 85.0
        assert value["total_votes"] == 1
        assert len(value["analyses_summary"]) == 1
        assert value["analyses_summary"][0]["skill_name"] == "巴菲特"
        assert "timestamp" in value

    @pytest.mark.asyncio
    async def test_saves_with_review_report(self):
        """包含 review_report 时一并保存"""
        mock_store = MagicMock()
        mock_store.put = AsyncMock()

        orch = DebateOrchestrator(memory_store=mock_store)

        result = DebateResult(
            session_id="test-s2",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            analyses=[],
            vote_summary=VoteSummary(),
            review_report=IndependentReview(
                overall_quality=0.8,
                independent_rating="看涨",
                independent_score=75,
            ),
        )

        await orch._save_decision_to_memory(result)

        value = mock_store.put.call_args.kwargs["value"]
        assert "review_report" in value
        assert value["review_report"]["overall_quality"] == 0.8
        assert value["review_report"]["independent_rating"] == "看涨"

    @pytest.mark.asyncio
    async def test_no_store_no_error(self):
        """memory_store 为 None 时不保存也不报错"""
        orch = DebateOrchestrator()  # memory_store=None
        result = DebateResult(
            session_id="test-s3",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            analyses=[],
            vote_summary=VoteSummary(),
        )
        # 不应抛出异常
        await orch._save_decision_to_memory(result)

    @pytest.mark.asyncio
    async def test_store_failure_no_crash(self):
        """memory_store.put 失败时不阻塞"""
        mock_store = MagicMock()
        mock_store.put = AsyncMock(side_effect=RuntimeError("存储失败"))

        orch = DebateOrchestrator(memory_store=mock_store)
        result = DebateResult(
            session_id="test-s4",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            analyses=[],
            vote_summary=VoteSummary(),
        )
        # 不应抛出异常
        await orch._save_decision_to_memory(result)
        mock_store.put.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# Phase 5: MemoryStore 失败不阻塞全流程
# ═══════════════════════════════════════════════════════════════════


class TestMemoryResilience:
    """MemoryStore 异常时辩论流程不中断"""

    @pytest.mark.asyncio
    async def test_search_failure_does_not_block_debate(self):
        """memory_store.search 异常时不阻塞"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        mock_store = MagicMock()
        mock_store.search = AsyncMock(side_effect=RuntimeError("查询失败"))

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
            key_evidence=[],
            confidence=0.8,
        )

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)

            assert isinstance(result, DebateResult)
            assert len(result.analyses) == 1
            assert result.vote_summary.total_votes == 1

    @pytest.mark.asyncio
    async def test_save_failure_does_not_block_return(self):
        """保存决策失败不阻塞返回结果"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])
        # save 会尝试 put
        mock_store.put = AsyncMock(side_effect=RuntimeError("保存失败"))

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
            skill_ids=["buffett"],
        )

        mock_analysis = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
            key_evidence=[],
            confidence=0.8,
        )

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)

            # 即使保存失败，也应返回有效的 DebateResult
            assert isinstance(result, DebateResult)
            assert result.vote_summary.total_votes == 1
            # 验证 save 被调用过（put 被尝试过）
            assert mock_store.put.called


# ═══════════════════════════════════════════════════════════════════
# Phase 6: 集成测试 — 完整流程
# ═══════════════════════════════════════════════════════════════════


class TestFullFlowWithMemory:
    """完整流程集成测试"""

    @pytest.mark.asyncio
    async def test_full_flow_with_history(self):
        """全流程：3 位大师 + 历史注入 + 保存"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "stock_name": "平安银行",
                    "question": "是否值得投资？",
                    "timestamp": "2026-06-01",
                    "consensus": "看涨",
                    "average_score": 72.5,
                    "confidence": 0.75,
                    "total_votes": 3,
                    "analyses_summary": [
                        {"agent_name": "master.buffett", "skill_name": "巴菲特",
                         "rating": "看涨", "score": 85, "summary": "看好"},
                        {"agent_name": "master.munger", "skill_name": "芒格",
                         "rating": "中性", "score": 60, "summary": "谨慎"},
                    ],
                },
            ),
        ])
        mock_store.put = AsyncMock()

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
            skill_ids=["buffett", "munger", "graham"],
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

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(
                stock_code="000001",
                stock_name="平安银行",
                question="是否值得投资？",
            )
            result = await orch.run(inp)

            # 基础验证
            assert isinstance(result, DebateResult)
            assert result.stock_code == "000001"
            assert len(result.analyses) == 3

            # 验证 history_context 生成了
            assert mock_store.search.called

            # 验证结果保存了
            assert mock_store.put.called
            saved_value = mock_store.put.call_args.kwargs["value"]
            assert saved_value["stock_code"] == "000001"
            assert saved_value["total_votes"] == 3

    @pytest.mark.asyncio
    async def test_no_memory_store_flow(self):
        """不传入 memory_store 时正常工作（向后兼容）"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            skill_ids=["buffett"],
        )
        assert orch.memory_store is None

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

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)

            assert isinstance(result, DebateResult)
            assert len(result.analyses) == 1
            assert result.vote_summary.consensus == "看涨"

    @pytest.mark.asyncio
    async def test_to_summary_dict_with_history(self):
        """含历史注入的完整流程 to_summary_dict 可用"""
        mock_collector = MagicMock()
        mock_collector.get_realtime_quotes.return_value = []
        mock_collector.get_klines.return_value = []
        mock_collector.get_news.return_value = []

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.put = AsyncMock()

        orch = DebateOrchestrator(
            data_collector=mock_collector,
            memory_store=mock_store,
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

        with (
            patch(
                "src.debate.orchestrator._run_single_master",
                new_callable=AsyncMock,
                return_value=mock_analysis,
            ),
            patch(
                "src.debate.orchestrator._run_review_for_master",
                new_callable=AsyncMock,
                return_value=RebuttalAnalysis(agent_name="master.mock"),
            ),
            patch(
                "src.debate.orchestrator._run_independent_review",
                new_callable=AsyncMock,
                return_value=IndependentReview(),
            ),
        ):
            inp = DebateInput(stock_code="000001")
            result = await orch.run(inp)
            summary = result.to_summary_dict()
            assert summary["共识"] == "看涨"
            assert summary["参与大师数"] == 1

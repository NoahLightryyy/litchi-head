"""D2 强制输出方向 —— 单元测试

测试策略（与 D1/D3/M1 测试模式一致）：
- InvestmentAnalysis direction 字段模型验证
- AgentAnalysis direction 字段模型验证
- VoteSummary direction_distribution 追踪验证
- MasterAgent.run() prompt 包含方向约束指令
- _run_single_master 方向映射与规范化
- aggregate_node 方向分布统计
- DebateResult.to_summary_dict 含方向信息
- 全流程集成测试（mock LLM 层）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentContext
from src.agents.master_agent import InvestmentAnalysis, MasterAgent
from src.debate.models import (
    AgentAnalysis,
    AnalystReport,
    DebateInput,
    DebateResult,
    IndependentReview,
    RebuttalAnalysis,
    VoteSummary,
)
from src.debate.orchestrator import (
    DebateOrchestrator,
    _run_single_master,
    aggregate_node,
)
from src.memory.skill_disk import MasterSkill

# ── 测试用大师 Skill ─────────────────────────

_BUFFETT_SKILL = MasterSkill(
    skill_id="buffett",
    name="沃伦·巴菲特",
    avatar="🧑‍🦳",
    title="伯克希尔·哈撒韦 CEO",
    description="价值投资大师",
    system_prompt="我是巴菲特。原则：安全边际、护城河、长期持有。",
    knowledge_filter="巴菲特",
    enabled_by_default=True,
)

_MUNGER_SKILL = MasterSkill(
    skill_id="munger",
    name="查理·芒格",
    avatar="🧓",
    title="伯克希尔副董事长",
    description="多元思维模型倡导者",
    system_prompt="我是芒格。原则：多元思维、逆向思考。",
    knowledge_filter="芒格",
    enabled_by_default=True,
)

_DALIO_SKILL = MasterSkill(
    skill_id="dalio",
    name="瑞·达利欧",
    avatar="👴",
    title="桥水基金创始人",
    description="全天候策略倡导者",
    system_prompt="我是达利欧。原则：经济机器、风险平价、周期分析。",
    knowledge_filter="达利欧",
    enabled_by_default=True,
)


# ═══════════════════════════════════════════════════════════════════
# Phase 1: InvestmentAnalysis direction 字段
# ═══════════════════════════════════════════════════════════════════


class TestInvestmentAnalysisDirection:
    """InvestmentAnalysis direction 字段模型验证"""

    def test_default_direction_is_neutral(self):
        """默认 direction 为 Neutral"""
        a = InvestmentAnalysis(
            rating="看涨",
            score=75,
            summary="测试",
            analysis="测试分析",
            key_evidence=[],
        )
        assert a.direction == "Neutral"

    def test_bullish_direction(self):
        """Bullish 方向可通过构造传入"""
        a = InvestmentAnalysis(
            rating="看涨",
            score=80,
            summary="看涨",
            analysis="看多分析",
            key_evidence=[],
            direction="Bullish",
        )
        assert a.direction == "Bullish"

    def test_bearish_direction(self):
        """Bearish 方向可通过构造传入"""
        a = InvestmentAnalysis(
            rating="看跌",
            score=30,
            summary="看跌",
            analysis="看空分析",
            key_evidence=[],
            direction="Bearish",
        )
        assert a.direction == "Bearish"

    def test_invalid_direction_raises_validation_error(self):
        """无效 direction 值应触发 Pydantic 验证错误"""
        with pytest.raises(Exception):
            InvestmentAnalysis(
                rating="中性",
                score=50,
                summary="中性",
                analysis="中性分析",
                direction="InvalidDirection",
            )

    def test_full_analysis_with_direction_in_model_dump(self):
        """direction 在 model_dump 中可见"""
        a = InvestmentAnalysis(
            rating="看涨",
            score=85,
            summary="核心观点",
            analysis="详细分析",
            key_evidence=["证据1", "证据2"],
            risk_warning="注意风险",
            direction="Bullish",
        )
        dumped = a.model_dump()
        assert dumped["direction"] == "Bullish"
        assert dumped["rating"] == "看涨"
        assert dumped["score"] == 85


# ═══════════════════════════════════════════════════════════════════
# Phase 2: AgentAnalysis direction 字段
# ═══════════════════════════════════════════════════════════════════


class TestAgentAnalysisDirection:
    """AgentAnalysis direction 字段"""

    def test_default_direction_is_neutral(self):
        """默认 direction 为 Neutral"""
        a = AgentAnalysis(
            agent_name="test",
            skill_id="test",
            skill_name="测试",
            rating="中性",
            score=50,
            summary="测试摘要",
            analysis="测试分析",
        )
        assert a.direction == "Neutral"

    def test_direction_in_construction(self):
        """构造时指定 direction"""
        a = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看涨",
            analysis="看好",
            direction="Bullish",
        )
        assert a.direction == "Bullish"

    def test_direction_in_model_dump(self):
        """direction 在 model_dump 中可见"""
        a = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看跌",
            score=30,
            summary="看跌",
            analysis="看空",
            direction="Bearish",
        )
        dumped = a.model_dump()
        assert dumped["direction"] == "Bearish"


# ═══════════════════════════════════════════════════════════════════
# Phase 3: VoteSummary direction_distribution
# ═══════════════════════════════════════════════════════════════════


class TestVoteSummaryDirectionDistribution:
    """VoteSummary direction_distribution 字段"""

    def test_default_direction_distribution_empty(self):
        """默认 direction_distribution 为空字典"""
        vs = VoteSummary()
        assert vs.direction_distribution == {}

    def test_direction_distribution_populated(self):
        """方向分布正确填充"""
        vs = VoteSummary(
            total_votes=3,
            rating_distribution={"看涨": 2, "看跌": 1},
            average_score=65.0,
            weighted_score=62.0,
            consensus="看涨",
            confidence=0.7,
            direction_distribution={"Bullish": 2, "Bearish": 1},
        )
        assert vs.direction_distribution["Bullish"] == 2
        assert vs.direction_distribution["Bearish"] == 1
        assert "Neutral" not in vs.direction_distribution

    def test_all_three_directions(self):
        """三种方向均出现时正确计数"""
        vs = VoteSummary(
            total_votes=4,
            rating_distribution={"看涨": 2, "中性": 1, "看跌": 1},
            direction_distribution={"Bullish": 2, "Neutral": 1, "Bearish": 1},
        )
        assert sum(vs.direction_distribution.values()) == 4
        assert vs.direction_distribution["Bullish"] == 2
        assert vs.direction_distribution["Neutral"] == 1
        assert vs.direction_distribution["Bearish"] == 1


# ═══════════════════════════════════════════════════════════════════
# Phase 4: MasterAgent.run() prompt 含方向约束
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentDirectionPrompt:
    """MasterAgent.run() prompt 包含方向约束指令"""

    async def test_direction_constraint_in_prompt_with_knowledge(self):
        """知识命中时，prompt 应包含方向约束指令"""
        agent = MasterAgent(skill=_BUFFETT_SKILL)
        ctx = AgentContext(
            session_id="test-d2",
            input_data={"question": "平安银行值得投资吗？"},
        )
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = InvestmentAnalysis(
                rating="看涨",
                score=75,
                summary="值得投资",
                analysis="银行股估值低",
                key_evidence=["估值低", "利润增长"],
                direction="Bullish",
            )
            # 注入知识
            agent.knowledge_base.chunks = [
                {
                    "text": "平安银行 2025 年净利润增长 5%",
                    "source": "财报.md",
                    "section": "业绩",
                    "type": "data",
                },
            ]
            agent.knowledge_base._rebuild_embeddings()

            await agent.run(ctx)

            call_args, call_kwargs = mock_llm.call_args
            prompt = call_kwargs.get("prompt", call_args[0] if call_args else "")
            assert "direction" in prompt
            assert "Bullish" in prompt
            assert "Bearish" in prompt
            assert "Neutral" in prompt
            assert "强制方向判断" in prompt

    async def test_direction_constraint_in_prompt_without_knowledge(self):
        """无知识命中时，prompt 应包含方向约束指令"""
        agent = MasterAgent(skill=_BUFFETT_SKILL)
        ctx = AgentContext(
            session_id="test-d2-no-kb",
            input_data={"question": "茅台估值如何？"},
        )
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = InvestmentAnalysis(
                rating="看涨",
                score=70,
                summary="茅台确定性高",
                analysis="品牌护城河强",
                key_evidence=[],
                direction="Bullish",
            )
            # 清空知识库确保无命中
            agent.knowledge_base.chunks = []
            agent.knowledge_base._rebuild_embeddings()

            await agent.run(ctx)

            call_args, call_kwargs = mock_llm.call_args
            prompt = call_kwargs.get("prompt", call_args[0] if call_args else "")
            assert "direction" in prompt
            assert "强制方向判断" in prompt

    async def test_direction_in_analysis_output(self):
        """MasterAgent.run() 返回结果中包含 direction"""
        agent = MasterAgent(skill=_BUFFETT_SKILL)
        ctx = AgentContext(
            session_id="test-d2-out",
            input_data={"question": "宁德时代如何？"},
        )
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = InvestmentAnalysis(
                rating="看涨",
                score=82,
                summary="电池龙头",
                analysis="技术领先",
                key_evidence=[],
                direction="Bullish",
            )

            result = await agent.run(ctx)

            assert result.data["analysis"]["direction"] == "Bullish"

    async def test_direction_normalized_in_agent_result(self):
        """direction 值在落盘时被加固"""
        agent = MasterAgent(skill=_BUFFETT_SKILL)
        ctx = AgentContext(
            session_id="test-d2-norm",
            input_data={"question": "测试？"},
        )
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = InvestmentAnalysis(
                rating="中性",
                score=50,
                summary="中性",
                analysis="待观察",
                key_evidence=[],
                direction="Neutral",
            )

            result = await agent.run(ctx)
            assert result.data["analysis"]["direction"] == "Neutral"


# ═══════════════════════════════════════════════════════════════════
# Phase 5: _run_single_master 方向映射
# ═══════════════════════════════════════════════════════════════════


class TestRunSingleMasterDirection:
    """_run_single_master 方向提取与映射"""

    async def test_direction_extracted_from_analysis_raw(self):
        """direction 从 analysis_raw 正确提取到 AgentAnalysis"""
        market_data = {"brief": "市场平稳", "quote": None, "quotes": [], "klines": [], "news": []}

        with patch("src.debate.orchestrator.MasterAgent") as mock_master:
            agent_instance = mock_master.return_value
            agent_instance.run_safe = AsyncMock()
            agent_instance.run_safe.return_value = MagicMock(
                success=True,
                data={
                    "analysis": {
                        "rating": "看涨",
                        "score": 80,
                        "summary": "看好",
                        "analysis": "分析内容",
                        "key_evidence": ["证据1"],
                        "risk_warning": None,
                        "direction": "Bullish",
                    },
                },
                confidence=0.8,
            )

            result = await _run_single_master(
                skill=_BUFFETT_SKILL,
                session_id="test",
                question="测试？",
                stock_code="000001",
                stock_name="平安银行",
                market_data=market_data,
            )

            assert result.direction == "Bullish"

    async def test_invalid_direction_normalized_to_neutral(self):
        """无效 direction 被规范化为 Neutral"""
        market_data = {"brief": "", "quote": None, "quotes": [], "klines": [], "news": []}

        with patch("src.debate.orchestrator.MasterAgent") as mock_master:
            agent_instance = mock_master.return_value
            agent_instance.run_safe = AsyncMock()
            agent_instance.run_safe.return_value = MagicMock(
                success=True,
                data={
                    "analysis": {
                        "rating": "看涨",
                        "score": 70,
                        "summary": "看好",
                        "analysis": "内容",
                        "key_evidence": [],
                        "risk_warning": None,
                        "direction": "INVALID",
                    },
                },
                confidence=0.7,
            )

            result = await _run_single_master(
                skill=_BUFFETT_SKILL,
                session_id="test",
                question="测试？",
                stock_code="000001",
                stock_name="平安银行",
                market_data=market_data,
            )

            assert result.direction == "Neutral"

    async def test_missing_direction_defaults_to_neutral(self):
        """缺失 direction 字段默认 Neutral"""
        market_data = {"brief": "", "quote": None, "quotes": [], "klines": [], "news": []}

        with patch("src.debate.orchestrator.MasterAgent") as mock_master:
            agent_instance = mock_master.return_value
            agent_instance.run_safe = AsyncMock()
            agent_instance.run_safe.return_value = MagicMock(
                success=True,
                data={
                    "analysis": {
                        "rating": "中性",
                        "score": 50,
                        "summary": "中性",
                        "analysis": "内容",
                        "key_evidence": [],
                        "risk_warning": None,
                        # direction 缺失
                    },
                },
                confidence=0.5,
            )

            result = await _run_single_master(
                skill=_BUFFETT_SKILL,
                session_id="test",
                question="测试？",
                stock_code="000001",
                stock_name="平安银行",
                market_data=market_data,
            )

            assert result.direction == "Neutral"

    async def test_failed_analysis_has_neutral_direction(self):
        """分析失败时 direction 为 Neutral"""
        market_data = {"brief": "", "quote": None, "quotes": [], "klines": [], "news": []}

        with patch("src.debate.orchestrator.MasterAgent") as mock_master:
            agent_instance = mock_master.return_value
            agent_instance.run_safe = AsyncMock()
            agent_instance.run_safe.return_value = MagicMock(
                success=False,
                data={},
                error="LLM 调用失败",
                confidence=0.0,
            )

            result = await _run_single_master(
                skill=_BUFFETT_SKILL,
                session_id="test",
                question="测试？",
                stock_code="000001",
                stock_name="平安银行",
                market_data=market_data,
            )

            assert result.direction == "Neutral"
            assert result.success is False


# ═══════════════════════════════════════════════════════════════════
# Phase 6: aggregate_node 方向分布
# ═══════════════════════════════════════════════════════════════════


class TestAggregateDirectionDistribution:
    """aggregate_node 方向分布统计"""

    def _make_analysis(
        self,
        name: str,
        direction: str,
        rating: str = "看涨",
        score: int = 70,
        confidence: float = 0.7,
    ) -> AgentAnalysis:
        """创建带方向的 AgentAnalysis"""
        return AgentAnalysis(
            agent_name=f"master.{name}",
            skill_id=name,
            skill_name=name,
            rating=rating,
            score=score,
            summary="测试",
            analysis="测试分析",
            confidence=confidence,
            direction=direction,
        )

    async def test_mixed_directions(self):
        """混合方向时统计正确"""
        state = {
            "analyses": {
                "master.buffett": self._make_analysis("buffett", "Bullish"),
                "master.munger": self._make_analysis("munger", "Bearish"),
                "master.dalio": self._make_analysis("dalio", "Neutral"),
            },
            "review_round": {},
            "review_report": {},
        }

        result = await aggregate_node(state)
        vs = result["vote_summary"]

        assert vs.direction_distribution == {
            "Bullish": 1,
            "Bearish": 1,
            "Neutral": 1,
        }

    async def test_all_same_direction(self):
        """所有大师同一方向"""
        state = {
            "analyses": {
                "master.buffett": self._make_analysis("buffett", "Bullish"),
                "master.munger": self._make_analysis("munger", "Bullish"),
                "master.dalio": self._make_analysis("dalio", "Bullish"),
            },
            "review_round": {},
            "review_report": {},
        }

        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.direction_distribution["Bullish"] == 3
        assert vs.direction_distribution.get("Bearish", 0) == 0
        assert vs.direction_distribution.get("Neutral", 0) == 0

    async def test_no_analyses_empty_distribution(self):
        """无成功大师时 direction_distribution 为空"""
        state = {
            "analyses": {},
            "review_round": {},
            "review_report": {},
        }

        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.direction_distribution == {}

    async def test_failed_analyses_excluded(self):
        """失败大师不计入方向分布"""
        state = {
            "analyses": {
                "master.buffett": self._make_analysis("buffett", "Bullish"),
                "master.munger": AgentAnalysis(
                    agent_name="master.munger",
                    skill_id="munger",
                    skill_name="芒格",
                    rating="中性",
                    score=0,
                    summary="",
                    analysis="",
                    success=False,
                    direction="Neutral",
                ),
            },
            "review_round": {},
            "review_report": {},
        }

        result = await aggregate_node(state)
        vs = result["vote_summary"]
        assert vs.direction_distribution == {"Bullish": 1}


# ═══════════════════════════════════════════════════════════════════
# Phase 7: DebateResult.to_summary_dict 含方向信息
# ═══════════════════════════════════════════════════════════════════


class TestDebateResultDirectionSummary:
    """DebateResult.to_summary_dict 包含方向信息"""

    def test_summary_contains_direction_distribution(self):
        """to_summary_dict 中方向分布可见"""
        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            analyses=[
                AgentAnalysis(
                    agent_name="master.buffett",
                    skill_id="buffett",
                    skill_name="巴菲特",
                    rating="看涨",
                    score=80,
                    summary="看好",
                    analysis="分析",
                    direction="Bullish",
                ),
            ],
            vote_summary=VoteSummary(
                total_votes=1,
                rating_distribution={"看涨": 1},
                average_score=80.0,
                weighted_score=80.0,
                consensus="看涨",
                confidence=0.7,
                direction_distribution={"Bullish": 1},
            ),
        )

        summary = result.to_summary_dict()
        assert "方向分布" in summary
        assert summary["方向分布"] == {"Bullish": 1}

    def test_summary_no_direction_if_empty(self):
        """无方向分布时方向字段存在但为空"""
        result = DebateResult(
            session_id="test",
            stock_code="000001",
            stock_name="平安银行",
            question="测试",
            analyses=[],
            vote_summary=VoteSummary(),
        )

        summary = result.to_summary_dict()
        assert "方向分布" in summary
        assert summary["方向分布"] == {}


# ═══════════════════════════════════════════════════════════════════
# Phase 8: 全流程集成测试
# ═══════════════════════════════════════════════════════════════════


class TestDirectionFullIntegration:
    """D2 方向约束全流程集成测试（mock LLM 层）"""

    async def test_direction_flows_through_full_pipeline(self):
        """方向值从 LLM → MasterAgent → orchestrator → VoteSummary 完整链路"""
        orchestrator = DebateOrchestrator(
            skill_ids=["buffett", "munger", "dalio"],
        )
        debate_input = DebateInput(
            stock_code="000001",
            stock_name="平安银行",
            question="值得投资吗？",
        )

        # 构建 mock 分析师报告（避免真实 LLM 调用）
        mock_analyst_report = AnalystReport(
            analyst_type="fundamental",
            key_findings=["盈利能力稳健"],
            data_evidence=["ROE 15%"],
            confidence=0.7,
            summary="基本面总体向好",
            score=72,
            direction_hint="Bullish",
        )

        # Mock 数据收集（避免真实网络调用）
        with patch.object(
            orchestrator.data_collector, "get_realtime_quotes", return_value=[]
        ):
            with patch.object(
                orchestrator.data_collector, "get_klines", return_value=[]
            ):
                with patch.object(
                    orchestrator.data_collector, "get_news", return_value=[]
                ):
                    # Mock 分析师层 + LLM 层
                    with (
                        patch(
                            "src.debate.orchestrator._run_single_analyst",
                            new_callable=AsyncMock,
                            return_value=mock_analyst_report,
                        ),
                        patch(
                            "src.utils.llm.llm_service.invoke_structured",
                            new_callable=AsyncMock,
                        ) as mock_llm,
                    ):
                        # 调用顺序：3 大师 × master_round → 3 × review_round → 1 × review_report
                        mock_llm.side_effect = [
                            # master_round: buffett, munger, dalio
                            InvestmentAnalysis(
                                rating="看涨", score=80, summary="看好",
                                analysis="银行股低估", key_evidence=["估值低"],
                                direction="Bullish",
                            ),
                            InvestmentAnalysis(
                                rating="看跌", score=30, summary="看空",
                                analysis="息差收窄", key_evidence=["净息差下降"],
                                direction="Bearish",
                            ),
                            InvestmentAnalysis(
                                rating="中性", score=50, summary="中性",
                                analysis="等待明确信号", key_evidence=[],
                                direction="Neutral",
                            ),
                            # review_round: buffett, munger, dalio
                            RebuttalAnalysis(
                                agent_name="master.buffett",
                                original_agreement=0.6, rebuttal="同意部分",
                                adjusted_score=75,
                            ),
                            RebuttalAnalysis(
                                agent_name="master.munger",
                                original_agreement=0.3, rebuttal="不同意",
                            ),
                            RebuttalAnalysis(
                                agent_name="master.dalio",
                                original_agreement=0.5, rebuttal="中性",
                            ),
                            # review_report
                            IndependentReview(
                                overall_quality=0.7,
                                independent_rating="中性",
                                independent_score=55,
                                confidence=0.6,
                            ),
                        ]

                        result = await orchestrator.run(debate_input)

        # 验证方向分布
        assert result.vote_summary.direction_distribution == {
            "Bullish": 1,
            "Bearish": 1,
            "Neutral": 1,
        }

        # 验证每位大师的 direction
        direction_map = {a.skill_id: a.direction for a in result.analyses if a.success}
        assert direction_map["buffett"] == "Bullish"
        assert direction_map["munger"] == "Bearish"
        assert direction_map["dalio"] == "Neutral"

        # 验证 to_summary_dict 包含方向
        summary = result.to_summary_dict()
        assert "方向分布" in summary
        assert summary["方向分布"] == {"Bullish": 1, "Bearish": 1, "Neutral": 1}

    async def test_direction_survives_serialization_roundtrip(self):
        """direction 在 AgentAnalysis serialization roundtrip 后不变"""
        original = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
            direction="Bullish",
        )

        dumped = original.model_dump()
        restored = AgentAnalysis(**dumped)
        assert restored.direction == "Bullish"

    async def test_history_context_includes_direction(self):
        """历史记忆格式化中包含方向信息"""
        from src.debate.orchestrator import _format_history_context
        from src.memory.store import MemoryItem

        items = [
            MemoryItem(
                key="000001",
                value={
                    "stock_code": "000001",
                    "question": "是否值得？",
                    "consensus": "看涨",
                    "average_score": 75.0,
                    "confidence": 0.7,
                    "total_votes": 3,
                    "timestamp": "2026-06-12T00:00:00",
                    "analyses_summary": [
                        {
                            "skill_name": "巴菲特",
                            "rating": "看涨",
                            "score": 80,
                            "summary": "看好",
                            "direction": "Bullish",
                        },
                    ],
                },
            ),
        ]

        result = _format_history_context(items, "000001")
        assert "Bullish" in result
        assert "[Bullish]" in result or "Bullish" in result


# ═══════════════════════════════════════════════════════════════════
# Phase 9: 向后兼容
# ═══════════════════════════════════════════════════════════════════


class TestDirectionBackwardCompatibility:
    """D2 向后兼容性验证"""

    def test_old_agent_analysis_without_direction(self):
        """旧的 AgentAnalysis（无 direction）构造时默认 Neutral"""
        a = AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=80,
            summary="看好",
            analysis="分析",
        )
        assert a.direction == "Neutral"

    def test_old_vote_summary_without_direction_distribution(self):
        """旧的 VoteSummary（无 direction_distribution）构造时默认为空"""
        vs = VoteSummary(
            total_votes=2,
            rating_distribution={"看涨": 2},
            average_score=75.0,
            weighted_score=72.0,
            consensus="看涨",
            confidence=0.7,
        )
        assert vs.direction_distribution == {}

    async def test_debate_orchestrator_no_knowledge_of_direction(self):
        """orchestrator 的 _run_single_master 在无 direction 时默认 Neutral"""
        market_data = {"brief": "", "quote": None, "quotes": [], "klines": [], "news": []}
        with patch("src.debate.orchestrator.MasterAgent") as mock_master:
            agent_instance = mock_master.return_value
            agent_instance.run_safe = AsyncMock()
            # 模拟不含 direction 的旧版 LLM 输出
            agent_instance.run_safe.return_value = MagicMock(
                success=True,
                data={
                    "analysis": {
                        "rating": "看涨",
                        "score": 75,
                        "summary": "看好",
                        "analysis": "内容",
                        "key_evidence": [],
                        "risk_warning": None,
                    },
                },
                confidence=0.75,
            )

            result = await _run_single_master(
                skill=_BUFFETT_SKILL,
                session_id="test",
                question="测试？",
                stock_code="000001",
                stock_name="平安银行",
                market_data=market_data,
            )
            # 应当兼容处理为 Neutral，不报错
            assert result.direction == "Neutral"

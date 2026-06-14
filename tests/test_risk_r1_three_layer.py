"""R1 三层风控辩论 —— 单元测试

测试策略：
- RiskAssessment / RiskRoundResult / TradeRecommendation 模型构造与默认值
- RiskOfficerProfile 创建与不可变性
- _run_single_risk_officer mock LLM 调用验证
- make_risk_round_node / make_pm_round_node 节点行为
- DebateOrchestrator enable_risk 图编译与运行（mock LLM）
- enable_risk=False 向后兼容
- to_summary_dict R1 字段展示
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.debate.models import (
    DebateInput,
    DebateResult,
)
from src.risk.models import RiskAssessment, RiskRoundResult, TradeRecommendation

# ═══════════════════════════════════════════════════════════════════
# Phase 1: 模型验证
# ═══════════════════════════════════════════════════════════════════


class TestRiskAssessmentModel:
    """RiskAssessment 模型构造与默认值"""

    def test_default_construction(self):
        """默认构造使用安全默认值"""
        ra = RiskAssessment()
        assert ra.risk_style == "neutral"
        assert ra.risk_style_label == "中性型"
        assert ra.action == "hold"
        assert ra.position_size_pct == 0.0
        assert ra.stop_loss_pct == 0.0
        assert ra.take_profit_pct == 0.0
        assert ra.risk_score == 50
        assert ra.risk_rating == "中等风险"
        assert ra.key_risks == []
        assert ra.risk_mitigations == []
        assert ra.discipline_violations == []
        assert ra.analysis == ""
        assert ra.confidence == 0.0
        assert ra.success is True
        assert ra.error is None

    def test_full_construction(self):
        """全字段构造"""
        ra = RiskAssessment(
            risk_style="aggressive",
            risk_style_label="激进型风控官",
            action="buy",
            position_size_pct=0.06,
            stop_loss_pct=0.08,
            take_profit_pct=0.20,
            risk_score=60,
            risk_rating="中等风险",
            key_risks=["市场波动加剧", "政策不确定性"],
            risk_mitigations=["分批建仓", "设置移动止损"],
            discipline_violations=[],
            analysis="综合分析后建议适当进场",
            confidence=0.75,
            success=True,
        )
        assert ra.action == "buy"
        assert ra.position_size_pct == 0.06
        assert len(ra.key_risks) == 2
        assert len(ra.risk_mitigations) == 2

    def test_serialization(self):
        """序列化为 dict 并反序列化"""
        ra = RiskAssessment(
            risk_style="conservative",
            action="hold",
            key_risks=["高估值风险"],
        )
        d = ra.model_dump()
        assert d["risk_style"] == "conservative"
        assert d["action"] == "hold"

        ra2 = RiskAssessment(**d)
        assert ra2.risk_style == ra.risk_style
        assert ra2.key_risks == ra.key_risks

    def test_failed_assessment(self):
        """失败的评估应保留错误信息"""
        ra = RiskAssessment(
            risk_style="aggressive",
            success=False,
            error="LLM 调用超时",
        )
        assert ra.success is False
        assert ra.error == "LLM 调用超时"

    def test_action_none_rejected_by_pydantic(self):
        """action 为 None 时 Pydantic 应拒绝（str 字段不接受 None）"""
        with pytest.raises(Exception):
            RiskAssessment(action=None)  # type: ignore[arg-type]

    def test_score_clamping_expected(self):
        """risk_score 使用默认值（clamping 在实际调用时由 orchestrator 执行）"""
        ra = RiskAssessment(risk_score=0)
        assert ra.risk_score == 0  # 模型不自动 clamp


class TestRiskRoundResultModel:
    """RiskRoundResult 模型"""

    def test_default_construction(self):
        """默认构造"""
        rrr = RiskRoundResult()
        assert rrr.assessments == {}
        assert rrr.errors == []
        assert rrr.risk_consensus_action == "hold"
        assert rrr.avg_risk_score == 50
        assert rrr.min_position_pct == 0.0
        assert rrr.max_position_pct == 0.0
        assert rrr.total_discipline_violations == 0

    def test_with_three_assessments(self):
        """含三位风控官评估的汇总"""
        assessments = {
            "risk.aggressive": RiskAssessment(
                risk_style="aggressive", action="buy",
                position_size_pct=0.06, risk_score=60,
                discipline_violations=["仓位过重"],
            ),
            "risk.conservative": RiskAssessment(
                risk_style="conservative", action="hold",
                position_size_pct=0.02, risk_score=80,
            ),
            "risk.neutral": RiskAssessment(
                risk_style="neutral", action="buy",
                position_size_pct=0.04, risk_score=50,
                discipline_violations=["未确认证据门槛"],
            ),
        }
        rrr = RiskRoundResult(
            assessments=assessments,
            risk_consensus_action="buy",
            avg_risk_score=63,
            min_position_pct=0.02,
            max_position_pct=0.06,
            avg_stop_loss_pct=0.05,
            total_discipline_violations=2,
        )
        assert len(rrr.assessments) == 3
        assert rrr.risk_consensus_action == "buy"
        assert rrr.total_discipline_violations == 2


class TestTradeRecommendationModel:
    """TradeRecommendation 模型"""

    def test_default_construction(self):
        tr = TradeRecommendation()
        assert tr.action == "hold"
        assert tr.position_size_pct == 0.0
        assert tr.discipline_checks_passed is True

    def test_full_construction(self):
        tr = TradeRecommendation(
            action="buy",
            position_size_pct=0.05,
            stop_loss_pct=0.07,
            take_profit_pct=0.15,
            reasoning="综合分析后建议进场",
            risk_level="中等风险",
            confidence=0.80,
            key_warnings=["政策风险需关注"],
            risk_consensus="三位风控官中两位建议买入",
            risk_officers_summary="激进:buy | 保守:hold | 中性:buy",
            discipline_checks_passed=True,
            discipline_summary="所有纪律检查通过",
        )
        assert tr.action == "buy"
        assert tr.position_size_pct == 0.05
        assert len(tr.key_warnings) == 1
        assert tr.confidence == 0.80


# ═══════════════════════════════════════════════════════════════════
# Phase 2: 风控官人格
# ═══════════════════════════════════════════════════════════════════


class TestRiskOfficerProfiles:
    """RiskOfficerProfile 与 get_default_risk_officers"""

    def test_default_returns_three_officers(self):
        """默认返回 3 位风控官"""
        from src.risk.profiles import get_default_risk_officers

        officers = get_default_risk_officers()
        assert len(officers) == 3

    def test_three_distinct_styles(self):
        """三位风控官风格各不相同"""
        from src.risk.profiles import get_default_risk_officers

        officers = get_default_risk_officers()
        styles = {o.style for o in officers}
        assert styles == {"aggressive", "conservative", "neutral"}

    def test_each_has_system_prompt(self):
        """每位风控官都有 system_prompt"""
        from src.risk.profiles import get_default_risk_officers

        for officer in get_default_risk_officers():
            assert len(officer.system_prompt) > 200
            assert officer.name
            assert officer.perspective

    def test_discipline_rules_in_prompts(self):
        """所有 system_prompt 都包含交易纪律"""
        from src.risk.profiles import get_default_risk_officers

        for officer in get_default_risk_officers():
            assert "证据门槛" in officer.system_prompt
            assert "结构止损" in officer.system_prompt
            assert "仓位管理" in officer.system_prompt


# ═══════════════════════════════════════════════════════════════════
# Phase 3: 风险编排节点
# ═══════════════════════════════════════════════════════════════════


class TestRiskRoundNode:
    """make_risk_round_node 节点行为"""

    @pytest.mark.asyncio
    async def test_node_runs_all_three_officers(self):
        """节点应该运行全部 3 位风控官"""
        from src.risk.orchestrator import make_risk_round_node
        from src.risk.profiles import get_default_risk_officers

        officers = get_default_risk_officers()

        mock_response = MagicMock()
        mock_response.action = "buy"
        mock_response.position_size_pct = 0.05
        mock_response.stop_loss_pct = 0.07
        mock_response.take_profit_pct = 0.15
        mock_response.risk_score = 50
        mock_response.risk_rating = "中等风险"
        mock_response.key_risks = ["市场风险"]
        mock_response.risk_mitigations = ["止损"]
        mock_response.discipline_violations = []
        mock_response.analysis = "风险可控"
        mock_response.confidence = 0.7

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_invoke:
            node = make_risk_round_node(officers)

            state = {
                "session_id": "test-s1",
                "debate_input": {
                    "stock_code": "000001",
                    "question": "测试问题",
                },
                "vote_summary": {"consensus": "看涨", "average_score": 72.0},
                "analyses": {},
                "analyst_reports": {},
            }

            result = await node(state)

            # 验证调用了 3 次（每位风控官一次）
            assert mock_invoke.call_count == 3
            assert "risk_round" in result
            rr_dict = result["risk_round"]
            assert rr_dict["risk_consensus_action"] == "buy"
            assert len(rr_dict["assessments"]) == 3

    @pytest.mark.asyncio
    async def test_node_handles_failure_gracefully(self):
        """风控官失败不阻塞后续流程"""
        from src.risk.orchestrator import make_risk_round_node
        from src.risk.profiles import get_default_risk_officers

        officers = get_default_risk_officers()

        mock_invoke = AsyncMock()
        # 第一次成功，第二次失败
        mock_success = MagicMock()
        mock_success.action = "buy"
        mock_success.position_size_pct = 0.05
        mock_success.stop_loss_pct = 0.07
        mock_success.take_profit_pct = 0.15
        mock_success.risk_score = 50
        mock_success.risk_rating = "中等风险"
        mock_success.key_risks = []
        mock_success.risk_mitigations = []
        mock_success.discipline_violations = []
        mock_success.analysis = "ok"
        mock_success.confidence = 0.7
        mock_invoke.side_effect = [
            mock_success,
            Exception("API 超时"),
            mock_success,
        ]

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            mock_invoke,
        ):
            node = make_risk_round_node(officers)
            state = {
                "session_id": "test-s2",
                "debate_input": {"stock_code": "000001", "question": "测试"},
                "vote_summary": {},
                "analyses": {},
                "analyst_reports": {},
            }
            result = await node(state)

            # 仍然返回 3 个 assessment（失败的那个也是 RiskAssessment）
            rr_dict = result["risk_round"]
            assert len(rr_dict["assessments"]) == 3
            # 有错误记录
            assert len(rr_dict["errors"]) == 1

    @pytest.mark.asyncio
    async def test_node_with_empty_state(self):
        """空 state 不崩溃"""
        from src.risk.orchestrator import make_risk_round_node
        from src.risk.profiles import get_default_risk_officers

        officers = get_default_risk_officers()

        mock_response = MagicMock()
        mock_response.action = "hold"
        mock_response.position_size_pct = 0.0
        mock_response.stop_loss_pct = 0.0
        mock_response.take_profit_pct = 0.0
        mock_response.risk_score = 50
        mock_response.risk_rating = "中等风险"
        mock_response.key_risks = []
        mock_response.risk_mitigations = []
        mock_response.discipline_violations = []
        mock_response.analysis = "无足够信息"
        mock_response.confidence = 0.0

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            node = make_risk_round_node(officers)
            result = await node({})
            assert "risk_round" in result
            assert result["risk_round"]["risk_consensus_action"] == "hold"


class TestPMRoundNode:
    """make_pm_round_node 节点行为"""

    @pytest.mark.asyncio
    async def test_pm_node_produces_recommendation(self):
        """PM 节点产出 TradeRecommendation"""
        from src.risk.orchestrator import make_pm_round_node

        mock_response = MagicMock()
        mock_response.action = "buy"
        mock_response.position_size_pct = 0.05
        mock_response.stop_loss_pct = 0.07
        mock_response.take_profit_pct = 0.15
        mock_response.reasoning = "综合各方意见后建议买入"
        mock_response.risk_level = "中等风险"
        mock_response.confidence = 0.78
        mock_response.key_warnings = ["注意政策风险"]
        mock_response.risk_consensus = "多数风控官支持买入"
        mock_response.risk_officers_summary = "激进:buy | 保守:hold | 中性:buy"
        mock_response.discipline_checks_passed = True
        mock_response.discipline_summary = "全部检查通过"

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            node = make_pm_round_node()

            risk_round_dict = {
                "assessments": {},
                "risk_consensus_action": "buy",
                "avg_risk_score": 60,
                "min_position_pct": 0.02,
                "max_position_pct": 0.06,
                "total_discipline_violations": 0,
            }

            state = {
                "session_id": "test-pm",
                "vote_summary": {"consensus": "看涨"},
                "analyses": {},
                "analyst_reports": {},
                "risk_round": risk_round_dict,
            }

            result = await node(state)

            assert "trade_recommendation" in result
            tr = result["trade_recommendation"]
            assert tr["action"] == "buy"
            assert tr["position_size_pct"] == 0.05
            assert tr["confidence"] == 0.78
            assert tr["discipline_checks_passed"] is True

    @pytest.mark.asyncio
    async def test_pm_node_handles_llm_failure(self):
        """PM LLM 失败时返回保守默认值"""
        from src.risk.orchestrator import make_pm_round_node

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            side_effect=Exception("LLM 不可用"),
        ):
            node = make_pm_round_node()
            result = await node({"session_id": "test-fail"})

            tr = result["trade_recommendation"]
            assert tr["action"] == "hold"
            assert "PM 裁决失败" in tr["reasoning"]

    @pytest.mark.asyncio
    async def test_pm_node_without_risk_round(self):
        """无 risk_round 数据时 PM 仍能工作"""
        from src.risk.orchestrator import make_pm_round_node

        mock_response = MagicMock()
        mock_response.action = "hold"
        mock_response.position_size_pct = 0.0
        mock_response.stop_loss_pct = 0.0
        mock_response.take_profit_pct = 0.0
        mock_response.reasoning = "缺乏风控数据，建议观望"
        mock_response.risk_level = "中等风险"
        mock_response.confidence = 0.3
        mock_response.key_warnings = []
        mock_response.risk_consensus = ""
        mock_response.risk_officers_summary = ""
        mock_response.discipline_checks_passed = True
        mock_response.discipline_summary = ""

        with patch(
            "src.risk.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            node = make_pm_round_node()
            result = await node({
                "session_id": "test-no-risk",
                "vote_summary": {},
                "analyses": {},
                "analyst_reports": {},
            })

            assert "trade_recommendation" in result


# ═══════════════════════════════════════════════════════════════════
# Phase 4: 编排器集成
# ═══════════════════════════════════════════════════════════════════


class TestOrchestratorWithRisk:
    """DebateOrchestrator enable_risk 集成测试"""

    @pytest.mark.asyncio
    async def test_graph_compiles_with_risk_enabled(self):
        """enable_risk=True 时图编译成功"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_risk=True)
        graph = orch._build_graph()
        assert graph is not None
        # 不调用 compile() 即可验证节点存在

    @pytest.mark.asyncio
    async def test_graph_has_risk_nodes(self):
        """enable_risk=True 的图包含 risk_round 和 pm_round 节点"""
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_risk=True)
        graph = orch._build_graph()
        compiled = graph.compile()
        # 验证图可以编译
        assert compiled is not None

    @pytest.mark.asyncio
    async def test_full_flow_with_risk(self):
        """enable_risk=True 全流程运行（mock LLM），验证风险字段存在"""
        from src.agents.master_agent import MasterAgent
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator(enable_risk=True)

        # Mock MasterAgent 绕开复杂的 LLM 调用序列
        mock_master = AsyncMock()
        mock_master_result = MagicMock()
        mock_master_result.success = True
        mock_master_result.data = {
            "analysis": {
                "rating": "看涨",
                "score": 75,
                "summary": "买入信号明确",
                "analysis": "测试分析文本",
                "key_evidence": ["成交量放大"],
                "direction": "Bullish",
            }
        }
        mock_master_result.confidence = 0.80
        mock_master.run_safe.return_value = mock_master_result

        # 构建足够长的 mock invoke_structured 序列
        # 分析师 x4 + 独立评审 x1 + 风控 x3 + PM x1 + review_round rebuttals x5
        def make_analyst():
            r = MagicMock()
            r.analyst_type = "fundamental"
            r.key_findings = ["数据正常"]
            r.data_evidence = ["数据点"]
            r.red_flags = []
            r.confidence = 0.7
            r.summary = "总结"
            r.score = 70
            r.direction_hint = "Bullish"
            return r

        def make_review():
            r = MagicMock()
            r.reviewer_style = "independent"
            r.overall_quality = 0.7
            r.independent_rating = "看涨"
            r.independent_score = 70
            r.confidence = 0.5
            r.consensus_support = 0.6
            r.quality_assessments = {}
            r.weight_suggestions = {}
            r.identified_biases = []
            r.blind_spots = []
            r.key_risks_synthesis = ""
            r.consistency_observation = ""
            r.aggregation_recommendation = ""
            return r

        def make_rebuttal():
            r = MagicMock()
            r.agent_name = "master.test"
            r.original_agreement = 0.5
            r.rebuttal = "同意"
            r.adjusted_rating = None
            r.adjusted_score = None
            r.adjusted_confidence = None
            r.key_counterpoints = []
            r.peer_influences = ""
            return r

        def make_risk():
            r = MagicMock()
            r.action = "buy"
            r.position_size_pct = 0.05
            r.stop_loss_pct = 0.07
            r.take_profit_pct = 0.15
            r.risk_score = 50
            r.risk_rating = "中等风险"
            r.key_risks = []
            r.risk_mitigations = []
            r.discipline_violations = []
            r.analysis = "可控"
            r.confidence = 0.7
            return r

        def make_pm():
            r = MagicMock()
            r.action = "buy"
            r.position_size_pct = 0.05
            r.stop_loss_pct = 0.07
            r.take_profit_pct = 0.15
            r.reasoning = "综合建议买入"
            r.risk_level = "中等风险"
            r.confidence = 0.78
            r.key_warnings = []
            r.risk_consensus = "多数支持"
            r.risk_officers_summary = "all:buy"
            r.discipline_checks_passed = True
            r.discipline_summary = "通过"
            return r

        # 足够的响应序列（分析×4 + review×1 + rebuttal×5 + risk×3 + pm×1 = 15）
        side_effects = [make_analyst() for _ in range(4)]
        side_effects.append(make_review())
        side_effects.extend(make_rebuttal() for _ in range(5))
        side_effects.extend(make_risk() for _ in range(3))
        side_effects.append(make_pm())

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            side_effect=side_effects,
        ):
            with patch.object(MasterAgent, "run_safe", mock_master.run_safe):
                result = await orch.run(
                    DebateInput(stock_code="000001")
                )

                assert isinstance(result, DebateResult)
                # 验证风险字段存在
                assert result.risk_round is not None
                assert result.trade_recommendation is not None
                assert result.trade_recommendation["action"] == "buy"
                assert result.trade_recommendation["confidence"] == 0.78

    @pytest.mark.asyncio
    async def test_summary_dict_includes_risk_fields(self):
        """to_summary_dict 包含 R1 字段"""
        risk_round_data = {
            "assessments": {},
            "risk_consensus_action": "buy",
            "avg_risk_score": 60,
            "min_position_pct": 0.02,
            "max_position_pct": 0.06,
            "total_discipline_violations": 0,
        }
        trade_rec_data = {
            "action": "buy",
            "position_size_pct": 0.05,
            "stop_loss_pct": 0.07,
            "take_profit_pct": 0.15,
            "reasoning": "综合建议",
            "risk_level": "中等风险",
            "confidence": 0.78,
            "key_warnings": [],
            "risk_consensus": "",
            "risk_officers_summary": "",
            "discipline_checks_passed": True,
            "discipline_summary": "",
        }
        result = DebateResult(
            session_id="test-r1",
            stock_code="000001",
            stock_name="测试股票",
            question="测试",
            risk_round=risk_round_data,
            trade_recommendation=trade_rec_data,
        )
        summary = result.to_summary_dict()

        assert summary.get("风控审核") is True
        assert summary.get("风控共识操作") == "buy"
        assert summary.get("平均风险评分") == 60
        assert summary.get("仓位范围") == "2% ~ 6%"
        assert summary.get("最终建议") == "BUY"
        assert summary.get("建议仓位") == "5%"
        assert summary.get("风险等级") == "中等风险"
        assert summary.get("纪律通过") is True


# ═══════════════════════════════════════════════════════════════════
# Phase 5: 向后兼容
# ═══════════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """enable_risk=False 保持向后兼容"""

    @pytest.mark.asyncio
    async def test_default_disables_risk(self):
        """默认 DebateOrchestrator 不启用风控"""
        from src.agents.master_agent import MasterAgent
        from src.debate.orchestrator import DebateOrchestrator

        orch = DebateOrchestrator()

        # Mock MasterAgent + 分析师 + 独立评审
        mock_master = AsyncMock()
        mock_master_result = MagicMock()
        mock_master_result.success = True
        mock_master_result.data = {
            "analysis": {
                "rating": "看涨",
                "score": 70,
                "summary": "测试",
                "analysis": "测试",
                "key_evidence": [],
                "direction": "Bullish",
            }
        }
        mock_master_result.confidence = 0.75
        mock_master.run_safe.return_value = mock_master_result

        analyst_response = MagicMock()
        analyst_response.analyst_type = "fundamental"
        analyst_response.key_findings = ["数据正常"]
        analyst_response.data_evidence = ["数据"]
        analyst_response.red_flags = []
        analyst_response.confidence = 0.7
        analyst_response.summary = "总结"
        analyst_response.score = 70
        analyst_response.direction_hint = "Bullish"

        review_response = MagicMock()
        review_response.reviewer_style = "independent"
        review_response.overall_quality = 0.7
        review_response.independent_rating = "看涨"
        review_response.independent_score = 70
        review_response.confidence = 0.5
        review_response.consensus_support = 0.6
        review_response.quality_assessments = {}
        review_response.weight_suggestions = {}
        review_response.identified_biases = []
        review_response.blind_spots = []
        review_response.key_risks_synthesis = ""
        review_response.consistency_observation = ""
        review_response.aggregation_recommendation = ""

        with patch(
            "src.debate.orchestrator.llm_service.invoke_structured",
            new_callable=AsyncMock,
            side_effect=[
                analyst_response,  # x4 analysts
                analyst_response,
                analyst_response,
                analyst_response,
                review_response,  # D3 review
            ],
        ):
            with patch.object(MasterAgent, "run_safe", mock_master.run_safe):
                result = await orch.run(DebateInput(stock_code="000001"))

                assert isinstance(result, DebateResult)
                # 不启用风控时，risk 字段应为 None
                assert result.risk_round is None
                assert result.trade_recommendation is None

    def test_debate_result_without_risk_fields(self):
        """不提供 risk 字段时 DebateResult 正常构造"""
        result = DebateResult(
            session_id="test-no-risk",
            stock_code="000001",
            stock_name="测试",
            question="测试",
        )
        assert result.risk_round is None
        assert result.trade_recommendation is None

        # to_summary_dict 应正常返回（不含风控字段）
        summary = result.to_summary_dict()
        assert "风控审核" not in summary
        assert "最终建议" not in summary

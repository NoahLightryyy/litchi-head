"""M2 交易后反思测试

测试策略：
- ReflectionRecord / ActualOutcome 模型验证
- _format_reflection_context 格式化逻辑（空列表/不相关/相关/多条）
- generate_reflection（mock LLM）
- reflect_on_decision 集成（mock MemoryStore + LLM 层）
- DebateOrchestrator enable_reflection 反思注入
- MemoryStore / LLM 失败不阻塞流程
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.debate.orchestrator import DebateOrchestrator
from src.debate.reflection import (
    ActualOutcome,
    ReflectionRecord,
    _format_reflection_context,
    _load_decision_from_memory,
    generate_reflection,
)
from src.memory.store import MemoryItem, MemoryStore

# ═══════════════════════════════════════════════════════════════════
# Phase 1: 模型验证
# ═══════════════════════════════════════════════════════════════════


class TestActualOutcomeModel:
    """ActualOutcome 模型验证"""

    def test_minimal_construction(self):
        """最小字段构造"""
        outcome = ActualOutcome(stock_code="000001")
        assert outcome.stock_code == "000001"
        assert outcome.actual_direction == "Neutral"
        assert outcome.price_change_pct == 0.0

    def test_full_construction(self):
        """全字段构造"""
        outcome = ActualOutcome(
            stock_code="000001",
            decision_date="2026-06-10",
            evaluation_date="2026-06-14",
            price_change_pct=+3.5,
            actual_direction="Bullish",
            holding_period_days=3,
            notes="期间无重大利空",
        )
        assert outcome.stock_code == "000001"
        assert outcome.price_change_pct == 3.5
        assert outcome.actual_direction == "Bullish"
        assert outcome.holding_period_days == 3

    def test_defaults_are_sensible(self):
        """默认值合理"""
        outcome = ActualOutcome(stock_code="600519")
        assert outcome.decision_date == ""
        assert outcome.price_change_pct == 0.0


class TestReflectionRecordModel:
    """ReflectionRecord 模型验证"""

    def test_minimal_construction(self):
        """最小字段构造"""
        record = ReflectionRecord(
            session_id="sess-001",
            stock_code="000001",
        )
        assert record.session_id == "sess-001"
        assert record.stock_code == "000001"
        assert record.was_correct is False
        assert record.key_lessons == []

    def test_full_construction(self):
        """全字段构造"""
        record = ReflectionRecord(
            session_id="sess-001",
            stock_code="000001",
            stock_name="平安银行",
            decision_date="2026-06-10",
            evaluation_date="2026-06-14",
            predicted_direction="Bullish",
            predicted_consensus="看涨",
            predicted_action="buy",
            predicted_score=75.0,
            predicted_confidence=0.85,
            actual_direction="Bullish",
            actual_price_change_pct=+3.5,
            was_correct=True,
            accuracy_score=0.8,
            reflection_text="方向正确但入场时机偏早",
            key_lessons=["等待确认信号再入场", "关注大盘走势"],
            improvement_suggestions=["增加技术指标确认"],
            identified_biases=["过度乐观"],
            latency_ms=1200.0,
        )
        assert record.was_correct is True
        assert record.accuracy_score == 0.8
        assert len(record.key_lessons) == 2
        assert len(record.improvement_suggestions) == 1

    def test_model_dump_serializable(self):
        """model_dump 可序列化（用于 MemoryStore 存储）"""
        record = ReflectionRecord(
            session_id="sess-001",
            stock_code="000001",
            key_lessons=["教训1"],
        )
        dumped = record.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["session_id"] == "sess-001"
        assert dumped["key_lessons"] == ["教训1"]


# ═══════════════════════════════════════════════════════════════════
# Phase 2: _format_reflection_context 格式化逻辑
# ═══════════════════════════════════════════════════════════════════


class TestFormatReflectionContext:
    """_format_reflection_context 格式化函数验证"""

    def test_empty_items(self):
        """空列表返回空字符串"""
        result = _format_reflection_context([], "000001")
        assert result == ""

    def test_no_relevant_items(self):
        """没有匹配股票代码的反思时返回空字符串"""
        items = [
            MemoryItem(
                key="600519_ref_1",
                value={
                    "stock_code": "600519",
                    "reflection_text": "判断正确",
                },
            ),
        ]
        result = _format_reflection_context(items, "000001")
        assert result == ""

    def test_single_relevant_reflection(self):
        """一条匹配的反思应输出格式化文本"""
        items = [
            MemoryItem(
                key="000001_ref_1",
                value={
                    "stock_code": "000001",
                    "decision_date": "2026-06-10",
                    "evaluation_date": "2026-06-14",
                    "predicted_direction": "Bullish",
                    "actual_direction": "Bullish",
                    "actual_price_change_pct": +3.5,
                    "was_correct": True,
                    "predicted_score": 75,
                    "predicted_confidence": 0.85,
                    "accuracy_score": 0.8,
                    "reflection_text": "方向正确但入场时机偏早，下次应等待确认信号。",
                    "key_lessons": ["等待确认信号", "关注大盘"],
                    "improvement_suggestions": ["增加技术指标确认"],
                },
            ),
        ]
        result = _format_reflection_context(items, "000001")
        assert "历史反思记录" in result
        assert "Bullish" in result
        assert "方向正确" in result
        assert "等待确认信号" in result
        assert "增加技术指标确认" in result
        assert "✅" in result  # was_correct
        assert "📌 关键教训" in result
        assert "💡 改进建议" in result

    def test_multiple_reflections_takes_latest_3(self):
        """多条反思取最近 3 条"""
        items = []
        for i in range(5):
            items.append(MemoryItem(
                key=f"000001_ref_{i}",
                value={
                    "stock_code": "000001",
                    "decision_date": f"2026-06-{10+i:02d}",
                    "evaluation_date": f"2026-06-{14+i:02d}",
                    "predicted_direction": "Neutral",
                    "actual_direction": "Neutral",
                    "actual_price_change_pct": 0.0,
                    "was_correct": True,
                    "predicted_score": 50,
                    "predicted_confidence": 0.5,
                    "accuracy_score": 0.5,
                    "reflection_text": f"反思内容 #{i}",
                },
            ))
        result = _format_reflection_context(items, "000001")
        # 应包含最近 3 条（#2, #3, #4）
        assert result.count("反思 #") == 3
        assert "反思 #3" in result


# ═══════════════════════════════════════════════════════════════════
# Phase 3: generate_reflection (mock LLM)
# ═══════════════════════════════════════════════════════════════════


class TestGenerateReflection:
    """generate_reflection 函数验证"""

    @pytest.fixture
    def decision_summary(self) -> dict:
        return {
            "股票代码": "000001",
            "股票名称": "平安银行",
            "共识": "看涨",
            "平均评分": 72.5,
            "加权评分": 68.3,
            "置信度": 0.78,
            "方向分布": {"Bullish": 3, "Bearish": 1, "Neutral": 1},
            "最终建议": "BUY",
            "建议仓位": "15%",
            "止损位": "8%",
        }

    @pytest.fixture
    def outcome(self) -> ActualOutcome:
        return ActualOutcome(
            stock_code="000001",
            decision_date="2026-06-10",
            evaluation_date="2026-06-14",
            price_change_pct=+3.5,
            actual_direction="Bullish",
            holding_period_days=3,
            notes="大盘同期 +1.2%",
        )

    @pytest.mark.asyncio
    async def test_generate_success(self, decision_summary, outcome):
        """LLM 返回正确反思结果"""
        mock_reflection = ReflectionRecord(
            session_id="",
            stock_code="000001",
            stock_name="平安银行",
            decision_date="2026-06-10",
            evaluation_date="2026-06-14",
            predicted_direction="Bullish",
            predicted_consensus="看涨",
            predicted_action="buy",
            predicted_score=72.5,
            predicted_confidence=0.78,
            actual_direction="Bullish",
            actual_price_change_pct=3.5,
            was_correct=True,
            accuracy_score=0.8,
            reflection_text="方向正确，仓位偏保守",
            key_lessons=["可适度提高仓位"],
            improvement_suggestions=["关注量能"],
            identified_biases=["保守倾向"],
            latency_ms=0,
        )

        with patch("src.debate.reflection.llm_service.invoke_structured") as mock_invoke:
            mock_invoke.return_value = mock_reflection

            result = await generate_reflection(
                decision_summary=decision_summary,
                outcome=outcome,
                session_id="sess-test",
            )

        assert result.session_id == "sess-test"
        assert result.stock_code == "000001"
        assert result.was_correct is True
        assert result.accuracy_score == 0.8
        assert len(result.key_lessons) == 1
        assert result.actual_direction == "Bullish"
        assert result.actual_price_change_pct == 3.5

    @pytest.mark.asyncio
    async def test_generate_wrong_prediction(self, decision_summary, outcome):
        """方向预测错误时应正确返回"""
        outcome.price_change_pct = -5.0
        outcome.actual_direction = "Bearish"

        mock_reflection = ReflectionRecord(
            session_id="",
            stock_code="000001",
            was_correct=False,
            accuracy_score=0.2,
            reflection_text="完全判断错误",
            key_lessons=["忽视了下行风险"],
        )

        with patch("src.debate.reflection.llm_service.invoke_structured") as mock_invoke:
            mock_invoke.return_value = mock_reflection

            result = await generate_reflection(
                decision_summary=decision_summary,
                outcome=outcome,
            )

        assert result.was_correct is False
        assert result.actual_price_change_pct == -5.0
        assert "完全判断错误" in result.reflection_text

    @pytest.mark.asyncio
    async def test_generate_llm_failure_returns_default(self, decision_summary, outcome):
        """LLM 调用失败返回默认记录（不抛异常）"""
        with patch("src.debate.reflection.llm_service.invoke_structured") as mock_invoke:
            mock_invoke.side_effect = RuntimeError("LLM unavailable")

            result = await generate_reflection(
                decision_summary=decision_summary,
                outcome=outcome,
            )

        assert result.stock_code == "000001"
        assert result.reflection_text != ""
        assert "失败" in result.reflection_text


# ═══════════════════════════════════════════════════════════════════
# Phase 4: _load_decision_from_memory
# ═══════════════════════════════════════════════════════════════════


class TestLoadDecisionFromMemory:
    """_load_decision_from_memory 函数验证"""

    @pytest.mark.asyncio
    async def test_load_existing_decision(self):
        """加载存在的决策"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="000001",
            value={"stock_code": "000001", "consensus": "看涨"},
        )

        result = await _load_decision_from_memory(mock_store, "000001")
        assert result is not None
        assert result["stock_code"] == "000001"
        assert result["consensus"] == "看涨"

    @pytest.mark.asyncio
    async def test_load_nonexistent_decision(self):
        """加载不存在的决策返回 None"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None

        result = await _load_decision_from_memory(mock_store, "000001")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_store_error_returns_none(self):
        """MemoryStore 异常返回 None（不抛异常）"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.side_effect = OSError("disk full")

        result = await _load_decision_from_memory(mock_store, "000001")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Phase 5: reflect_on_decision 集成
# ═══════════════════════════════════════════════════════════════════


class TestReflectOnDecision:
    """DebateOrchestrator.reflect_on_decision 集成测试"""

    @pytest.mark.asyncio
    async def test_reflect_no_memory_store(self):
        """无 memory_store 时返回 None"""
        orch = DebateOrchestrator(memory_store=None)
        outcome = ActualOutcome(stock_code="000001")
        result = await orch.reflect_on_decision("000001", outcome)
        assert result is None

    @pytest.mark.asyncio
    async def test_reflect_no_decision_found(self):
        """无历史决策时返回 None"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = None

        orch = DebateOrchestrator(memory_store=mock_store)
        outcome = ActualOutcome(stock_code="000001")
        result = await orch.reflect_on_decision("000001", outcome)
        assert result is None

    @pytest.mark.asyncio
    async def test_reflect_success(self):
        """完整反思流程成功"""
        mock_store = AsyncMock(spec=MemoryStore)
        # 模拟存在的历史决策
        mock_store.get.return_value = MemoryItem(
            key="000001",
            value={
                "stock_code": "000001",
                "stock_name": "平安银行",
                "consensus": "看涨",
                "average_score": 72.5,
                "confidence": 0.78,
                "total_votes": 5,
            },
        )

        mock_reflection = ReflectionRecord(
            session_id="",
            stock_code="000001",
            was_correct=True,
            accuracy_score=0.75,
            reflection_text="方向正确",
            key_lessons=["注意止损"],
        )

        orch = DebateOrchestrator(memory_store=mock_store)
        outcome = ActualOutcome(
            stock_code="000001",
            price_change_pct=+2.0,
            actual_direction="Bullish",
        )

        with patch("src.debate.reflection.llm_service.invoke_structured") as mock_invoke:
            mock_invoke.return_value = mock_reflection

            result = await orch.reflect_on_decision("000001", outcome)

        assert result is not None
        assert result.stock_code == "000001"
        # 验证反思保存到了 memory_store
        mock_store.put.assert_called_once()
        call_args = mock_store.put.call_args
        assert call_args.kwargs["namespace"] == ("reflective", "debate")

    @pytest.mark.asyncio
    async def test_reflect_save_failure_not_blocking(self):
        """MemoryStore 保存失败不阻塞反思返回"""
        mock_store = AsyncMock(spec=MemoryStore)
        mock_store.get.return_value = MemoryItem(
            key="000001",
            value={"stock_code": "000001", "consensus": "看涨"},
        )
        mock_store.put.side_effect = OSError("disk full")

        mock_reflection = ReflectionRecord(
            session_id="",
            stock_code="000001",
            was_correct=True,
            reflection_text="ok",
        )

        orch = DebateOrchestrator(memory_store=mock_store)
        outcome = ActualOutcome(stock_code="000001")

        with patch("src.debate.reflection.llm_service.invoke_structured") as mock_invoke:
            mock_invoke.return_value = mock_reflection

            result = await orch.reflect_on_decision("000001", outcome)

        # 即使保存失败，反思仍应返回
        assert result is not None
        assert result.reflection_text == "ok"


# ═══════════════════════════════════════════════════════════════════
# Phase 6: enable_reflection 编排器集成
# ═══════════════════════════════════════════════════════════════════


class TestEnableReflectionInOrchestrator:
    """DebateOrchestrator enable_reflection 编排器集成"""

    def test_default_disable(self):
        """默认 enable_reflection=False"""
        orch = DebateOrchestrator()
        assert orch.enable_reflection is False

    def test_enable_reflection_flag(self):
        """启用 enable_reflection"""
        mock_store = AsyncMock(spec=MemoryStore)
        orch = DebateOrchestrator(
            memory_store=mock_store,
            enable_reflection=True,
        )
        assert orch.enable_reflection is True

    @pytest.mark.asyncio
    async def test_reflection_injected_in_run(self):
        """启用 enable_reflection 时 reflection_context 应被注入到 state"""
        mock_store = AsyncMock(spec=MemoryStore)
        # 模拟历史决策查询（M1）
        mock_store.search.return_value = []

        # 模拟反思查询（M2）
        # 先返回空给 M1 history 查询，后返回反思数据
        mock_store.search.side_effect = [
            [],  # M1 history
            [   # M2 reflection
                MemoryItem(
                    key="000001_ref_1",
                    value={
                        "stock_code": "000001",
                        "decision_date": "2026-06-10",
                        "evaluation_date": "2026-06-14",
                        "predicted_direction": "Bullish",
                        "actual_direction": "Bearish",
                        "actual_price_change_pct": -4.0,
                        "was_correct": False,
                        "predicted_score": 70,
                        "predicted_confidence": 0.8,
                        "accuracy_score": 0.1,
                        "reflection_text": "完全看反了",
                        "key_lessons": ["风险意识不足"],
                        "improvement_suggestions": ["增加风控力度"],
                    },
                ),
            ],
        ]

        from src.debate.models import DebateInput

        orch = DebateOrchestrator(
            memory_store=mock_store,
            enable_reflection=True,
        )

        # 创建一个修改过的 _build_graph 来短路执行
        # （不做完整 9 层链路，只验证 state 中的 reflection_context）
        original_build = orch._build_graph
        def mock_build():
            from langgraph.graph import END, StateGraph

            from src.debate.orchestrator import DebateState
            g = StateGraph(DebateState)
            g.add_node("check", lambda s: {})
            g.set_entry_point("check")
            g.add_edge("check", END)
            return g
        orch._build_graph = mock_build

        try:
            await orch.run(DebateInput(
                stock_code="000001",
                stock_name="平安银行",
                question="是否值得投资？",
            ))

            # 验证 search 被调用了两次
            # (一次 M1 history, 一次 M2 reflection)
            assert mock_store.search.call_count == 2

            # 验证第二次调用的是 ("reflective", "debate")
            second_call = mock_store.search.call_args_list[1]
            assert second_call.kwargs["namespace"] == ("reflective", "debate")
        finally:
            orch._build_graph = original_build


# ═══════════════════════════════════════════════════════════════════
# Phase 7: 边界与容错
# ═══════════════════════════════════════════════════════════════════


class TestFailureTolerance:
    """反思相关操作的容错性"""

    @pytest.mark.asyncio
    async def test_format_reflection_non_dict_value(self):
        """MemoryItem.value 不是 dict 时不崩溃"""
        items = [
            MemoryItem(
                key="000001_ref_1",
                value="this is a string, not a dict",
            ),
        ]
        result = _format_reflection_context(items, "000001")
        assert result == ""  # 过滤掉非 dict 值

    @pytest.mark.asyncio
    async def test_format_reflection_partial_fields(self):
        """Reflection 只有部分字段时仍可格式化"""
        items = [
            MemoryItem(
                key="000001_ref_1",
                value={
                    "stock_code": "000001",
                    # 缺少大多数字段
                },
            ),
        ]
        result = _format_reflection_context(items, "000001")
        assert "历史反思记录" in result  # 至少能格式化

    @pytest.mark.asyncio
    async def test_reflection_search_failure_not_blocking(self):
        """反思查询失败不阻塞辩论流程"""
        mock_store = AsyncMock(spec=MemoryStore)
        # M1 history 成功，M2 reflection 失败
        mock_store.search.side_effect = [
            [],  # M1 ok
            RuntimeError("reflective namespace corrupted"),  # M2 fail
        ]

        from src.debate.models import DebateInput

        orch = DebateOrchestrator(
            memory_store=mock_store,
            enable_reflection=True,
        )

        # 短路图
        original_build = orch._build_graph
        def mock_build():
            from langgraph.graph import END, StateGraph

            from src.debate.orchestrator import DebateState
            g = StateGraph(DebateState)
            g.add_node("check", lambda s: {})
            g.set_entry_point("check")
            g.add_edge("check", END)
            return g
        orch._build_graph = mock_build

        try:
            result = await orch.run(DebateInput(
                stock_code="000001",
                question="测试",
            ))
            # 不应抛异常
            assert result is not None
        finally:
            orch._build_graph = original_build

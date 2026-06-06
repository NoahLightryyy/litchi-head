"""冒烟测试 —— 验证测试基座 (conftest.py) 正常工作

此文件验证：
1. 项目核心模块可以正常导入
2. conftest 中的 mock 工具函数可用
3. 共享 fixtures 正常创建
"""

from unittest.mock import AsyncMock

import pytest

from src.agents.base import AgentContext
from src.core.protocol import AgentMessage
from src.utils.logger import AgentLogger
from tests.conftest import make_mock_llm_error, make_mock_llm_sequence, make_mock_llm_service

# ═══════════════════════════════════════════════════════════════════
# 基础导入测试
# ═══════════════════════════════════════════════════════════════════


class TestImports:
    """验证项目核心模块可以正常导入"""

    def test_import_agents_base(self) -> None:
        from src.agents.base import AgentContext  # noqa: F811

        assert AgentContext is not None

    def test_import_core_protocol(self) -> None:
        from src.core.protocol import AgentMessage  # noqa: F811

        assert AgentMessage is not None

    def test_import_utils_config(self) -> None:
        from src.utils.config import Settings  # noqa: F811

        assert Settings is not None

    def test_import_utils_llm(self) -> None:
        from src.utils.llm import LLMService  # noqa: F811

        assert LLMService is not None

    def test_import_utils_logger(self) -> None:
        from src.utils.logger import AgentLogger  # noqa: F811

        assert AgentLogger is not None

    def test_import_utils_cost_tracker(self) -> None:
        from src.utils.cost_tracker import CostTracker  # noqa: F811

        assert CostTracker is not None


# ═══════════════════════════════════════════════════════════════════
# Mock LLM 工具函数测试
# ═══════════════════════════════════════════════════════════════════


class TestMakeMockLLMService:
    """验证 make_mock_llm_service 函数行为"""

    @pytest.mark.asyncio
    async def test_ainvoke_returns_fixed_text(self) -> None:
        """ainvoke 应返回固定文本"""
        mock = make_mock_llm_service(text_response="测试结果")
        result = await mock.ainvoke("任何提示词")
        assert result == "测试结果"

    @pytest.mark.asyncio
    async def test_ainvoke_accepts_all_params(self) -> None:
        """ainvoke 应接受所有标准参数"""
        mock = make_mock_llm_service(text_response="ok")
        result = await mock.ainvoke(
            prompt="test",
            system_prompt="system",
            provider="deepseek",
            agent_name="test_agent",
            session_id="sess_001",
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_invoke_structured_returns_model(self) -> None:
        """invoke_structured 应返回指定 Pydantic 模型的实例"""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str = "default"
            value: float = 0.0

        mock = make_mock_llm_service()
        result = await mock.invoke_structured(
            prompt="test",
            output_model=TestModel,
        )
        assert isinstance(result, TestModel)
        assert result.name == "default"
        assert result.value == 0.0

    def test_is_async_mock(self) -> None:
        """工厂函数应返回 AsyncMock 实例"""
        mock = make_mock_llm_service()
        assert isinstance(mock, AsyncMock)
        assert hasattr(mock, "ainvoke")
        assert hasattr(mock, "invoke_structured")
        assert hasattr(mock, "get_llm")
        assert hasattr(mock, "clear_cache")


class TestMakeMockLLMSequence:
    """验证 make_mock_llm_sequence 函数行为"""

    @pytest.mark.asyncio
    async def test_returns_in_order(self) -> None:
        """应按顺序返回响应"""
        mock = make_mock_llm_sequence(["第一轮", "第二轮", "第三轮"])

        r1 = await mock.ainvoke("prompt")
        r2 = await mock.ainvoke("prompt")
        r3 = await mock.ainvoke("prompt")

        assert r1 == "第一轮"
        assert r2 == "第二轮"
        assert r3 == "第三轮"

    @pytest.mark.asyncio
    async def test_reuses_last_on_exhaustion(self) -> None:
        """响应耗尽后应重复最后一个"""
        mock = make_mock_llm_sequence(["a", "b"])

        await mock.ainvoke("")  # a
        await mock.ainvoke("")  # b
        r3 = await mock.ainvoke("")
        assert r3 == "b"

    @pytest.mark.asyncio
    async def test_empty_list_returns_ok(self) -> None:
        """空列表应优雅降级返回 'ok'"""
        mock = make_mock_llm_sequence([])
        result = await mock.ainvoke("prompt")
        assert result == "ok"


class TestMakeMockLLMError:
    """验证 make_mock_llm_error 函数行为"""

    @pytest.mark.asyncio
    async def test_raises_default_exception(self) -> None:
        """默认应抛出 ConnectionError"""
        mock = make_mock_llm_error()
        with pytest.raises(ConnectionError, match="mock API error"):
            await mock.ainvoke("prompt")

    @pytest.mark.asyncio
    async def test_raises_custom_exception(self) -> None:
        """应支持自定义异常"""
        mock = make_mock_llm_error(ValueError("自定义错误"))
        with pytest.raises(ValueError, match="自定义错误"):
            await mock.ainvoke("prompt")


# ═══════════════════════════════════════════════════════════════════
# Shared Fixtures 测试
# ═══════════════════════════════════════════════════════════════════


class TestSampleContext:
    """验证 sample_context fixture"""

    def test_has_required_fields(self, sample_context: AgentContext) -> None:
        assert sample_context.session_id == "test-session-001"
        assert "news" in sample_context.input_data
        assert "ticker" in sample_context.input_data

    def test_is_mutable(self, sample_context: AgentContext) -> None:
        """上下文应支持在测试中修改"""
        sample_context.session_id = "custom-session"
        assert sample_context.session_id == "custom-session"


class TestSampleResult:
    """验证 sample_result fixture"""

    def test_has_required_fields(self, sample_context: AgentContext) -> None:
        from src.agents.base import AgentResult

        result = AgentResult(
            agent_name="test",
            session_id=sample_context.session_id,
            success=True,
            data={},
        )
        assert result.agent_name == "test"
        assert result.success is True
        assert result.error is None
        assert result.latency_ms == 0.0

    def test_to_message(self, sample_context: AgentContext) -> None:
        """AgentResult.to_message() 应返回有效的 AgentMessage"""
        from src.agents.base import AgentResult

        result = AgentResult(
            agent_name="test_agent",
            session_id=sample_context.session_id,
            success=True,
            data={"key": "value"},
            confidence=0.9,
            reasoning="测试原因",
        )
        msg = result.to_message()
        assert isinstance(msg, AgentMessage)
        assert msg.sender == "test_agent"
        assert msg.receiver == "orchestrator"
        assert msg.message_type == "report"
        assert msg.payload["success"] is True
        assert msg.payload["data"] == {"key": "value"}


class TestSampleMessage:
    """验证 sample_message fixture"""

    def test_has_required_fields(self, sample_message: AgentMessage) -> None:
        assert sample_message.sender == "test_sender"
        assert sample_message.receiver == "test_receiver"
        assert sample_message.message_type == "report"
        assert sample_message.session_id == "test-session-001"
        assert 0.0 <= sample_message.confidence <= 1.0
        assert sample_message.message_id is not None


class TestMockLLMFixture:
    """验证 mock_llm fixture"""

    @pytest.mark.asyncio
    async def test_patches_llm_service(self, mock_llm: AsyncMock) -> None:
        """mock_llm fixture 应能正常调用"""
        from src.utils.llm import llm_service

        # 验证 llm_service 已被 patch 为 mock
        result = await llm_service.ainvoke("测试提示词")
        assert result == '{"status": "ok", "summary": "测试响应"}'

    @pytest.mark.asyncio
    async def test_mock_llm_sequence_fixture(
        self, mock_llm_sequence: AsyncMock
    ) -> None:
        """mock_llm_sequence fixture 应能正常调用"""
        from src.utils.llm import llm_service

        r1 = await llm_service.ainvoke("第一轮")
        r2 = await llm_service.ainvoke("第二轮")
        assert r1 == "response_1"
        assert r2 == "response_2"

    @pytest.mark.asyncio
    async def test_mock_llm_error_fixture(self, mock_llm_error: AsyncMock) -> None:
        """mock_llm_error fixture 应能正常抛异常"""
        from src.utils.llm import llm_service

        with pytest.raises(ConnectionError):
            await llm_service.ainvoke("会失败的调用")


# ═══════════════════════════════════════════════════════════════════
# Logger 实例化测试（隔离测试，不共用 fixture）
# ═══════════════════════════════════════════════════════════════════


class TestAgentLogger:
    """验证 AgentLogger 可以正常实例化（不污染其他测试）"""

    def test_create_logger(self) -> None:
        log = AgentLogger("test_logger")
        assert log.name == "test_logger"
        assert log.logger is not None
        log.info("这是一个测试日志消息")

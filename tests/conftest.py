# ruff: noqa: E402 — sys.path 操作在标准 import 之前，是 src layout conftest 的必要模式

"""
pytest 共享配置 —— 测试基座 (TD-004)

提供：
1. Mock LLM 工具函数（make_mock_llm_service / make_mock_llm_sequence）
2. 共享 pytest fixtures（mock_llm, sample_context, sample_result 等）
3. asyncio 模式自动适配
4. 自定义 marker 注册

用法示例：
    async def test_agent_with_mock(mock_llm):
        result = await my_agent.run(ctx)
        assert result.success
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（src 布局的标准做法）
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.agents.base import AgentContext, AgentResult
from src.core.protocol import AgentMessage

# ═══════════════════════════════════════════════════════════════════
# Tool Functions —— Mock LLM 工厂
# ═══════════════════════════════════════════════════════════════════


def make_mock_llm_service(text_response: str = "ok") -> AsyncMock:
    """创建固定文本响应的 mock LLMService

    模拟 LLMService 的两个核心方法：
    - ainvoke() → 固定字符串
    - invoke_structured() → 根据 output_model 创建空实例

    Args:
        text_response: ainvoke() 返回的固定文本

    Returns:
        配置好的 AsyncMock，行为类似 LLMService

    用法：
        mock_svc = make_mock_llm_service("分析完成")
        with patch("src.utils.llm.llm_service", mock_svc):
            result = await agent.run(ctx)
    """
    mock = AsyncMock(spec=[
        "ainvoke", "invoke_structured", "get_llm", "clear_cache",
    ])

    async def _ainvoke(
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> str:
        return text_response

    async def _invoke_structured(
        prompt: str,
        output_model: type[BaseModel],
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> BaseModel:
        return output_model()

    mock.ainvoke = _ainvoke
    mock.invoke_structured = _invoke_structured
    mock.get_llm.return_value = MagicMock()
    mock.clear_cache.return_value = None

    return mock


def make_mock_llm_sequence(responses: list[str]) -> AsyncMock:
    """创建按顺序返回不同文本响应的 mock LLMService

    适用于需要多次 LLM 调用的场景（如辩论流程），
    每次调用 ainvoke() 返回列表中的下一个响应。

    Args:
        responses: 按顺序返回的文本列表

    Returns:
        配置好的 AsyncMock

    用法：
        mock_svc = make_mock_llm_sequence(["第一轮", "第二轮"])
        with patch("src.utils.llm.llm_service", mock_svc):
            ...
    """
    mock = AsyncMock(spec=[
        "ainvoke", "invoke_structured", "get_llm", "clear_cache",
    ])
    iterator = iter(responses)

    async def _ainvoke(
        prompt: str,
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> str:
        try:
            return next(iterator)
        except StopIteration:
            return responses[-1] if responses else "ok"

    async def _invoke_structured(
        prompt: str,
        output_model: type[BaseModel],
        system_prompt: str | None = None,
        provider: str | None = None,
        agent_name: str = "unknown",
        session_id: str = "",
    ) -> BaseModel:
        return output_model()

    mock.ainvoke = _ainvoke
    mock.invoke_structured = _invoke_structured
    mock.get_llm.return_value = MagicMock()

    return mock


def make_mock_llm_error(exception: Exception | None = None) -> AsyncMock:
    """创建调用时抛出异常的 mock LLMService

    用于测试 Agent 的错误处理路径（超时、API 异常等）。

    Args:
        exception: 要抛出的异常，默认 ConnectionError("mock API error")

    Returns:
        配置好的 AsyncMock
    """
    exc = exception or ConnectionError("mock API error")
    mock = AsyncMock(spec=[
        "ainvoke", "invoke_structured", "get_llm", "clear_cache",
    ])

    async def _error(*args: Any, **kwargs: Any) -> Any:
        raise exc

    mock.ainvoke = _error
    mock.invoke_structured = _error
    mock.get_llm.return_value = MagicMock()

    return mock


# ═══════════════════════════════════════════════════════════════════
# pytest 配置
# ═══════════════════════════════════════════════════════════════════


def pytest_configure(config: pytest.Config) -> None:
    """注册自定义 markers"""
    config.addinivalue_line("markers", "unit: 单元测试（无需外部依赖）")
    config.addinivalue_line(
        "markers", "integration: 集成测试（需要真实 LLM 或数据源）"
    )
    config.addinivalue_line(
        "markers",
        "slow: 慢速测试（标记并默认跳过，用 pytest --slow 运行）",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """自动为异步测试添加 asyncio marker（配合 asyncio_mode=auto 使用）"""
    for item in items:
        if "asyncio" in item.keywords:
            continue
        # 如果测试函数是协程函数，添加 asyncio marker
        if hasattr(item, "obj") and hasattr(item.obj, "__code__"):
            try:
                import inspect

                if inspect.iscoroutinefunction(item.obj):
                    item.add_marker(pytest.mark.asyncio)
            except (TypeError, AttributeError):
                # 某些测试 item 无 obj 属性，安全跳过
                pass


# ═══════════════════════════════════════════════════════════════════
# Shared Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_llm() -> AsyncMock:
    """自动 patch llm_service 的基础 fixture

    所有需要 mock LLM 的测试可以直接使用此 fixture，
    不需要手动编写 with patch(...) 上下文。

    Returns:
        mock 的 LLMService 实例

    用法：
        async def test_something(mock_llm):
            result = await my_agent.run(ctx)
            assert result.success
    """
    mock_svc = make_mock_llm_service('{"status": "ok", "summary": "测试响应"}')
    with patch("src.utils.llm.llm_service", mock_svc):
        yield mock_svc


@pytest.fixture
def sample_context() -> AgentContext:
    """创建标准的测试上下文"""
    return AgentContext(
        session_id="test-session-001",
        input_data={
            "news": "今日股市震荡上行，沪指收涨0.5%",
            "ticker": "000001",
            "market_data": {},
        },
    )


@pytest.fixture
def sample_result() -> AgentResult:
    """创建标准的 Agent 测试结果"""
    return AgentResult(
        agent_name="test_agent",
        session_id="test-session-001",
        success=True,
        data={
            "summary": "测试结果摘要",
            "sentiment": "positive",
            "confidence": 0.85,
        },
        confidence=0.85,
        reasoning="基于测试数据的分析结果",
    )


@pytest.fixture
def sample_message() -> AgentMessage:
    """创建标准的 Agent 通信消息"""
    return AgentMessage(
        sender="test_sender",
        receiver="test_receiver",
        message_type="report",
        session_id="test-session-001",
        payload={"data": "test"},
        confidence=0.8,
    )


@pytest.fixture
def mock_llm_sequence() -> AsyncMock:
    """按顺序返回响应的 mock LLM fixture

    用法：
        async def test_multi_turn(mock_llm_sequence):
            # mock_llm_sequence 默认返回 ["response_1", "response_2"]
            ...
    """
    mock_svc = make_mock_llm_sequence(["response_1", "response_2"])
    with patch("src.utils.llm.llm_service", mock_svc):
        yield mock_svc


@pytest.fixture
def mock_llm_error() -> AsyncMock:
    """调用时抛异常的 mock LLM fixture

    用于测试 Agent 在 LLM 调用失败时的错误处理逻辑。

    用法：
        async def test_agent_retry(mock_llm_error):
            result = await agent.run_safe(ctx)
            assert not result.success
            assert "mock API error" in result.error
    """
    mock_svc = make_mock_llm_error()
    with patch("src.utils.llm.llm_service", mock_svc):
        yield mock_svc

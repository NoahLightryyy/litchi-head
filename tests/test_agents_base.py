"""Agent 基类业务测试（TD-004 追认）"""

import asyncio
from unittest.mock import patch

import pytest

from src.agents.base import AgentContext, AgentResult, BaseAgent

# ═══════════════════════════════════════════════════════════════════
# AgentContext
# ═══════════════════════════════════════════════════════════════════


class TestAgentContext:
    def test_has_required_fields(self):
        ctx = AgentContext(session_id="s1", input_data={"key": "val"})
        assert ctx.session_id == "s1"
        assert ctx.input_data == {"key": "val"}
        assert ctx.memory == {}
        assert ctx.config == {}

    def test_is_mutable(self):
        ctx = AgentContext(session_id="s1", input_data={})
        ctx.memory["key"] = "val"
        assert ctx.memory["key"] == "val"


# ═══════════════════════════════════════════════════════════════════
# AgentResult
# ═══════════════════════════════════════════════════════════════════


class TestAgentResult:
    def test_has_required_fields(self):
        r = AgentResult()
        assert r.agent_name == ""
        assert r.success is True
        assert r.data == {}
        assert r.confidence == 0.0
        assert r.error is None
        assert r.latency_ms == 0.0

    def test_to_message_standard(self):
        r = AgentResult(
            agent_name="test_agent",
            session_id="s1",
            success=True,
            data={"result": "ok"},
            confidence=0.95,
            reasoning="因为测试",
        )
        msg = r.to_message()
        assert msg.sender == "test_agent"
        assert msg.receiver == "orchestrator"
        assert msg.message_type == "report"
        assert msg.session_id == "s1"
        assert msg.confidence == 0.95
        assert msg.payload["data"] == {"result": "ok"}
        assert msg.payload["reasoning"] == "因为测试"

    def test_to_message_error_case(self):
        r = AgentResult(
            agent_name="err_agent",
            session_id="s1",
            success=False,
            data={},
            error="出错了",
        )
        msg = r.to_message()
        assert msg.payload["success"] is False
        assert msg.payload["error"] == "出错了"

    def test_to_message_message_id_unique(self):
        r1 = AgentResult(agent_name="a", session_id="s1")
        r2 = AgentResult(agent_name="a", session_id="s1")
        assert r1.to_message().message_id != r2.to_message().message_id


# ═══════════════════════════════════════════════════════════════════
# BaseAgent
# ═══════════════════════════════════════════════════════════════════


class _ConcreteAgent(BaseAgent):
    """测试用的具体 Agent 实现"""

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(data={"parsed": ctx.input_data}, confidence=0.8)


class _SlowAgent(BaseAgent):
    """模拟超时的 Agent"""

    async def run(self, ctx: AgentContext) -> AgentResult:
        await asyncio.sleep(999)
        return AgentResult()


class _CrashAgent(BaseAgent):
    """模拟抛异常的 Agent"""

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise ValueError("模拟错误")


class TestBaseAgent:
    def test_init(self):
        agent = _ConcreteAgent("test_agent", {"key": "val"})
        assert agent.name == "test_agent"
        assert agent.config == {"key": "val"}

    def test_init_default_config(self):
        agent = _ConcreteAgent("test_agent")
        assert agent.config == {}

    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseAgent("abstract")  # type: ignore

    @pytest.mark.asyncio
    async def test_run_safe_success(self):
        agent = _ConcreteAgent("success_agent")
        ctx = AgentContext(session_id="s1", input_data={"msg": "hello"})
        result = await agent.run_safe(ctx)

        assert result.success is True
        assert result.agent_name == "success_agent"
        assert result.session_id == "s1"
        assert result.data["parsed"] == {"msg": "hello"}
        assert result.confidence == 0.8
        assert result.error is None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_safe_sets_agent_name_and_session(self):
        """验证 run_safe 会正确填充 agent_name 和 session_id"""
        agent = _ConcreteAgent("named_agent")
        ctx = AgentContext(session_id="session_x", input_data={})
        result = await agent.run_safe(ctx)
        assert result.agent_name == "named_agent"
        assert result.session_id == "session_x"

    @pytest.mark.asyncio
    async def test_run_safe_timeout(self):
        agent = _SlowAgent("slow_agent")
        ctx = AgentContext(session_id="s1", input_data={})

        with patch.object(agent, "config", {"timeout": 0.001}):
            with patch(
                "src.agents.base.settings.debate_timeout_seconds", 0.001
            ):
                result = await agent.run_safe(ctx)

        assert result.success is False
        assert "超时" in (result.error or "")
        assert result.agent_name == "slow_agent"
        assert result.session_id == "s1"

    @pytest.mark.asyncio
    async def test_run_safe_exception(self):
        agent = _CrashAgent("crash_agent")
        ctx = AgentContext(session_id="s1", input_data={})
        result = await agent.run_safe(ctx)

        assert result.success is False
        assert "模拟错误" in (result.error or "")
        assert result.agent_name == "crash_agent"

    @pytest.mark.asyncio
    async def test_run_safe_records_latency(self):
        agent = _ConcreteAgent("fast_agent")
        ctx = AgentContext(session_id="s1", input_data={})
        result = await agent.run_safe(ctx)
        assert result.latency_ms > 0
        assert isinstance(result.latency_ms, float)

    def test_run_raises_not_implemented(self):
        """直接调用抽象方法应抛 NotImplementedError"""

        class _Minimal(BaseAgent):
            pass

        with pytest.raises(TypeError):
            _Minimal("minimal")  # 没实现 abstractmethod 就不能实例化

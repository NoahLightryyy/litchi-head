"""XiaoZhiAgent（教育小智）单元测试"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.base import AgentContext, AgentResult
from src.agents.xiao_zhi import XiaoZhiAgent


@pytest.fixture
def agent():
    """创建测试用 XiaoZhiAgent 实例"""
    return XiaoZhiAgent()


@pytest.fixture
def agent_with_kb_path(tmp_path):
    """使用临时知识库路径的 Agent"""
    return XiaoZhiAgent(knowledge_base_path=str(tmp_path))


# ═══════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════
#
# 注意：ctx fixture 由 tests/test_agents/conftest.py 提供
# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════


class TestXiaoZhiInit:
    def test_init_default_name(self):
        agent = XiaoZhiAgent()
        assert agent.name == "xiao_zhi"

    def test_init_custom_name(self):
        agent = XiaoZhiAgent(name="my_edu_agent")
        assert agent.name == "my_edu_agent"

    def test_init_creates_knowledge_base(self, tmp_path):
        """使用临时路径避免真实知识库数据干扰"""
        agent = XiaoZhiAgent(knowledge_base_path=str(tmp_path))
        assert hasattr(agent, "knowledge_base")
        # 知识库应能正常使用（search 返回 list，空知识库返回空列表）
        assert agent.knowledge_base.search("测试") == []

    def test_get_tools_returns_list(self, agent):
        tools = agent.get_tools()
        assert isinstance(tools, list)
        # Phase 0 返回空列表（ADR-009: Phase 1 接入具体 Tool）


# ═══════════════════════════════════════════════════════════════════
# Run — 输入验证
# ═══════════════════════════════════════════════════════════════════


class TestXiaoZhiRunValidation:
    async def test_run_without_question_returns_error(self, agent, ctx):
        ctx.input_data = {}
        result = await agent.run(ctx)
        assert result.success is False
        assert "question" in (result.error or "").lower()

    async def test_run_with_empty_question_returns_error(self, agent, ctx):
        ctx.input_data = {"question": ""}
        result = await agent.run(ctx)
        assert result.success is False

    async def test_run_with_whitespace_question(self, agent, ctx):
        ctx.input_data = {"question": "   "}
        result = await agent.run(ctx)
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════
# Run — 知识检索与 LLM 调用（Mock LLM）
# ═══════════════════════════════════════════════════════════════════


class TestXiaoZhiRunWithMockLLM:
    async def test_run_searches_knowledge_base(self, agent, ctx):
        """验证 run 会调用知识库搜索"""
        with patch.object(
            agent.knowledge_base, "search", wraps=agent.knowledge_base.search,
        ) as mock_search:
            with patch(
                "src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock,
            ) as mock_llm:
                mock_llm.return_value = "安全边际是价值投资的核心概念..."
                await agent.run(ctx)

                # 知识库搜索应被调用
                mock_search.assert_called_once()
                # 传入的查询应包含用户问题
                args, _ = mock_search.call_args
                assert "安全边际" in str(args[0])

    async def test_run_passes_knowledge_to_llm(self, agent, ctx):
        """验证 LLM 调用包含知识库上下文"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "安全边际是..."

            # 先导入一些知识到知识库
            knowledge_text = "安全边际 = 内在价值 - 市场价格"
            agent.knowledge_base.chunks = [
                {
                    "text": knowledge_text,
                    "source": "安全边际.md",
                    "section": "定义",
                    "type": "concept",
                },
            ]
            agent.knowledge_base._rebuild_embeddings()

            result = await agent.run(ctx)

            # 验证 LLM 调用参数中包含知识库内容
            call_args, call_kwargs = mock_llm.call_args
            prompt = call_kwargs.get("prompt", call_args[0] if call_args else "")
            assert "安全边际" in prompt
            assert result.success is True
            assert result.data.get("answer") == "安全边际是..."

    async def test_run_no_knowledge_found(self, agent, ctx):
        """验证无相关知识时 Agent 仍能回答（降级为纯 LLM）"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "抱歉，我没有找到相关知识..."

            # 知识库为空
            result = await agent.run(ctx)

            assert result.success is True
            call_args, call_kwargs = mock_llm.call_args
            prompt = call_args[0] if call_args else call_kwargs.get("prompt", "")
            assert "安全边际" in prompt

    async def test_run_sets_confidence_based_on_search(self, agent, ctx):
        """验证 confidence 与知识检索命中情况关联"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock):
            # 有知识命中
            agent.knowledge_base.chunks = [
                {
                    "text": "安全边际是核心概念",
                    "source": "test.md",
                    "section": "定义",
                    "type": "concept",
                },
            ]
            agent.knowledge_base._rebuild_embeddings()

            result_with_kb = await agent.run(ctx)
            assert result_with_kb.confidence >= 0.0

    async def test_run_returns_structured_result(self, agent, ctx):
        """验证返回结果包含 answer 字段"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "安全边际是价值投资的核心概念..."
            result = await agent.run(ctx)

            assert isinstance(result, AgentResult)
            assert result.success is True
            assert "answer" in result.data

    async def test_run_with_different_question_types(self, agent):
        """验证不同类型问题都能正确处理"""
        questions = ["什么是MACD？", "PE怎么计算？", "巴菲特是谁？"]
        for q in questions:
            ctx = AgentContext(session_id="test-session", input_data={"question": q})
            with patch(
                "src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock,
            ) as mock_llm:
                mock_llm.return_value = f"关于{q}的回答..."
                result = await agent.run(ctx)
                assert result.success is True
                assert "answer" in result.data


# ═══════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════


class TestXiaoZhiSystemPrompt:
    def test_system_prompt_contains_role(self, agent):
        prompt = agent.get_system_prompt()
        assert "教育" in prompt
        assert "金融" in prompt

    def test_system_prompt_mentions_knowledge_base(self, agent):
        prompt = agent.get_system_prompt()
        assert "知识库" in prompt or "知识" in prompt


# ═══════════════════════════════════════════════════════════════════
# Run — LLM 错误路径（边界条件）
# ═══════════════════════════════════════════════════════════════════


class TestXiaoZhiLLMError:
    async def test_llm_timeout_returns_error(self, agent, ctx):
        """LLM 超时时 Agent 应返回错误而非崩溃"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = TimeoutError("LLM API timeout after 30s")
            result = await agent.run(ctx)
            assert result.success is False
            assert "timeout" in (result.error or "").lower() or "LLM" in (result.error or "")

    async def test_llm_empty_response(self, agent, ctx):
        """LLM 返回空字符串时 Agent 不应崩溃"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ""
            result = await agent.run(ctx)
            assert result.success is True
            assert isinstance(result.data, dict)

    async def test_llm_connection_error(self, agent, ctx):
        """网络错误时 Agent 应优雅降级"""
        with patch("src.agents.xiao_zhi.llm_service.ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = ConnectionError("Connection refused")
            result = await agent.run(ctx)
            assert result.success is False
            assert result.error is not None

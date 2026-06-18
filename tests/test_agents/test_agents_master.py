"""MasterAgent（通用大师 Agent）单元测试

注意：
- ctx / buffet_lite / munger_lite / make_analysis 由 tests/test_agents/conftest.py 提供
- agent_with_skill / agent_with_skill_id 是 MasterAgent 独有，保留在文件内
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.base import AgentContext, AgentResult
from src.agents.master_agent import MasterAgent
from src.memory.skill_disk import SkillDisk

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def agent_with_skill(tmp_path, buffet_lite):
    """通过 skill 创建（使用临时知识库路径）"""
    return MasterAgent(skill=buffet_lite, knowledge_base_path=str(tmp_path))


@pytest.fixture
def agent_with_skill_id(tmp_path):
    """通过 skill_id 创建（使用临时知识库路径）"""
    return MasterAgent(skill_id="buffett", knowledge_base_path=str(tmp_path))


# ═══════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentInit:
    """初始化测试"""

    def test_init_with_skill(self, buffet_lite):
        """通过 skill 参数创建"""
        agent = MasterAgent(skill=buffet_lite)
        assert agent.name == "master"
        assert agent.skill.skill_id == "buffett"
        assert agent.skill.name == "沃伦·巴菲特"

    def test_init_with_skill_id(self):
        """通过 skill_id 自动加载"""
        agent = MasterAgent(skill_id="buffett")
        assert agent.name == "master.buffett"
        assert agent.skill.skill_id == "buffett"

    def test_init_with_skill_id_and_disk(self):
        """通过 skill_id + 自定义 disk"""
        disk = SkillDisk()
        agent = MasterAgent(skill_id="munger", disk=disk)
        assert agent.name == "master.munger"
        assert agent.skill.skill_id == "munger"
        assert agent.skill.name == "查理·芒格"

    def test_init_creates_knowledge_base(self, tmp_path, buffet_lite):
        """初始化创建 knowledge_base（用临时路径避免真实数据）"""
        agent = MasterAgent(skill=buffet_lite, knowledge_base_path=str(tmp_path))
        assert hasattr(agent, "knowledge_base")
        assert agent.knowledge_base.search("测试") == []

    def test_init_without_skill_raises(self):
        """未提供 skill 或 skill_id 抛出 ValueError"""
        with pytest.raises(ValueError, match="必须提供 skill"):
            MasterAgent()

    def test_init_with_skill_id_nonexistent_raises(self):
        """不存在的 skill_id 抛出 KeyError"""
        with pytest.raises(KeyError):
            MasterAgent(skill_id="nonexistent")

    def test_get_tools_returns_list(self, agent_with_skill):
        """get_tools() 返回列表（Phase 0 为空）"""
        tools = agent_with_skill.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0


# ═══════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentSystemPrompt:
    """系统提示词测试"""

    def test_system_prompt_matches_skill(self, agent_with_skill):
        """system_prompt 来自 skill"""
        prompt = agent_with_skill.get_system_prompt()
        assert "安全边际" in prompt
        assert "巴菲特" in prompt
        assert "护城河" in prompt

    def test_different_skill_different_prompt(self, buffet_lite, munger_lite):
        """不同大师的 system_prompt 不同"""
        buffett_agent = MasterAgent(skill=buffet_lite)
        munger_agent = MasterAgent(skill=munger_lite)
        assert "巴菲特" in buffett_agent.get_system_prompt()
        assert "芒格" in munger_agent.get_system_prompt()
        assert buffett_agent.get_system_prompt() != munger_agent.get_system_prompt()


# ═══════════════════════════════════════════════════════════════════
# Run — 输入验证
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentRunValidation:
    """输入验证测试"""

    async def test_run_without_question_returns_error(self, agent_with_skill, ctx):
        ctx.input_data = {}
        result = await agent_with_skill.run(ctx)
        assert result.success is False
        assert "question" in (result.error or "").lower()

    async def test_run_with_empty_question_returns_error(self, agent_with_skill, ctx):
        ctx.input_data = {"question": ""}
        result = await agent_with_skill.run(ctx)
        assert result.success is False

    async def test_run_with_whitespace_question(self, agent_with_skill, ctx):
        ctx.input_data = {"question": "   "}
        result = await agent_with_skill.run(ctx)
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════
# Run — Mock LLM 流程
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentRunWithMockLLM:
    """Mock LLM 流程测试（结构化输出）"""

    async def test_run_searches_knowledge_base(self, agent_with_skill, ctx, make_analysis):
        """验证 run 会调用知识库搜索"""
        with patch.object(
            agent_with_skill.knowledge_base,
            "search",
            wraps=agent_with_skill.knowledge_base.search,
        ) as mock_search:
            with patch(
                "src.agents.master_agent.llm_service.invoke_structured",
                new_callable=AsyncMock,
            ) as mock_llm:
                mock_llm.return_value = make_analysis()
                await agent_with_skill.run(ctx)

                mock_search.assert_called_once()
                _, kwargs = mock_search.call_args
                assert "安全边际" in str(kwargs.get("query", ""))

    async def test_run_passes_knowledge_to_llm(self, agent_with_skill, ctx, make_analysis):
        """验证 LLM 调用包含知识库上下文"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(
                summary="安全边际是关键",
                analysis="安全边际 = 内在价值 - 市场价格",
            )

            # 注入知识到知识库
            agent_with_skill.knowledge_base.chunks = [
                {
                    "text": "安全边际 = 内在价值 - 市场价格",
                    "source": "安全边际.md",
                    "section": "定义",
                    "type": "concept",
                },
            ]
            agent_with_skill.knowledge_base._rebuild_embeddings()

            result = await agent_with_skill.run(ctx)

            # 验证 LLM prompt 中包含知识库内容
            call_args, call_kwargs = mock_llm.call_args
            prompt = call_kwargs.get("prompt", call_args[0] if call_args else "")
            assert "安全边际" in prompt

            # 验证返回结果包含分析内容
            assert result.success is True
            assert "安全边际是关键" in str(result.data.get("answer", ""))

    async def test_run_no_knowledge_found(self, agent_with_skill, ctx, make_analysis):
        """无知识命中时降级为纯 LLM 回答"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(
                summary="基于我的理解",
                analysis="安全边际是价值投资的核心概念",
            )

            # 知识库为空 → 无命中
            result = await agent_with_skill.run(ctx)

            assert result.success is True
            call_args, call_kwargs = mock_llm.call_args
            prompt = call_args[0] if call_args else call_kwargs.get("prompt", "")
            assert "安全边际" in prompt

    async def test_run_sets_confidence_with_knowledge(self, agent_with_skill, ctx, make_analysis):
        """知识命中时 confidence 较高"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(score=85)
            agent_with_skill.knowledge_base.chunks = [
                {
                    "text": "安全边际是核心概念",
                    "source": "test.md",
                    "section": "定义",
                    "type": "concept",
                },
            ]
            agent_with_skill.knowledge_base._rebuild_embeddings()

            result = await agent_with_skill.run(ctx)
            # 知识命中 + LLM 评分 → 置信度较高
            assert result.confidence >= 0.7
            assert result.confidence <= 0.95

    async def test_run_sets_confidence_without_knowledge(  # noqa: E501
        self, agent_with_skill, ctx, make_analysis,
    ):
        """无知识命中 + 低 LLM 评分时 confidence 较低"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(score=60)
            # 知识库为空
            result = await agent_with_skill.run(ctx)
            # 无知识命中 + score=60 → confidence = 0.6 + 0 + 0.6*0.3 = 0.78
            assert result.confidence == 0.78

    async def test_run_returns_structured_result(self, agent_with_skill, ctx, make_analysis):
        """返回结果包含大师标识和结构化分析"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            analysis = make_analysis(rating="看涨", score=90)
            mock_llm.return_value = analysis
            result = await agent_with_skill.run(ctx)

            assert isinstance(result, AgentResult)
            assert result.success is True
            # 向后兼容字段
            assert isinstance(result.data.get("answer"), str)
            assert result.data.get("skill_id") == "buffett"
            assert result.data.get("skill_name") == "沃伦·巴菲特"
            assert "knowledge_sources" in result.data
            # 结构化字段
            assert "analysis" in result.data
            assert result.data["analysis"]["rating"] == "看涨"
            assert result.data["analysis"]["score"] == 90

    async def test_reasoning_contains_skill_name_and_rating(  # noqa: E501
        self, agent_with_skill, ctx, make_analysis,
    ):
        """reasoning 字段包含大师名和评级"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(rating="看涨")
            result = await agent_with_skill.run(ctx)
            assert "巴菲特" in result.reasoning
            assert "看涨" in result.reasoning


# ═══════════════════════════════════════════════════════════════════
# Run — 不同大师 Skill
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentDifferentSkills:
    """不同大师 Skill 切换测试"""

    async def test_buffett_agent_uses_buffett_identity(self, buffet_lite, make_analysis):
        """巴菲特 Agent 使用巴菲特的 prompt"""
        agent = MasterAgent(skill=buffet_lite)
        ctx = AgentContext(session_id="s1", input_data={"question": "如何选股？"})
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis()
            result = await agent.run(ctx)
            assert result.data.get("skill_id") == "buffett"
            assert result.data.get("skill_name") == "沃伦·巴菲特"

    async def test_munger_agent_uses_munger_identity(self, munger_lite, make_analysis):
        """芒格 Agent 使用芒格的 prompt"""
        agent = MasterAgent(skill=munger_lite)
        ctx = AgentContext(session_id="s1", input_data={"question": "如何避免投资错误？"})
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis()
            result = await agent.run(ctx)
            assert result.data.get("skill_id") == "munger"
            assert result.data.get("skill_name") == "查理·芒格"

    async def test_different_skills_have_different_system_prompts_in_llm_call(  # noqa: E501
        self, buffet_lite, munger_lite, make_analysis,
    ):
        """不同大师的 system_prompt 传递到 LLM 调用不同"""
        buffett_agent = MasterAgent(skill=buffet_lite)
        munger_agent = MasterAgent(skill=munger_lite)

        for agent, expected_text in [
            (buffett_agent, "安全边际"),
            (munger_agent, "多元思维"),
        ]:
            ctx = AgentContext(session_id="s1", input_data={"question": "test"})
            with patch(
                "src.agents.master_agent.llm_service.invoke_structured",
                new_callable=AsyncMock,
            ) as mock_llm:
                mock_llm.return_value = make_analysis()
                await agent.run(ctx)
                call_args, call_kwargs = mock_llm.call_args
                sys_prompt = call_kwargs.get("system_prompt", "")
                assert expected_text in sys_prompt


# ═══════════════════════════════════════════════════════════════════
# Run — run_safe 封装
# ═══════════════════════════════════════════════════════════════════


class TestMasterAgentRunSafe:
    """run_safe() 封装层测试"""

    async def test_run_safe_success(self, agent_with_skill, ctx, make_analysis):
        """run_safe 成功返回结果"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = make_analysis(
                summary="安全边际是关键",
                analysis="详细分析内容",
            )
            result = await agent_with_skill.run_safe(ctx)
            assert result.success is True
            assert "安全边际是关键" in str(result.data.get("answer", ""))
            assert result.agent_name == "master"
            assert result.session_id == "test-session"
            assert result.latency_ms >= 0  # 耗时记录

    async def test_run_safe_llm_error(self, agent_with_skill, ctx):
        """LLM 异常时 run_safe 返回错误"""
        with patch(
            "src.agents.master_agent.llm_service.invoke_structured",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM 调用异常")
            result = await agent_with_skill.run_safe(ctx)
            assert result.success is False
            assert "LLM 调用异常" in (result.error or "")

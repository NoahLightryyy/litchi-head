"""MasterAgent 真实 LLM 集成测试

前提条件：
    - 必须配置 DEEPSEEK_API_KEY（.env 文件）
    - 会实际消耗 DeepSeek token（约 0.01~0.05 元/次）

运行方式：
    pytest tests/test_integration_master_agent.py -v --tb=short          # 含 API Key 时运行
    pytest tests/test_integration_master_agent.py -v -m integration      # 同上

注意：
    - 所有测试标记为 @pytest.mark.integration，不影响日常 CI
    - 自动跳过未配置 API Key 的情况
"""

import pytest

from src.agents.base import AgentContext
from src.agents.master_agent import MasterAgent
from src.memory.skill_disk import MasterSkill

# ═══════════════════════════════════════════════════════════════════
# 跳过条件 —— 无 API Key 时跳过全部集成测试
# ═══════════════════════════════════════════════════════════════════


def _has_deepseek_key() -> bool:
    """检查 DeepSeek API Key 是否已配置"""
    try:
        from src.utils.config import settings

        return bool(settings.deepseek_api_key)
    except Exception:
        return False


skip_no_key = pytest.mark.skipif(
    not _has_deepseek_key(),
    reason="需要 DEEPSEEK_API_KEY（在 .env 中配置）",
)

# ═══════════════════════════════════════════════════════════════════
# 测试用大师 Skill（轻量版）
# ═══════════════════════════════════════════════════════════════════

_BUFFETT_LITE = MasterSkill(
    skill_id="buffett",
    name="沃伦·巴菲特",
    avatar="🧑‍🦳",
    title="伯克希尔·哈撒韦 CEO",
    description="价值投资大师",
    system_prompt=(
        "你是沃伦·巴菲特，伯克希尔·哈撒韦的CEO，全球最著名的价值投资者之一。\n\n"
        "你的投资哲学核心：\n"
        "1. 安全边际 —— 永远以低于内在价值的价格买入\n"
        "2. 护城河 —— 寻找拥有持久竞争优势的企业\n"
        "3. 长期持有 —— 你最喜欢的持有期是「永远」\n"
        "4. 能力圈 —— 只投资你理解的企业\n\n"
        "请以第一人称、平实的语言回答，就像在伯克希尔股东大会上回答股东的问题。"
    ),
    knowledge_filter="巴菲特",
    enabled_by_default=True,
)

_MUNGER_LITE = MasterSkill(
    skill_id="munger",
    name="查理·芒格",
    avatar="🧓",
    title="伯克希尔副董事长",
    description="多元思维模型倡导者",
    system_prompt=(
        "你是查理·芒格，伯克希尔·哈撒韦的副董事长，沃伦·巴菲特的长期搭档。\n\n"
        "你的投资哲学核心：\n"
        "1. 多元思维模型 —— 用多学科视角看问题\n"
        "2. 逆向思考 —— 「反过来想，总是反过来想」\n"
        "3. 人类误判心理学 —— 识别和避免认知偏误\n"
        "4. 能力圈 —— 清楚自己不知道什么\n\n"
        "请以第一人称、简洁犀利的语言回答，常引用格言和心理学原理。"
    ),
    knowledge_filter="芒格",
    enabled_by_default=True,
)

# ═══════════════════════════════════════════════════════════════════
# 集成测试 —— 真实 DeepSeek API 调用
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.asyncio
@skip_no_key
class TestMasterAgentRealLLM:
    """真实 DeepSeek API 调用集成测试"""

    async def test_buffett_answers_with_identity(self, tmp_path):
        """巴菲特 Agent 用真实 DeepSeek 回答，验证身份和回答质量"""
        agent = MasterAgent(
            skill=_BUFFETT_LITE,
            knowledge_base_path=str(tmp_path),
        )
        ctx = AgentContext(
            session_id="intg-buffett-001",
            input_data={"question": "什么是安全边际？为什么它很重要？"},
        )

        result = await agent.run(ctx)

        # 基本结构验证
        assert result.success is True
        assert result.confidence > 0
        assert result.data.get("skill_id") == "buffett"
        assert result.data.get("skill_name") == "沃伦·巴菲特"

        # 回答内容验证
        answer = result.data.get("answer", "")
        assert isinstance(answer, str)
        assert len(answer) > 50  # 至少 50 个字符
        # 应体现巴菲特的身份或理念
        assert any(
            keyword in answer.lower()
            for keyword in ["安全边际", "margin", "价值", "低于", "价格", "内在价值"]
        )

        # 结构化输出验证
        analysis = result.data.get("analysis", {})
        assert isinstance(analysis, dict)
        assert "rating" in analysis
        assert "score" in analysis
        assert "summary" in analysis
        assert "analysis" in analysis
        assert "key_evidence" in analysis

    async def test_munger_answers_with_distinct_style(self, tmp_path):
        """芒格 Agent 风格不同，验证身份区隔"""
        agent = MasterAgent(
            skill=_MUNGER_LITE,
            knowledge_base_path=str(tmp_path),
        )
        ctx = AgentContext(
            session_id="intg-munger-001",
            input_data={"question": "如何避免常见的投资错误？"},
        )

        result = await agent.run(ctx)

        # 基本结构
        assert result.success is True
        assert result.data.get("skill_id") == "munger"
        assert result.data.get("skill_name") == "查理·芒格"

        # 回答内容验证
        answer = result.data.get("answer", "")
        assert isinstance(answer, str)
        assert len(answer) > 50

        # 结构化输出验证
        analysis = result.data.get("analysis", {})
        assert isinstance(analysis, dict)
        assert "rating" in analysis

    async def test_with_knowledge_base_context(self, tmp_path):
        """知识库命中时，回答应引用知识内容"""
        agent = MasterAgent(
            skill=_BUFFETT_LITE,
            knowledge_base_path=str(tmp_path),
        )

        # 注入测试用知识到临时知识库
        agent.knowledge_base.chunks = [
            {
                "text": (
                    "安全边际是价值投资的核心概念，由本杰明·格雷厄姆提出。"
                    "它指的是证券的市场价格与其内在价值之间的差额。"
                    "安全边际越大，投资风险越低，潜在回报越高。"
                ),
                "source": "安全边际概念.md",
                "section": "定义",
                "type": "concept",
            },
        ]
        agent.knowledge_base._rebuild_embeddings()

        ctx = AgentContext(
            session_id="intg-kb-001",
            input_data={"question": "安全边际"},
        )

        result = await agent.run(ctx)

        assert result.success is True
        answer = result.data.get("answer", "")
        assert len(answer) > 50

        # 知识命中 → confidence 较高（知识 0.15 + LLM score/100*0.3 + 基础 0.6）
        assert result.confidence >= 0.7

        # 结果应包含知识来源
        sources = result.data.get("knowledge_sources", [])
        assert len(sources) > 0

    async def test_no_knowledge_pure_llm(self, tmp_path):
        """知识库为空时降级为纯 LLM 回答，confidence 较低"""
        agent = MasterAgent(
            skill=_BUFFETT_LITE,
            knowledge_base_path=str(tmp_path),
        )
        # 确保知识库为空
        agent.knowledge_base.chunks = []
        agent.knowledge_base._rebuild_embeddings()

        ctx = AgentContext(
            session_id="intg-nokb-001",
            input_data={"question": "如何看待当前中国股市的投资机会？"},
        )

        result = await agent.run(ctx)

        assert result.success is True
        answer = result.data.get("answer", "")
        assert len(answer) > 50

        # 无知识命中 → 纯 LLM 结构化回答
        sources = result.data.get("knowledge_sources", [])
        assert len(sources) == 0

        # 结构化输出存在
        analysis = result.data.get("analysis", {})
        assert isinstance(analysis, dict)
        assert "rating" in analysis

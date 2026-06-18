"""pytest 共享配置 —— agents 模块测试基座

提供：
1. 测试用 MasterSkill 工厂 fixture（buffet_lite / munger_lite）
2. 共享 fixture（ctx / make_analysis）
3. 根 conftest.py 中的共享 fixture 自动继承

用法：
    def test_init(buffet_lite):
        agent = MasterAgent(skill=buffet_lite)

    def test_analysis(make_analysis):
        result = make_analysis(rating="看涨")
"""

import pytest

from src.agents.base import AgentContext
from src.agents.master_agent import InvestmentAnalysis
from src.memory.skill_disk import MasterSkill


@pytest.fixture
def ctx():
    """创建测试用 AgentContext（统一版）"""
    return AgentContext(
        session_id="test-session",
        input_data={"question": "什么是安全边际？"},
    )


@pytest.fixture
def buffet_lite() -> MasterSkill:
    """沃伦·巴菲特 — 测试用 MasterSkill"""
    return MasterSkill(
        skill_id="buffett",
        name="沃伦·巴菲特",
        avatar="🧑‍🦳",
        title="伯克希尔·哈撒韦 CEO",
        description="价值投资大师",
        system_prompt="我是巴菲特。我的原则：安全边际、护城河、长期持有。",
        knowledge_filter="巴菲特",
        enabled_by_default=True,
    )


@pytest.fixture
def munger_lite() -> MasterSkill:
    """查理·芒格 — 测试用 MasterSkill"""
    return MasterSkill(
        skill_id="munger",
        name="查理·芒格",
        avatar="🧓",
        title="伯克希尔副董事长",
        description="多元思维模型倡导者",
        system_prompt="我是芒格。我的原则：多元思维、逆向思考、人类误判心理学。",
        knowledge_filter="芒格",
        enabled_by_default=True,
    )


@pytest.fixture
def make_analysis():
    """创建测试用 InvestmentAnalysis 实例的工厂

    用法：
        def test_something(make_analysis):
            analysis = make_analysis(rating="看涨", score=90)
    """

    def _inner(**overrides) -> InvestmentAnalysis:
        kwargs = dict(
            rating="看涨",
            score=75,
            summary="安全边际是价值投资的核心",
            analysis="安全边际指的是市场价格与内在价值之间的差额。安全边际越大，投资风险越低。",
            key_evidence=["安全边际 = 内在价值 - 市场价格", "格雷厄姆提出的核心概念"],
            risk_warning=None,
        )
        kwargs.update(overrides)
        return InvestmentAnalysis(**kwargs)

    return _inner

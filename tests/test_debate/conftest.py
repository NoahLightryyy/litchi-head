"""pytest 共享配置 —— debate 模块测试基座

提供：
1. 所有 debate 测试共享的 fixture（sample_analyses 等）
2. 根 conftest.py 中的共享 fixture 自动继承

用法：
    直接引用 fixture 名称即可，conftest 自动注册：
        async def test_analysis_quality(sample_analyses):
            ...
"""

import pytest

from src.debate.models import AgentAnalysis, DebateInput


@pytest.fixture
def sample_analyses() -> dict[str, AgentAnalysis]:
    """3 位大师的模拟分析结果"""
    return {
        "master.buffett": AgentAnalysis(
            agent_name="master.buffett",
            skill_id="buffett",
            skill_name="巴菲特",
            rating="看涨",
            score=85,
            summary="看好长期价值",
            analysis="该公司具有强大护城河和稳定现金流...",
            key_evidence=["ROE连续5年>15%", "资产负债率<40%"],
            confidence=0.85,
        ),
        "master.munger": AgentAnalysis(
            agent_name="master.munger",
            skill_id="munger",
            skill_name="芒格",
            rating="中性",
            score=55,
            summary="需谨慎看待",
            analysis="当前估值偏高，但基本面尚可...",
            key_evidence=["PE处于历史高位", "行业竞争加剧"],
            confidence=0.6,
        ),
        "master.graham": AgentAnalysis(
            agent_name="master.graham",
            skill_id="graham",
            skill_name="格雷厄姆",
            rating="看涨",
            score=70,
            summary="安全边际充足",
            analysis="股价低于内在价值约20%，存在安全边际...",
            key_evidence=["市净率<1.5", "股息率>3%"],
            confidence=0.7,
        ),
    }


@pytest.fixture
def sample_debate_input() -> DebateInput:
    """创建标准的辩论输入"""
    return DebateInput(
        stock_code="000001",
        stock_name="平安银行",
        question="是否值得投资？",
        context={"news": "今日股市震荡上行"},
    )

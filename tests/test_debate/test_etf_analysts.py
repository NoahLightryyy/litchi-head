from src.debate.analysts import get_default_analysts
from src.debate.etf_analysts import ETF_SCOPE_PROMPT, get_etf_analysts


def test_etf_reuses_full_analyst_team_without_mutating_stock_personas():
    before = [item.model_dump() for item in get_default_analysts()]
    personas = get_etf_analysts()
    assert [item.analyst_type for item in personas] == [item["analyst_type"] for item in before]
    assert len(personas) == 5
    assert [item.model_dump() for item in get_default_analysts()] == before
    assert personas[0].name == "基金结构与主题分析师"
    assert "财务健康 ——" not in personas[0].system_prompt
    assert "基金结构与主题暴露" in personas[0].system_prompt


def test_every_etf_role_retains_missing_data_and_price_basis_limits():
    for persona in get_etf_analysts():
        assert ETF_SCOPE_PROMPT in persona.system_prompt
        assert "市场价格不等于基金净值" in persona.system_prompt
        assert "主题关键词命中不证明实际持仓" in persona.system_prompt
        assert "未复权" in persona.system_prompt
        assert "5-10%" not in persona.system_prompt

"""分析师人格定义单元测试

DP-005: 测试灵感官（Inspiration）分析师的存在和 prompt 完整性。
"""

from src.debate.analysts import get_default_analysts


class TestGetDefaultAnalysts:
    """get_default_analysts 单元测试"""

    def test_returns_5_analysts(self):
        """默认分析师含 5 位（含 DP-005 灵感官）"""
        analysts = get_default_analysts()
        assert len(analysts) == 5

    def test_includes_inspiration_analyst(self):
        """应包含灵感官（inspiration）"""
        analysts = get_default_analysts()
        types = {p.analyst_type for p in analysts}
        assert "inspiration" in types

    def test_inspiration_prompt_contains_contrarian_keywords(self):
        """灵感官 prompt 应包含反共识关键词"""
        analysts = get_default_analysts()
        insp = [p for p in analysts if p.analyst_type == "inspiration"][0]
        prompt = insp.system_prompt
        assert "反共识" in prompt
        assert "质疑" in prompt
        assert "跨界" in prompt or "联想" in prompt

    def test_inspiration_name(self):
        """灵感官显示名称正确"""
        analysts = get_default_analysts()
        insp = [p for p in analysts if p.analyst_type == "inspiration"][0]
        assert "反共识" in insp.name

    def test_all_analysts_have_required_fields(self):
        """每位分析师必须包含所有必需字段"""
        analysts = get_default_analysts()
        for p in analysts:
            assert p.analyst_type, f"分析师 {p.name} 缺少 analyst_type"
            assert p.name, "分析师名称不能为空"
            assert p.system_prompt, f"分析师 {p.name} 缺少 system_prompt"

    def test_all_analysts_types_unique(self):
        """分析师类型必须唯一"""
        analysts = get_default_analysts()
        types = [p.analyst_type for p in analysts]
        assert len(types) == len(set(types))

    def test_default_order(self):
        """默认顺序正确"""
        analysts = get_default_analysts()
        expected_order = ["fundamental", "technical", "sentiment", "macro", "inspiration"]
        actual_order = [p.analyst_type for p in analysts]
        assert actual_order == expected_order

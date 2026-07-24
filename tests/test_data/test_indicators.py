"""PD 动态指标体系单元测试

测试覆盖：
1. 行业名称归一化（normalize_industry）
2. 产业链位置分类（classify_chain_position）
3. 注册表数据完整性（REGISTRY 所有行业都有指标）
4. 全链路选择器（DynamicIndicatorSelector.for_stock）
5. DataCollector 新方法（get_stock_industry, get_stock_chain_position, get_dynamic_indicators）
6. 异常路径（网络错误、空数据、未知行业）
"""

import pytest

from src.data.indicators.registry import (
    INDICATOR_DEFS_MAP,
    REGISTRY,
    SHENWAN_SECTORS,
    IndustryChainPosition,
    classify_chain_position,
    normalize_industry,
)
from src.data.indicators.selector import DynamicIndicatorSelector

# ═══════════════════════════════════════════════════════════════════════
# 行业名称归一化
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizeIndustry:
    def test_normalize_bank_level2(self):
        """银行Ⅱ → 银行"""
        assert normalize_industry("银行Ⅱ") == "银行"

    def test_normalize_baijiu_level2(self):
        """白酒Ⅱ → 食品饮料"""
        assert normalize_industry("白酒Ⅱ") == "食品饮料"

    def test_normalize_coal_mining(self):
        """煤炭开采 → 煤炭"""
        assert normalize_industry("煤炭开采") == "煤炭"

    def test_normalize_semiconductor(self):
        """半导体 → 电子"""
        assert normalize_industry("半导体") == "电子"

    def test_normalize_hospital_level3(self):
        """股份制银行Ⅲ → 银行"""
        assert normalize_industry("股份制银行Ⅲ") == "银行"

    def test_normalize_unknown_returns_raw(self):
        """未知行业名返回原值"""
        assert normalize_industry("不存在的行业") == "不存在的行业"

    def test_normalize_31_level1_self_mapping(self):
        """31 个一级行业自身映射不变"""
        for sector in SHENWAN_SECTORS:
            assert normalize_industry(sector) == sector


# ═══════════════════════════════════════════════════════════════════════
# 产业链位置分类
# ═══════════════════════════════════════════════════════════════════════


class TestChainPosition:
    def test_bank_is_financial(self):
        """银行 → financial"""
        assert classify_chain_position("银行") == IndustryChainPosition.FINANCIAL

    def test_coal_is_upstream(self):
        """煤炭 → upstream"""
        assert classify_chain_position("煤炭") == IndustryChainPosition.UPSTREAM

    def test_electronics_is_midstream(self):
        """电子 → midstream"""
        assert classify_chain_position("电子") == IndustryChainPosition.MIDSTREAM

    def test_food_is_downstream(self):
        """食品饮料 → downstream"""
        assert classify_chain_position("食品饮料") == IndustryChainPosition.DOWNSTREAM

    def test_unknown_is_other(self):
        """未知行业 → other"""
        assert classify_chain_position("不存在的行业") == IndustryChainPosition.OTHER

    def test_all_sectors_have_position(self):
        """全部 31 个一级行业都有产业链位置映射"""
        from src.data.indicators.registry import INDUSTRY_CHAIN_MAP

        for sector in REGISTRY:
            assert sector in INDUSTRY_CHAIN_MAP, f"{sector} 缺少产业链位置"


# ═══════════════════════════════════════════════════════════════════════
# 注册表数据完整性
# ═══════════════════════════════════════════════════════════════════════


class TestRegistry:
    def test_all_sectors_have_indicators(self):
        """所有注册的行业都有 >0 个指标"""
        for sector, ids in REGISTRY.items():
            assert len(ids) >= 5, f"{sector} 只有 {len(ids)} 个指标（最少 5 个）"

    def test_all_indicators_have_definition(self):
        """所有指标 ID 都有展开定义"""
        for sector, ids in REGISTRY.items():
            for iid in ids:
                assert iid in INDICATOR_DEFS_MAP, (
                    f"{sector} 的指标 {iid} 缺少 IndicatorDef 定义"
                )

    def test_indicator_ids_fit_available_fields(self):
        """所有指标 ID 对应的 field 都在 FinancialMetrics 或 ValuationMetrics 中"""
        valid_fields = {
            # FinancialMetrics 字段
            "eps", "book_value_per_share", "operating_cf_per_share",
            "roe", "roa", "gross_margin", "net_profit_margin",
            "revenue_growth", "net_profit_growth",
            "debt_ratio", "current_ratio", "quick_ratio",
            "inventory_turnover", "asset_turnover",
            "total_assets", "operating_revenue",
            # ValuationMetrics 字段（由 DataCollector 提供）
            "pe", "pb", "ps",
        }
        for sector, ids in REGISTRY.items():
            for iid in ids:
                field = INDICATOR_DEFS_MAP[iid].field
                assert field in valid_fields, (
                    f"{sector} 的指标 {iid} 字段 {field} 不在有效字段集合中"
                )

    def test_registry_has_31_sectors(self):
        """注册表包含约 31 个一级行业"""
        assert len(REGISTRY) >= 28, f"注册表只有 {len(REGISTRY)} 个行业，预期约 31"
        assert len(REGISTRY) <= 33


# ═══════════════════════════════════════════════════════════════════════
# 选择器全链路
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_selector(mock_empty_cache):
    """使用 mock_empty_cache 的 DataSource 创建选择器"""
    return DynamicIndicatorSelector(source=mock_empty_cache._source)


class TestSelector:
    def test_ping_an_bank_full_chain(self, mock_selector):
        """平安银行 → 银行 → financial → [pe, pb, roe, ...]"""
        result = mock_selector.for_stock("000001")
        assert result.industry == "银行"
        assert result.chain_position == IndustryChainPosition.FINANCIAL
        assert "pe" in result.indicator_ids
        assert "pb" in result.indicator_ids
        assert "roe" in result.indicator_ids
        assert "gross_margin" not in result.indicator_ids  # 银行不看毛利率
        assert "inventory_turnover" not in result.indicator_ids  # 银行不看存货

    def test_kweichow_moutai_full_chain(self, mock_selector):
        """贵州茅台 → 食品饮料 → downstream → [pe, roe, gross_margin, ...]"""
        result = mock_selector.for_stock("600519")
        assert result.industry == "食品饮料"
        assert result.chain_position == IndustryChainPosition.DOWNSTREAM
        assert "gross_margin" in result.indicator_ids
        assert "net_profit_margin" in result.indicator_ids

    def test_vanke_full_chain(self, mock_selector):
        """万科A → 房地产 → downstream → [pe, pb, debt_ratio, ...]"""
        result = mock_selector.for_stock("000002")
        assert result.industry == "房地产"
        assert "debt_ratio" in result.indicator_ids
        assert "current_ratio" in result.indicator_ids

    def test_unknown_stock_returns_empty(self, mock_selector):
        """未知行业的股票返回基本结果"""
        result = mock_selector.for_stock("999999")
        assert result.stock_code == "999999"
        assert result.industry == ""
        assert result.indicator_ids == []

    def test_indicator_defs_expanded(self, mock_selector):
        """所有指标都有完整定义"""
        result = mock_selector.for_stock("000001")
        assert len(result.indicator_defs) == len(result.indicator_ids)
        assert all(d.id in result.indicator_ids for d in result.indicator_defs)
        assert all(d.name for d in result.indicator_defs)

    def test_indicator_defs_have_all_fields(self, mock_selector):
        """指标定义包含完整描述信息"""
        result = mock_selector.for_stock("000001")
        for d in result.indicator_defs:
            assert d.description, f"{d.id} 缺少 description"
            assert d.unit, f"{d.id} 缺少 unit"


# ═══════════════════════════════════════════════════════════════════════
# DataCollector 集成测试
# ═══════════════════════════════════════════════════════════════════════


class TestDataCollectorIndicators:
    def test_get_stock_industry_pingan(self, collector):
        """get_stock_industry 返回原始行业名"""
        result = collector.get_stock_industry("000001")
        assert result == "银行Ⅱ"

    def test_get_stock_industry_moutai(self, collector):
        """贵州茅台 → 白酒Ⅱ"""
        result = collector.get_stock_industry("600519")
        assert result == "白酒Ⅱ"

    def test_get_stock_industry_unknown(self, collector):
        """未知代码 → None"""
        result = collector.get_stock_industry("999999")
        assert result is None

    def test_chain_position_pingan(self, collector):
        """平安银行 → financial"""
        result = collector.get_stock_chain_position("000001")
        assert result == "financial"

    def test_chain_position_moutai(self, collector):
        """贵州茅台 → downstream"""
        result = collector.get_stock_chain_position("600519")
        assert result == "downstream"

    def test_chain_position_unknown(self, collector):
        """未知代码 → other"""
        result = collector.get_stock_chain_position("999999")
        assert result == "other"

    def test_dynamic_indicators_pingan(self, collector):
        """平安银行动态指标 — 含行业/位置/指标列表"""
        result = collector.get_dynamic_indicators("000001")
        assert result["industry"] == "银行"
        assert result["chain_position"] == "financial"
        assert "pe" in result["indicator_ids"]
        assert "pb" in result["indicator_ids"]
        assert len(result["indicators"]) == len(result["indicator_ids"])

    def test_dynamic_indicators_unknown(self, collector):
        """未知代码动态指标为空"""
        result = collector.get_dynamic_indicators("999999")
        assert result["industry"] == ""
        assert result["chain_position"] == "other"
        assert result["indicator_ids"] == []

    def test_network_error_returns_none(self, failing_collector):
        """网络异常时 get_stock_industry 返回 None"""
        result = failing_collector.get_stock_industry("000001")
        assert result is None

    def test_network_error_chain_position(self, failing_collector):
        """网络异常时 get_stock_chain_position 返回 other"""
        result = failing_collector.get_stock_chain_position("000001")
        assert result == "other"


# ═══════════════════════════════════════════════════════════════════════
# SelectorResult 模型
# ═══════════════════════════════════════════════════════════════════════


class TestSelectorResult:
    def test_selector_result_defaults(self):
        """SelectorResult 默认值"""
        from src.data.indicators.selector import SelectorResult

        result = SelectorResult(stock_code="000001")
        assert result.industry == ""
        assert result.chain_position == IndustryChainPosition.OTHER
        assert result.indicator_ids == []
        assert result.indicator_defs == []

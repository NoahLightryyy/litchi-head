"""数据模型单元测试（TD-004 追认 — data 模块）"""

import pytest
from pydantic import ValidationError

from src.data.models import (
    BoardInfo,
    FinancialMetrics,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
    ValuationMetrics,
)


class TestStockInfo:
    def test_create_with_required_fields(self):
        info = StockInfo(code="000001", name="平安银行")
        assert info.code == "000001"
        assert info.name == "平安银行"
        assert info.market == ""

    def test_missing_code_raises(self):
        with pytest.raises(ValidationError):
            StockInfo(name="平安银行")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            StockInfo(code="000001")

    def test_serialization(self):
        info = StockInfo(code="600519", name="贵州茅台", market="SH")
        data = info.model_dump()
        assert data["code"] == "600519"
        assert data["name"] == "贵州茅台"
        assert data["market"] == "SH"

    def test_deserialization(self):
        data = {"code": "000001", "name": "平安银行", "market": "SZ"}
        info = StockInfo.model_validate(data)
        assert info.code == "000001"
        assert info.name == "平安银行"


class TestStockQuote:
    def test_create_with_required_fields(self):
        q = StockQuote(
            code="000001", name="平安银行", price=12.5,
            change=0.3, change_pct=2.46, volume=100000,
            amount=1.25e7,
        )
        assert q.code == "000001"
        assert q.price == 12.5
        assert q.change_pct == 2.46
        assert q.high == 0  # 默认值

    def test_missing_amount_ok(self):
        q = StockQuote(
            code="000001", name="平安银行", price=12.5,
            change=0.3, change_pct=2.46, volume=100000,
        )
        assert q.amount == 0.0

    def test_type_enforcement(self):
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="平安银行", price="invalid",
                change=0.3, change_pct=2.46, volume=100000,
            )

    def test_serialization_roundtrip(self):
        q = StockQuote(
            code="000001", name="平安银行", price=12.5,
            change=0.3, change_pct=2.46, volume=100000,
        )
        data = q.model_dump()
        assert data["change_pct"] == 2.46
        restored = StockQuote.model_validate(data)
        assert restored.price == q.price


class TestKLine:
    def test_create_with_required_fields(self):
        k = KLine(date="2026-06-05", open=12.0, close=12.5, high=12.8, low=11.9, volume=50000)
        assert k.date == "2026-06-05"
        assert k.close == 12.5
        assert k.amount == 0  # 默认值

    def test_missing_date_raises(self):
        with pytest.raises(ValidationError):
            KLine(open=12.0, close=12.5, high=12.8, low=11.9, volume=50000)

    def test_type_enforcement(self):
        with pytest.raises(ValidationError):
            KLine(date="2026-06-05", open=12.0, close=12.5, high=12.8, low=11.9, volume="lots")


class TestNewsItem:
    def test_create_with_required_fields(self):
        n = NewsItem(code="000001", title="平安银行发布年报", date="2026-06-05")
        assert n.code == "000001"
        assert n.title == "平安银行发布年报"
        assert n.content == ""  # 默认值
        assert n.source == ""

    def test_with_all_fields(self):
        n = NewsItem(
            code="000001", title="年报", date="2026-06-05",
            content="内容...", source="东方财富",
            url="http://example.com",
        )
        assert n.source == "东方财富"
        assert n.url == "http://example.com"


class TestBoardInfo:
    def test_industry_board(self):
        b = BoardInfo(code="BK0444", name="银行", board_type="industry")
        assert b.board_type == "industry"

    def test_concept_board(self):
        b = BoardInfo(code="BK0896", name="人工智能", board_type="concept")
        assert b.board_type == "concept"

    def test_invalid_board_type(self):
        with pytest.raises(ValidationError):
            BoardInfo(code="BK0001", name="测试", board_type="invalid")


class TestEdgeCases:
    """边界条件测试 — 负值/零值/极值"""

    def test_stock_quote_negative_price(self):
        """负价格应被拒绝"""
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="测试", price=-1.0,
                change=0.0, change_pct=0.0, volume=1000,
            )

    def test_stock_quote_negative_volume(self):
        """负交易量应被拒绝"""
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="测试", price=10.0,
                change=0.0, change_pct=0.0, volume=-100,
            )

    def test_stock_quote_zero_price(self):
        """零价格允许（停牌/退市股）"""
        q = StockQuote(
            code="000001", name="测试", price=0.0,
            change=0.0, change_pct=0.0, volume=1000,
        )
        assert q.price == 0.0

    def test_stock_quote_zero_volume(self):
        """零交易量应允许（停牌股）"""
        q = StockQuote(
            code="000001", name="测试", price=10.0,
            change=0.0, change_pct=0.0, volume=0,
        )
        assert q.volume == 0

    def test_stock_quote_negative_amount(self):
        """负成交额应被拒绝"""
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="测试", price=10.0,
                change=0.0, change_pct=0.0, volume=1000,
                amount=-1.0,
            )

    def test_kline_negative_close(self):
        """负收盘价应被拒绝"""
        with pytest.raises(ValidationError):
            KLine(date="2026-06-05", open=10.0, close=-1.0, high=10.0, low=10.0, volume=1000)

    def test_kline_high_less_than_low(self):
        """最高价 < 最低价应被拒绝"""
        with pytest.raises(ValidationError):
            KLine(date="2026-06-05", open=10.0, close=10.0, high=9.0, low=11.0, volume=1000)

    def test_kline_open_outside_range(self):
        """开盘价超出 [low, high] 区间应被拒绝"""
        with pytest.raises(ValidationError):
            KLine(date="2026-06-05", open=15.0, close=10.0, high=12.0, low=9.0, volume=1000)


class TestFinancialMetrics:
    """财务指标模型测试"""

    def test_create_with_required_fields(self):
        """仅必需字段构造"""
        fm = FinancialMetrics(stock_code="000001", report_date="2024-12-31")
        assert fm.stock_code == "000001"
        assert fm.report_date == "2024-12-31"
        assert fm.eps == 0.0  # 默认值

    def test_default_values(self):
        """所有 float 字段默认 0.0"""
        fm = FinancialMetrics(stock_code="000001", report_date="2024-12-31")
        for field_name in FinancialMetrics.model_fields:
            field_info = FinancialMetrics.model_fields[field_name]
            if field_info.annotation in (float,):
                assert getattr(fm, field_name) == 0.0, f"{field_name} 应默认为 0.0"

    def test_negative_eps_allowed(self):
        """EPS 允许负值（亏损公司）"""
        fm = FinancialMetrics(stock_code="000001", report_date="2024-12-31", eps=-0.5)
        assert fm.eps == -0.5

    def test_negative_operating_cf_allowed(self):
        """经营性现金流允许负值"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            operating_cf_per_share=-0.3,
        )
        assert fm.operating_cf_per_share == -0.3

    def test_negative_operating_revenue_allowed(self):
        """主营业务利润允许负值"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            operating_revenue=-1e8,
        )
        assert fm.operating_revenue == -1e8

    def test_negative_growth_allowed(self):
        """增长率允许负值"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            revenue_growth=-10.5, net_profit_growth=-20.3,
        )
        assert fm.revenue_growth == -10.5
        assert fm.net_profit_growth == -20.3

    def test_negative_debt_ratio_rejected(self):
        """资产负债率 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                debt_ratio=-1.0,
            )

    def test_debt_ratio_over_100_rejected(self):
        """资产负债率 > 100 应被拒绝（超过 100% 不合理）"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                debt_ratio=101.0,
            )

    def test_debt_ratio_boundary_allowed(self):
        """资产负债率边界值允许"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            debt_ratio=0.0,  # 无负债
        )
        assert fm.debt_ratio == 0.0
        fm2 = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            debt_ratio=100.0,  # 资不抵债
        )
        assert fm2.debt_ratio == 100.0

    def test_negative_book_value_rejected(self):
        """每股净资产 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                book_value_per_share=-1.0,
            )

    def test_negative_current_ratio_rejected(self):
        """流动比率 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                current_ratio=-0.5,
            )

    def test_negative_asset_turnover_rejected(self):
        """总资产周转率 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                asset_turnover=-0.1,
            )

    def test_negative_inventory_turnover_rejected(self):
        """存货周转率 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                inventory_turnover=-0.1,
            )

    def test_negative_total_assets_rejected(self):
        """总资产 < 0 应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                total_assets=-1.0,
            )

    def test_serialization_roundtrip(self):
        """序列化往返一致"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            eps=1.5, book_value_per_share=20.0,
            roe=15.0, gross_margin=45.0,
            debt_ratio=50.0, current_ratio=2.0,
            revenue_growth=10.0, net_profit_growth=8.0,
            total_assets=1e12,
        )
        data = fm.model_dump()
        restored = FinancialMetrics.model_validate(data)
        assert restored.eps == fm.eps
        assert restored.roe == fm.roe
        assert restored.debt_ratio == fm.debt_ratio
        assert restored.total_assets == 1e12

    def test_type_enforcement(self):
        """类型错误应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(
                stock_code="000001", report_date="2024-12-31",
                eps="invalid",  # str 而不是 float
            )

    def test_missing_stock_code_raises(self):
        """缺少股票代码应被拒绝"""
        with pytest.raises(ValidationError):
            FinancialMetrics(report_date="2024-12-31")  # type: ignore[call-arg]

    def test_missing_report_date_defaults_empty(self):
        """缺少报告期时默认为空字符串"""
        fm = FinancialMetrics(stock_code="000001")
        assert fm.report_date == ""

    def test_all_fields_constructable(self):
        """全字段构造验证"""
        fm = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            eps=2.5,
            book_value_per_share=25.0,
            operating_cf_per_share=3.2,
            roe=15.0,
            roa=8.0,
            gross_margin=55.0,
            net_profit_margin=20.0,
            revenue_growth=12.0,
            net_profit_growth=10.0,
            debt_ratio=42.5,
            current_ratio=2.5,
            quick_ratio=1.8,
            inventory_turnover=5.0,
            asset_turnover=0.8,
            total_assets=2e12,
            operating_revenue=5e10,
        )
        assert fm.eps == 2.5
        assert fm.book_value_per_share == 25.0
        assert fm.roe == 15.0
        assert fm.debt_ratio == 42.5
        assert fm.total_assets == 2e12


class TestValuationMetrics:
    """估值比率模型测试"""

    def test_create_with_required_fields(self):
        """仅必需字段构造"""
        vm = ValuationMetrics(stock_code="000001")
        assert vm.stock_code == "000001"
        assert vm.pe == 0.0
        assert vm.pb == 0.0
        assert vm.ps == 0.0
        assert vm.market_cap == 0.0
        assert vm.report_date == ""

    def test_create_with_all_fields(self):
        """全字段构造"""
        vm = ValuationMetrics(
            stock_code="000001", report_date="2024-12-31",
            pe=10.5, pb=1.2, ps=0.8, market_cap=2.5e11,
        )
        assert vm.pe == 10.5
        assert vm.pb == 1.2
        assert vm.ps == 0.8
        assert vm.market_cap == 2.5e11

    def test_negative_values_rejected(self):
        """所有比率字段 ge=0，负值应拒绝"""
        with pytest.raises(ValidationError):
            ValuationMetrics(stock_code="000001", pe=-1.0)
        with pytest.raises(ValidationError):
            ValuationMetrics(stock_code="000001", pb=-1.0)
        with pytest.raises(ValidationError):
            ValuationMetrics(stock_code="000001", ps=-0.1)
        with pytest.raises(ValidationError):
            ValuationMetrics(stock_code="000001", market_cap=-1.0)

    def test_zero_allowed(self):
        """零值允许（亏损公司或无数据）"""
        vm = ValuationMetrics(stock_code="000001", pe=0.0, pb=0.0)
        assert vm.pe == 0.0
        assert vm.pb == 0.0
        assert vm.ps == 0.0

    def test_serialization_roundtrip(self):
        """序列化往返一致"""
        vm = ValuationMetrics(
            stock_code="000001", report_date="2024-12-31",
            pe=10.5, pb=1.2, ps=0.8, market_cap=2.5e11,
        )
        data = vm.model_dump()
        restored = ValuationMetrics.model_validate(data)
        assert restored.pe == vm.pe
        assert restored.pb == vm.pb
        assert restored.market_cap == 2.5e11

    def test_stock_quote_market_cap_defaults_zero(self):
        """StockQuote.market_cap 默认 0.0（向后兼容）"""
        q = StockQuote(
            code="000001", name="平安银行", price=12.5,
            change=0.3, change_pct=2.46, volume=100000,
        )
        assert q.market_cap == 0.0

    def test_stock_quote_negative_market_cap_rejected(self):
        """StockQuote.market_cap < 0 应拒绝"""
        with pytest.raises(ValidationError):
            StockQuote(
                code="000001", name="平安银行", price=12.5,
                change=0.3, change_pct=2.46, volume=100000,
                market_cap=-1.0,
            )

    def test_pepb_known_values(self):
        """已知输入的正确计算验证"""
        # 股价 25, EPS 2.5 → PE = 10.0
        # 股价 25, BVPS 10 → PB = 2.5
        vm = ValuationMetrics(
            stock_code="000001",
            pe=25.0 / 2.5,   # 10.0
            pb=25.0 / 10.0,   # 2.5
        )
        assert vm.pe == 10.0
        assert vm.pb == 2.5

    def test_type_enforcement(self):
        """类型错误应拒绝"""
        with pytest.raises(ValidationError):
            ValuationMetrics(stock_code="000001", pe="invalid")

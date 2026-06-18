"""数据模型单元测试（TD-004 追认 — data 模块）"""

import pytest
from pydantic import ValidationError

from src.data.models import BoardInfo, KLine, NewsItem, StockInfo, StockQuote


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

"""契约测试 —— data → debate 数据流

验证 data 模块输出的 Pydantic 模型能被 debate 模块正确消费。
当 data/models.py 字段变更时，此测试首先失败，阻止跨模块静默破坏。

测试范围（TD-059）：
1. 数据模型 JSON 序列化/反序列化（round-trip）
2. format_market_brief 接收 data 模块输出
3. 字段完整性：debate 依赖的字段必须存在
"""

from __future__ import annotations

from src.data.collector import format_market_brief
from src.data.models import KLine, NewsItem, StockQuote


class TestDataToDebateContract:
    """data → debate 双向契约验证"""

    def test_stockquote_json_roundtrip(self):
        """StockQuote JSON 序列化/反序列化不丢字段"""
        original = StockQuote(
            code="000001",
            name="平安银行",
            price=12.34,
            change=0.25,
            change_pct=2.05,
            volume=1000000,
            amount=12340000.0,
            high=12.50,
            low=12.20,
            open_=12.30,
            prev_close=12.09,
        )
        json_str = original.model_dump_json()
        restored = StockQuote.model_validate_json(json_str)

        assert restored.code == original.code
        assert restored.name == original.name
        assert restored.price == original.price
        assert restored.change == original.change
        assert restored.change_pct == original.change_pct
        assert restored.volume == original.volume

    def test_kline_json_roundtrip(self):
        """KLine JSON 序列化/反序列化不丢字段"""
        original = KLine(
            date="2026-06-18",
            open=12.00,
            close=12.50,
            high=12.60,
            low=11.90,
            volume=2000000,
            amount=25000000.0,
        )
        json_str = original.model_dump_json()
        restored = KLine.model_validate_json(json_str)

        assert restored.date == original.date
        assert restored.open == original.open
        assert restored.close == original.close
        assert restored.high == original.high
        assert restored.low == original.low
        assert restored.volume == original.volume
        assert restored.amount == original.amount

    def test_newsitem_json_roundtrip(self):
        """NewsItem JSON 序列化/反序列化不丢字段"""
        original = NewsItem(
            code="000001",
            title="平安银行发布2026年中期业绩",
            date="2026-06-18",
            content="平安银行今日发布中期业绩，净利润同比增长15%...",
            source="东方财富",
            url="https://example.com/news/123",
        )
        json_str = original.model_dump_json()
        restored = NewsItem.model_validate_json(json_str)

        assert restored.code == original.code
        assert restored.title == original.title
        assert restored.date == original.date
        assert restored.content == original.content
        assert restored.source == original.source

    def test_format_market_brief_accepts_data_models(self):
        """format_market_brief 接受 data 模块的 StockQuote/KLine/NewsItem"""
        quote = StockQuote(
            code="000001",
            name="平安银行",
            price=12.34,
            change=0.25,
            change_pct=2.05,
            volume=1000000,
            amount=12340000.0,
            high=12.50,
            low=12.20,
            open_=12.30,
            prev_close=12.09,
        )
        klines = [
            KLine(
                date="2026-06-17", open=12.00, close=12.25,
                high=12.30, low=11.95, volume=1_500_000,
            ),
            KLine(
                date="2026-06-18", open=12.25, close=12.50,
                high=12.60, low=12.20, volume=1_800_000,
            ),
        ]
        news = [
            NewsItem(code="000001", title="业绩预告", date="2026-06-18", content="净利润增长"),
        ]

        brief = format_market_brief(
            stock_code="000001",
            stock_name="平安银行",
            quote=quote,
            klines=klines,
            news=news,
        )

        # 验证返回的是非空字符串
        assert isinstance(brief, str)
        assert len(brief) > 0
        # 包含股票名称
        assert "平安银行" in brief
        # 包含价格信息
        assert "12.34" in brief
        # 包含新闻标题
        assert "业绩预告" in brief

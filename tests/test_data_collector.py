"""数据采集器单元测试（mock akshare）"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.data.collector import DataCollector

# ── Mock DataFrames ──────────────────────────────────────────────────

MOCK_STOCKS_DF = pd.DataFrame({
    "code": ["000001", "000002", "600519"],
    "name": ["平安银行", "万科A", "贵州茅台"],
})

MOCK_QUOTES_DF = pd.DataFrame({
    "代码": ["000001", "600519"],
    "名称": ["平安银行", "贵州茅台"],
    "最新价": [12.50, 1880.00],
    "涨跌额": [0.30, -15.00],
    "涨跌幅": [2.46, -0.79],
    "成交量": [1000000, 500000],
    "成交额": [1.25e7, 9.4e8],
    "最高": [12.80, 1900.00],
    "最低": [12.30, 1860.00],
    "今开": [12.40, 1890.00],
    "昨收": [12.20, 1895.00],
})

MOCK_HIST_DF = pd.DataFrame({
    "日期": ["2026-06-05", "2026-06-04", "2026-06-03"],
    "开盘": [12.40, 12.30, 12.10],
    "收盘": [12.50, 12.35, 12.20],
    "最高": [12.80, 12.50, 12.30],
    "最低": [12.30, 12.20, 12.05],
    "成交量": [500000, 450000, 400000],
    "成交额": [6.25e6, 5.58e6, 4.88e6],
})

MOCK_NEWS_DF = pd.DataFrame({
    "title": ["平安银行发布年报", "平安银行数字化转型"],
    "date": ["2026-06-05", "2026-06-04"],
    "content": ["年报内容摘要", "数字化进展"],
    "source": ["东方财富", "证券时报"],
    "url": ["http://example.com/1", "http://example.com/2"],
})

MOCK_BOARDS_DF = pd.DataFrame({
    "板块名称": ["银行", "保险", "证券"],
    "板块代码": ["BK0444", "BK0476", "BK0473"],
})


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def collector():
    return DataCollector()


@pytest.fixture
def mock_empty_cache(collector):
    """确保缓存为空，避免测试间干扰"""
    collector.cache.clear()
    return collector


# ── Tests: get_all_stocks ────────────────────────────────────────────


class TestGetAllStocks:
    def test_returns_stock_info_list(self, mock_empty_cache):
        with patch("akshare.stock_info_a_code_name", return_value=MOCK_STOCKS_DF):
            result = mock_empty_cache.get_all_stocks()
        assert len(result) == 3
        assert result[0].code == "000001"
        assert result[0].name == "平安银行"
        assert result[2].code == "600519"
        assert result[2].name == "贵州茅台"

    def test_network_error_returns_empty(self, mock_empty_cache):
        with patch(
            "akshare.stock_info_a_code_name",
            side_effect=ConnectionError("no network"),
        ):
            result = mock_empty_cache.get_all_stocks()
        assert result == []

    def test_cache_hit_avoids_akshare(self, mock_empty_cache):
        mock_empty_cache.cache.set("all_stocks", [{"code": "cached"}])
        with patch("akshare.stock_info_a_code_name") as mock_ak:
            mock_empty_cache.get_all_stocks()
        mock_ak.assert_not_called()


# ── Tests: get_realtime_quotes ───────────────────────────────────────


class TestGetRealtimeQuotes:
    def test_returns_stock_quote_list(self, mock_empty_cache):
        with patch("akshare.stock_zh_a_spot_em", return_value=MOCK_QUOTES_DF):
            result = mock_empty_cache.get_realtime_quotes()
        assert len(result) == 2
        assert result[0].code == "000001"
        assert result[0].price == 12.50
        assert result[0].change_pct == 2.46

    def test_single_quote_by_code(self, mock_empty_cache):
        with patch("akshare.stock_zh_a_spot_em", return_value=MOCK_QUOTES_DF):
            result = mock_empty_cache.get_realtime_quote("600519")
        assert result is not None
        assert result.code == "600519"
        assert result.price == 1880.00

    def test_single_quote_not_found(self, mock_empty_cache):
        with patch("akshare.stock_zh_a_spot_em", return_value=MOCK_QUOTES_DF):
            result = mock_empty_cache.get_realtime_quote("999999")
        assert result is None

    def test_network_error_returns_empty(self, mock_empty_cache):
        with patch(
            "akshare.stock_zh_a_spot_em",
            side_effect=ConnectionError("no network"),
        ):
            result = mock_empty_cache.get_realtime_quotes()
        assert result == []


# ── Tests: get_klines ────────────────────────────────────────────────


class TestGetKLines:
    def test_returns_kline_list(self, mock_empty_cache):
        with patch("akshare.stock_zh_a_hist", return_value=MOCK_HIST_DF):
            result = mock_empty_cache.get_klines("000001")
        assert len(result) == 3
        assert result[0].date == "2026-06-05"
        assert result[0].close == 12.50
        assert result[1].open == 12.30

    def test_network_error_returns_empty(self, mock_empty_cache):
        with patch(
            "akshare.stock_zh_a_hist",
            side_effect=ConnectionError("no network"),
        ):
            result = mock_empty_cache.get_klines("000001")
        assert result == []


# ── Tests: get_news ──────────────────────────────────────────────────


class TestGetNews:
    def test_returns_news_list(self, mock_empty_cache):
        with patch("akshare.stock_news_em", return_value=MOCK_NEWS_DF):
            result = mock_empty_cache.get_news("000001")
        assert len(result) == 2
        assert result[0].title == "平安银行发布年报"
        assert result[0].source == "东方财富"

    def test_network_error_returns_empty(self, mock_empty_cache):
        with patch(
            "akshare.stock_news_em",
            side_effect=ConnectionError("no network"),
        ):
            result = mock_empty_cache.get_news("000001")
        assert result == []


# ── Tests: boards ────────────────────────────────────────────────────


class TestGetBoards:
    def test_industry_boards(self, mock_empty_cache):
        with patch(
            "akshare.stock_board_industry_name_em",
            return_value=MOCK_BOARDS_DF,
        ):
            result = mock_empty_cache.get_industry_boards()
        assert len(result) == 3
        assert result[0].name == "银行"
        assert result[0].board_type == "industry"

    def test_concept_boards_network_error(self, mock_empty_cache):
        with patch(
            "akshare.stock_board_concept_name_em",
            side_effect=ConnectionError("no network"),
        ):
            result = mock_empty_cache.get_concept_boards()
        assert result == []


# ── Tests: cache integration ─────────────────────────────────────────


class TestCacheIntegration:
    def test_get_all_stocks_caches_result(self, collector):
        collector.cache.clear()
        with patch("akshare.stock_info_a_code_name", return_value=MOCK_STOCKS_DF):
            collector.get_all_stocks()
        assert collector.cache.get("all_stocks") is not None

    def test_different_methods_different_cache_keys(self, collector):
        collector.cache.clear()
        with patch("akshare.stock_info_a_code_name", return_value=MOCK_STOCKS_DF), \
             patch("akshare.stock_zh_a_spot_em", return_value=MOCK_QUOTES_DF):
            stocks = collector.get_all_stocks()
            quotes = collector.get_realtime_quotes()
        assert len(stocks) == 3
        assert len(quotes) == 2


# ── Tests: format_market_brief ─────────────────────────────────────────


class TestFormatMarketBrief:
    """format_market_brief 函数验证"""

    def test_full_data(self):
        """提供完整行情+K线+新闻"""
        from src.data.collector import format_market_brief
        from src.data.models import KLine, NewsItem, StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50, high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35, high=12.50, low=12.20, volume=450000, amount=5.58e6),
            KLine(date="2026-06-03", open=12.10, close=12.20, high=12.30, low=12.05, volume=400000, amount=4.88e6),
        ]
        news = [
            NewsItem(code="000001", title="平安银行发布年报", date="2026-06-05", source="东方财富"),
            NewsItem(code="000001", title="平安银行数字化转型", date="2026-06-04", source="证券时报"),
        ]

        result = format_market_brief(
            stock_code="000001",
            stock_name="平安银行",
            quote=quote,
            klines=klines,
            news=news,
        )

        assert "📊 市场简报 — 平安银行 (000001)" in result
        assert "最新价 12.50 元" in result
        assert "涨幅 +2.46%" in result
        assert "平安银行发布年报" in result
        assert "平安银行数字化转型" in result

    def test_no_data(self):
        """无任何数据"""
        from src.data.collector import format_market_brief

        result = format_market_brief(
            stock_code="000001",
            stock_name="平安银行",
        )

        assert "暂无可用数据" in result

    def test_quote_only(self):
        """仅行情数据（无K线/新闻）"""
        from src.data.collector import format_market_brief
        from src.data.models import StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )

        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote,
        )

        assert "实时行情" in result
        assert "暂无可用数据" not in result

    def test_no_news(self):
        """有行情+K线但无新闻"""
        from src.data.collector import format_market_brief
        from src.data.models import KLine, StockQuote

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50, high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35, high=12.50, low=12.20, volume=450000, amount=5.58e6),
        ]
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote, klines=klines,
        )

        assert "实时行情" in result
        assert "近期走势" in result
        assert "新闻" not in result

    def test_empty_stock_name(self):
        """股票名为空时降级"""
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="")

        assert "000001" in result
        assert "暂无可用数据" in result

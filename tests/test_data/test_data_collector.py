"""数据采集器单元测试（MockDataSource）

注意：
- MockDataSource / MockFailingDataSource 由 tests/test_data/conftest.py 提供
- collector / mock_empty_cache / failing_collector fixture 由 conftest 提供
"""

from unittest.mock import MagicMock

from src.data.models import KLine, NewsItem, StockQuote

# ── Tests: get_all_stocks ────────────────────────────────────────────


class TestGetAllStocks:
    def test_returns_stock_info_list(self, mock_empty_cache):
        result = mock_empty_cache.get_all_stocks()
        assert len(result) == 3
        assert result[0].code == "000001"
        assert result[0].name == "平安银行"
        assert result[2].code == "600519"
        assert result[2].name == "贵州茅台"

    def test_network_error_returns_empty(self, failing_collector):
        result = failing_collector.get_all_stocks()
        assert result == []

    def test_cache_hit_avoids_source_call(self, mock_empty_cache):
        mock_empty_cache.cache.set("all_stocks", [{"code": "cached"}])
        mock_empty_cache._source.get_all_stocks = MagicMock(side_effect=AssertionError("不应调用"))
        mock_empty_cache.get_all_stocks()


# ── Tests: get_realtime_quotes ───────────────────────────────────────


class TestGetRealtimeQuotes:
    def test_returns_stock_quote_list(self, mock_empty_cache):
        result = mock_empty_cache.get_realtime_quotes()
        assert len(result) == 2
        assert result[0].code == "000001"
        assert result[0].price == 12.50
        assert result[0].change_pct == 2.46

    def test_single_quote_by_code(self, mock_empty_cache):
        result = mock_empty_cache.get_realtime_quote("600519")
        assert result is not None
        assert result.code == "600519"
        assert result.price == 1880.00

    def test_single_quote_not_found(self, mock_empty_cache):
        result = mock_empty_cache.get_realtime_quote("999999")
        assert result is None

    def test_network_error_returns_empty(self, failing_collector):
        result = failing_collector.get_realtime_quotes()
        assert result == []


# ── Tests: get_klines ────────────────────────────────────────────────


class TestGetKLines:
    def test_returns_kline_list(self, mock_empty_cache):
        result = mock_empty_cache.get_klines("000001")
        assert len(result) == 3
        assert result[0].date == "2026-06-05"
        assert result[0].close == 12.50
        assert result[1].open == 12.30

    def test_network_error_returns_empty(self, failing_collector):
        result = failing_collector.get_klines("000001")
        assert result == []


# ── Tests: get_news ──────────────────────────────────────────────────


class TestGetNews:
    def test_returns_news_list(self, mock_empty_cache):
        result = mock_empty_cache.get_news("000001")
        assert len(result) == 2
        assert result[0].title == "平安银行发布年报"
        assert result[0].source == "东方财富"

    def test_network_error_returns_empty(self, failing_collector):
        result = failing_collector.get_news("000001")
        assert result == []


# ── Tests: boards ────────────────────────────────────────────────────


class TestGetBoards:
    def test_industry_boards(self, mock_empty_cache):
        result = mock_empty_cache.get_industry_boards()
        assert len(result) == 3
        assert result[0].name == "银行"
        assert result[0].board_type == "industry"

    def test_concept_boards_returns_empty(self, mock_empty_cache):
        result = mock_empty_cache.get_concept_boards()
        assert result == []

    def test_industry_boards_network_error(self, failing_collector):
        result = failing_collector.get_industry_boards()
        assert result == []

    def test_concept_boards_network_error(self, failing_collector):
        result = failing_collector.get_concept_boards()
        assert result == []


# ── Tests: cache integration ─────────────────────────────────────────


class TestCacheIntegration:
    def test_get_all_stocks_caches_result(self, collector):
        collector.cache.clear()
        collector.get_all_stocks()
        assert collector.cache.get("all_stocks") is not None

    def test_different_methods_different_cache_keys(self, collector):
        collector.cache.clear()
        stocks = collector.get_all_stocks()
        quotes = collector.get_realtime_quotes()
        assert len(stocks) == 3
        assert len(quotes) == 2


# ── Tests: format_market_brief ─────────────────────────────────────────


class TestFormatMarketBrief:
    """format_market_brief 函数验证（C1 分区输出）"""

    def test_full_data(self):
        from src.data.collector import format_market_brief

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50,
                  high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35,
                  high=12.50, low=12.20, volume=450000, amount=5.58e6),
            KLine(date="2026-06-03", open=12.10, close=12.20,
                  high=12.30, low=12.05, volume=400000, amount=4.88e6),
        ]
        news = [
            NewsItem(code="000001", title="平安银行发布年报",
                     date="2026-06-05", source="东方财富"),
            NewsItem(code="000001", title="平安银行数字化转型",
                     date="2026-06-04", source="证券时报"),
        ]

        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            quote=quote, klines=klines, news=news,
        )

        assert "📊 市场简报 — 平安银行 (000001)" in result
        assert "最新价 12.50 元" in result
        assert "涨幅 +2.46%" in result
        assert "平安银行发布年报" in result
        assert "平安银行数字化转型" in result

    def test_no_data(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="平安银行")

        assert "暂无行情数据" in result
        assert "暂无新闻数据" in result
        assert "暂无情绪数据" in result
        assert "暂无基本面数据" in result

    def test_quote_only(self):
        from src.data.collector import format_market_brief

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )

        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote,
        )

        assert "----- 行情层 -----" in result
        assert "暂无新闻数据" in result

    def test_no_news(self):
        from src.data.collector import format_market_brief

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        klines = [
            KLine(date="2026-06-05", open=12.40, close=12.50,
                  high=12.80, low=12.30, volume=500000, amount=6.25e6),
            KLine(date="2026-06-04", open=12.30, close=12.35,
                  high=12.50, low=12.20, volume=450000, amount=5.58e6),
        ]
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote, klines=klines,
        )

        assert "----- 行情层 -----" in result
        assert "最新价 12.50" in result
        assert "暂无新闻数据" in result

    def test_empty_stock_name(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="")

        assert "📊 市场简报 — 000001" in result
        assert "暂无行情数据" in result

    def test_partition_has_four_zones(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="平安银行")

        assert "----- 行情层 -----" in result
        assert "----- 新闻层 -----" in result
        assert "----- 情绪层 -----" in result
        assert "----- 基本面层 -----" in result

    def test_partition_sentiment_placeholder(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="平安银行")
        lines = result.splitlines()
        idx = None
        for i, line in enumerate(lines):
            if "----- 情绪层 -----" in line:
                idx = i
                break
        assert idx is not None
        for j in range(idx + 1, len(lines)):
            if lines[j].strip():
                assert "暂无情绪数据" in lines[j]
                break

    def test_partition_fundamentals_placeholder(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="平安银行")
        lines = result.splitlines()
        idx = None
        for i, line in enumerate(lines):
            if "----- 基本面层 -----" in line:
                idx = i
                break
        assert idx is not None
        for j in range(idx + 1, len(lines)):
            if lines[j].strip():
                assert "暂无基本面数据" in lines[j]
                break

    def test_partition_news_section(self):
        from src.data.collector import format_market_brief
        from src.data.models import NewsItem

        news = [NewsItem(code="000001", title="测试新闻标题", date="2026-06-16")]
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", news=news,
        )

        lines = result.splitlines()
        in_news = False
        found_title = False
        for line in lines:
            if "----- 新闻层 -----" in line:
                in_news = True
                continue
            if in_news and "-----" in line:
                break
            if in_news and "测试新闻标题" in line:
                found_title = True
                break

        assert found_title, "新闻标题应在新闻层区段内"

    def test_partition_quotes_section(self):
        from src.data.collector import format_market_brief

        quote = StockQuote(
            code="000001", name="平安银行", price=12.50,
            change_pct=2.46, volume=1000000, change=0.30, amount=1.25e7,
            high=12.80, low=12.30, open_=12.40, prev_close=12.20,
        )
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行", quote=quote,
        )

        assert "涨幅 +2.46%" in result
        assert "成交量 1,000,000 手" in result

    def test_partition_visual_separator(self):
        from src.data.collector import format_market_brief

        result = format_market_brief(stock_code="000001", stock_name="平安银行")

        assert "━" * 35 in result
        lines = result.splitlines()
        header_idx = None
        sep_idx = None
        for i, line in enumerate(lines):
            if "📊 市场简报" in line:
                header_idx = i
            if "━" in line and "市场简报" not in line:
                sep_idx = i
                break
        assert header_idx is not None
        assert sep_idx is not None
        assert sep_idx == header_idx + 1, "分隔线应紧跟在标题后"

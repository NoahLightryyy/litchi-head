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

    # ── FD-001e: 基本面真实数据 ─────────────────────────────────────

    def test_with_financials_shows_report_date(self):
        """财务数据应显示最新报告期"""
        from src.data.collector import format_market_brief
        from src.data.models import FinancialMetrics

        fin = FinancialMetrics(stock_code="000001", report_date="2024-12-31", eps=1.25)
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[fin],
        )

        assert "最新报告期: 2024-12-31" in result
        assert "EPS 1.2500" in result

    def test_with_financials_all_dimensions(self):
        """全量财务数据应输出6大维度"""
        from src.data.collector import format_market_brief
        from src.data.models import FinancialMetrics

        fin = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            eps=1.25, book_value_per_share=18.50, operating_cf_per_share=2.10,
            roe=12.5, roa=5.2, gross_margin=45.8, net_profit_margin=18.3,
            revenue_growth=8.5, net_profit_growth=15.2,
            debt_ratio=55.0, current_ratio=1.8, quick_ratio=1.2,
            inventory_turnover=4.5, asset_turnover=0.85,
            total_assets=5_000_000_000_000, operating_revenue=150_000_000_000,
        )
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[fin],
        )

        # 每股指标
        assert "📊 每股指标:" in result
        assert "EPS 1.2500" in result
        assert "每股净资产 18.50" in result
        assert "每股经营现金流 2.10" in result

        # 盈利能力
        assert "📈 盈利能力:" in result
        assert "ROE 12.50%" in result
        assert "ROA 5.20%" in result
        assert "毛利率 45.80%" in result
        assert "净利率 18.30%" in result

        # 增长能力
        assert "🚀 增长能力:" in result
        assert "营收增长 +8.50%" in result
        assert "净利润增长 +15.20%" in result

        # 财务健康
        assert "🛡️ 财务健康:" in result
        assert "资产负债率 55.0%" in result
        assert "流动比率 1.80" in result
        assert "速动比率 1.20" in result

        # 运营效率
        assert "⚙️ 运营效率:" in result
        assert "存货周转率 4.50" in result
        assert "总资产周转率 0.85" in result

        # 规模(除以1亿)
        assert "🏢 规模:" in result
        assert "总资产 50000.00 亿元" in result
        assert "主营利润 1500.00 亿元" in result

    def test_with_financials_empty_list(self):
        """空列表应回退到暂无基本面数据"""
        from src.data.collector import format_market_brief

        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[],
        )

        assert "暂无基本面数据" in result

    def test_with_financials_all_zero(self):
        """全零财务数据应仅显示报告期"""
        from src.data.collector import format_market_brief
        from src.data.models import FinancialMetrics

        fin = FinancialMetrics(
            stock_code="000001", report_date="2024-09-30",
        )
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[fin],
        )

        assert "最新报告期: 2024-09-30" in result
        # 不应有维度标题行
        assert "📊 每股指标:" not in result
        assert "📈 盈利能力:" not in result
        assert "暂无基本面数据" not in result  # 仍有报告期，不算"无数据"

    def test_with_financials_partial(self):
        """部分字段为0时应跳过0值维度行"""
        from src.data.collector import format_market_brief
        from src.data.models import FinancialMetrics

        fin = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            eps=0.00, roe=15.0, debt_ratio=45.0,  # EPS=0, ROE有值, 负债率有值
        )
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[fin],
        )

        # ROE和负债率应显示
        assert "ROE 15.00%" in result
        assert "资产负债率 45.0%" in result
        # EPS=0 不应在结果显示
        assert "EPS 0.00" not in result

    def test_with_financials_negative_growth(self):
        """负增长率应正确显示负号"""
        from src.data.collector import format_market_brief
        from src.data.models import FinancialMetrics

        fin = FinancialMetrics(
            stock_code="000001", report_date="2024-12-31",
            revenue_growth=-5.3, net_profit_growth=-12.8,
            eps=-0.15,
        )
        result = format_market_brief(
            stock_code="000001", stock_name="平安银行",
            financials=[fin],
        )

        assert "营收增长 -5.30%" in result
        assert "净利润增长 -12.80%" in result
        assert "EPS -0.1500" in result


# ── Tests: get_financials ──────────────────────────────────────────


class TestGetFinancials:
    """DataCollector.get_financials 测试"""

    def test_returns_financial_metrics(self, mock_empty_cache):
        """正常返回财务指标"""
        result = mock_empty_cache.get_financials("000001")
        assert len(result) == 1
        assert result[0].stock_code == "000001"
        assert result[0].eps == 1.25
        assert result[0].roe == 10.5
        assert result[0].debt_ratio == 55.0

    def test_network_error_returns_empty(self, failing_collector):
        """网络失败时返回空列表"""
        result = failing_collector.get_financials("000001")
        assert result == []

    def test_cache_hit_avoids_source_call(self, mock_empty_cache):
        """缓存命中时不应调数据源"""
        mock_empty_cache.cache.set("financials:000001", [{"stock_code": "cached"}])
        mock_empty_cache._source.get_financials = MagicMock(
            side_effect=AssertionError("不应调用"),
        )
        result = mock_empty_cache.get_financials("000001")
        assert result == [{"stock_code": "cached"}]

    def test_cache_ttl(self, collector):
        """财务数据应有缓存"""
        collector.cache.clear()
        result = collector.get_financials("000001")
        assert len(result) == 1
        cached = collector.cache.get("financials:000001")
        assert cached is not None
        assert cached[0].eps == 1.25

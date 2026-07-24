"""stocks.py 路由测试

覆盖：
1. GET /api/stocks/search
2. GET /api/stocks/{code}/quote
3. GET /api/stocks/{code}/kline
4. GET /api/stocks/{code}/news
5. GET /api/stocks/{code}/technical-indicators
6. GET /api/stocks/{code}/capital-flow
"""

from __future__ import annotations

from unittest.mock import patch

from tests.test_backend.conftest import make_mock_financial, make_mock_kline

# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/search
# ═══════════════════════════════════════════════════════════════════════


class TestSearchStocks:
    """股票搜索"""

    def test_search_by_code(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/search", params={"q": "000001"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["code"] == "000001"

    def test_search_by_name(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/search", params={"q": "平安"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert "平安" in data[0]["name"]

    def test_empty_query_returns_empty(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/search", params={"q": ""})

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_no_match(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/search", params={"q": "ZZZZ_NOT_EXIST"})

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_max_20_results(self, client, mock_collector):
        """搜索结果最多返回 20 条"""
        from src.data.models import StockInfo  # noqa: PLC0415

        mock_collector._stocks = [
            StockInfo(code=f"000{i:03d}", name=f"股票{i}")
            for i in range(50)
        ]
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/search", params={"q": "股票"})

        assert resp.status_code == 200
        assert len(resp.json()["data"]) <= 20


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/quote
# ═══════════════════════════════════════════════════════════════════════


class TestGetQuote:
    """个股实时行情"""

    def test_returns_quote(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/quote")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data is not None
        assert data["code"] == "000001"
        assert data["price"] == 3200.0

    def test_enrich_fields(self, client, mock_collector):
        """补充前端字段"""
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/quote")

        data = resp.json()["data"]
        assert "turnover_rate" in data
        assert "fund_flow" in data
        assert "market_cap" in data
        assert "open" in data  # open_ → open

    def test_not_found(self, client, mock_collector):
        """不存在的股票返回 data=None"""
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/999999/quote")

        assert resp.status_code == 200
        assert resp.json()["data"] is None


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/kline
# ═══════════════════════════════════════════════════════════════════════


class TestGetKline:
    """个股 K 线"""

    def test_returns_klines(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/kline")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 99  # mock_collector 默认 99 根
        assert "date" in data[0]
        assert "close" in data[0]

    def test_with_period_param(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/kline", params={"period": "weekly"})

        assert resp.status_code == 200
        assert len(resp.json()["data"]) > 0

    def test_with_date_range(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get(
                "/api/stocks/000001/kline",
                params={"start": "2024-01-01", "end": "2024-01-31"},
            )

        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/news
# ═══════════════════════════════════════════════════════════════════════


class TestGetNews:
    """个股新闻"""

    def test_returns_news(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/news")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        assert "title" in data[0]

    def test_max_20_news(self, client, mock_collector):
        """新闻最多返回 20 条"""
        from src.data.models import NewsItem  # noqa: PLC0415

        mock_collector._news = [
            NewsItem(code="000001", title=f"新闻{i}", date="2024-01-02")
            for i in range(30)
        ]
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/news")

        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 20


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/technical-indicators
# ═══════════════════════════════════════════════════════════════════════


class TestGetTechnicalIndicators:
    """技术指标"""

    def test_returns_indicators(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/technical-indicators")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data is not None
        assert "ma" in data
        assert "rsi" in data
        assert "macd" in data
        assert "bollinger" in data

    def test_empty_klines(self, client, mock_collector):
        """K 线为空时返回 data=None"""
        mock_collector._klines = []
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/technical-indicators")

        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_insufficient_data(self, client, mock_collector):
        """数据不足 60 根仍尝试计算"""
        mock_collector._klines = [
            make_mock_kline(date=f"2024-01-{i:02d}", close=10.0) for i in range(1, 10)
        ]
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/technical-indicators")

        assert resp.status_code == 200
        data = resp.json()["data"]
        # 数据不足时部分指标为 None，但不崩溃
        assert data is not None


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/capital-flow
# ═══════════════════════════════════════════════════════════════════════


class TestGetCapitalFlow:
    """资金流向"""

    def test_returns_flow(self, client, mock_collector):
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/capital-flow")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 5
        assert "main_net_inflow" in data[0]
        assert "retail_net_inflow" in data[0]
        assert "institutional_net_inflow" in data[0]

    def test_empty_flow(self, client, mock_collector):
        mock_collector._capital_flow = []
        with patch("backend.routers.stocks.collector", mock_collector):
            resp = client.get("/api/stocks/000001/capital-flow")

        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/financials
# ═══════════════════════════════════════════════════════════════════════


class TestGetFinancials:
    """财务指标"""

    def test_returns_financials(self, client, mock_collector):
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/000001/financials")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        assert data[0]["eps"] == 1.25
        assert data[0]["report_date"] == "2024-12-31"

    def test_contains_core_fields(self, client, mock_collector):
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/000001/financials")

        data = resp.json()["data"][0]
        assert "roe" in data
        assert "gross_margin" in data
        assert "debt_ratio" in data
        assert "revenue_growth" in data
        assert "eps" in data

    def test_max_10_periods(self, client, mock_collector):
        mock_collector._financials = [
            make_mock_financial(report_date=f"2024-{m:02d}-01")
            for m in range(1, 15)
        ]
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/000001/financials")

        data = resp.json()["data"]
        assert len(data) <= 10

    def test_empty_financials(self, client, mock_collector):
        mock_collector._financials = []
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/999999/financials")

        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ═══════════════════════════════════════════════════════════════════════
# GET /api/stocks/{code}/valuation
# ═══════════════════════════════════════════════════════════════════════


class TestGetValuation:
    """估值比率"""

    def test_returns_valuation(self, client, mock_collector):
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/000001/valuation")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data is not None
        assert data["pe"] == 15.2
        assert data["pb"] == 1.8

    def test_has_all_fields(self, client, mock_collector):
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/000001/valuation")

        data = resp.json()["data"]
        assert "pe" in data
        assert "pb" in data
        assert "ps" in data
        assert "market_cap" in data

    def test_not_found(self, client, mock_collector):
        with patch("backend.routers.financials.collector", mock_collector):
            resp = client.get("/api/stocks/999999/valuation")

        assert resp.status_code == 200
        assert resp.json()["data"] is None

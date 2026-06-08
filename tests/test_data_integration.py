"""数据采集集成测试（真实 akshare 调用）

使用 @pytest.mark.integration 标记，不参与覆盖率统计。
网络不可用时自动跳过。

注意：不同 akshare API 依赖不同数据源，skip 检测按数据源独立判断。
"""

import urllib.request

import pytest


def _eastmoney_reachable() -> bool:
    """检查东方财富 API 是否可达

    东方财富 API（push2.eastmoney.com / push2his.eastmoney.com）
    用于：实时行情、K 线、新闻、板块
    """
    try:
        urllib.request.urlopen(
            "https://push2.eastmoney.com",
            timeout=3,
        )
        return True
    except Exception:
        return False


skip_no_eastmoney = pytest.mark.skipif(
    not _eastmoney_reachable(),
    reason="东方财富 API 不可达（代理/网络限制）",
)


def _akshare_any_available() -> bool:
    """检查是否有任一 akshare API 可用（用于股票列表测试）"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return len(df) > 0
    except Exception:
        return False


skip_no_network = pytest.mark.skipif(
    not _akshare_any_available(),
    reason="akshare API 不可用（代理/网络受限）",
)


@pytest.fixture
def collector():
    from src.data.collector import DataCollector
    return DataCollector()


@pytest.mark.integration
@skip_no_network
class TestDataCollectorIntegrationBasic:
    """基础集成测试"""

    def test_get_all_stocks_returns_data(self, collector):
        stocks = collector.get_all_stocks()
        assert len(stocks) > 100
        assert all(s.code for s in stocks)
        assert all(s.name for s in stocks)


@pytest.mark.integration
@skip_no_eastmoney
class TestDataCollectorIntegrationEastMoney:
    """东方财富数据源集成测试"""

    def test_get_realtime_quotes(self, collector):
        quotes = collector.get_realtime_quotes()
        assert len(quotes) > 0
        first = quotes[0]
        assert first.code
        assert first.price > 0

    def test_get_single_quote(self, collector):
        quote = collector.get_realtime_quote("000001")
        assert quote is not None
        assert quote.code == "000001"

    def test_get_klines_daily(self, collector):
        klines = collector.get_klines("000001", period="daily", adjust="qfq")
        assert len(klines) > 0
        assert klines[0].date
        assert klines[0].close > 0

    def test_get_industry_boards(self, collector):
        boards = collector.get_industry_boards()
        assert len(boards) > 0
        assert all(b.board_type == "industry" for b in boards)

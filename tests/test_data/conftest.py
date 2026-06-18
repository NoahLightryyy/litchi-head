"""pytest 共享配置 —— data 模块测试基座

提供：
1. MockDataSource — 返回固定 Pydantic 模型数据的模拟数据源
2. MockFailingDataSource — 始终抛 ConnectionError 的模拟数据源
3. 共享 fixture（collector / mock_empty_cache / failing_collector）
4. 根 conftest.py 中的共享 fixture 自动继承

用法：
    def test_stocks(collector):
        stocks = collector.get_all_stocks()
        assert len(stocks) == 3

    def test_network_error(failing_collector):
        result = failing_collector.get_all_stocks()
        assert result == []
"""

import pytest

from src.data.cache import DataCache
from src.data.collector import DataCollector
from src.data.models import BoardInfo, KLine, NewsItem, StockInfo, StockQuote

# ═══════════════════════════════════════════════════════════════════════
# Mock 数据源
# ═══════════════════════════════════════════════════════════════════════


class MockDataSource:
    """测试用模拟数据源 —— 返回固定 Pydantic 模型数据"""

    def get_all_stocks(self) -> list[StockInfo]:
        return [
            StockInfo(code="000001", name="平安银行"),
            StockInfo(code="000002", name="万科A"),
            StockInfo(code="600519", name="贵州茅台"),
        ]

    def get_realtime_quotes(self) -> list[StockQuote]:
        return [
            StockQuote(
                code="000001", name="平安银行", price=12.50,
                change=0.30, change_pct=2.46, volume=1000000,
                amount=1.25e7, high=12.80, low=12.30,
                open_=12.40, prev_close=12.20,
            ),
            StockQuote(
                code="600519", name="贵州茅台", price=1880.00,
                change=-15.00, change_pct=-0.79, volume=500000,
                amount=9.4e8, high=1900.00, low=1860.00,
                open_=1890.00, prev_close=1895.00,
            ),
        ]

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        return [
            KLine(
                date="2026-06-05", open=12.40, close=12.50,
                high=12.80, low=12.30, volume=500000, amount=6.25e6,
            ),
            KLine(
                date="2026-06-04", open=12.30, close=12.35,
                high=12.50, low=12.20, volume=450000, amount=5.58e6,
            ),
            KLine(
                date="2026-06-03", open=12.10, close=12.20,
                high=12.30, low=12.05, volume=400000, amount=4.88e6,
            ),
        ]

    def get_news(self, code: str) -> list[NewsItem]:
        return [
            NewsItem(code=code, title="平安银行发布年报", date="2026-06-05",
                     content="年报内容摘要", source="东方财富"),
            NewsItem(code=code, title="平安银行数字化转型", date="2026-06-04",
                     content="数字化进展", source="证券时报"),
        ]

    def get_industry_boards(self) -> list[BoardInfo]:
        return [
            BoardInfo(code="BK0444", name="银行", board_type="industry"),
            BoardInfo(code="BK0476", name="保险", board_type="industry"),
            BoardInfo(code="BK0473", name="证券", board_type="industry"),
        ]

    def get_concept_boards(self) -> list[BoardInfo]:
        return []


class MockFailingDataSource:
    """模拟网络异常的数据源 —— 所有方法抛 ConnectionError"""

    def get_all_stocks(self) -> list[StockInfo]:
        raise ConnectionError("no network")

    def get_realtime_quotes(self) -> list[StockQuote]:
        raise ConnectionError("no network")

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        raise ConnectionError("no network")

    def get_news(self, code: str) -> list[NewsItem]:
        raise ConnectionError("no network")

    def get_industry_boards(self) -> list[BoardInfo]:
        raise ConnectionError("no network")

    def get_concept_boards(self) -> list[BoardInfo]:
        raise ConnectionError("no network")

    def get_capital_flow(self, code: str) -> list:
        raise ConnectionError("no network")


# ═══════════════════════════════════════════════════════════════════════
# pytest Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def collector():
    """可配置的 MockDataSource 注入 DataCollector"""
    source = MockDataSource()
    cache = DataCache()
    return DataCollector(source=source, cache=cache)


@pytest.fixture
def mock_empty_cache(collector):
    """缓存清空的 collector"""
    collector.cache.clear()
    return collector


@pytest.fixture
def failing_collector():
    """总是网络异常失败的 collector"""
    source = MockFailingDataSource()
    cache = DataCache()
    collector = DataCollector(source=source, cache=cache)
    collector.cache.clear()
    return collector

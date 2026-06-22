"""backend 路由测试共享配置

提供：
1. TestClient fixture
2. MockCollector — 模拟 DataCollector，所有方法返回可配置数据
3. Mock akshare DataFrame 工厂
4. Pydantic 模型工厂（make_mock_quote / make_mock_kline / …）

使用方法：
    def test_endpoint(client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")
            assert resp.status_code == 200
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from src.data.models import (
    BoardInfo,
    CapitalFlowItem,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
)

# ═══════════════════════════════════════════════════════════════════════
# Pydantic 模型工厂
# ═══════════════════════════════════════════════════════════════════════


def make_mock_quote(**overrides: Any) -> StockQuote:
    """创建模拟行情快照

    默认返回上证指数（code=000001），可覆盖任意字段。
    """
    data = {
        "code": "000001",
        "name": "上证指数",
        "price": 3200.0,
        "change": 15.0,
        "change_pct": 0.47,
        "volume": 100_000_000,
        "amount": 20_000_000_000.0,
        "high": 3210.0,
        "low": 3190.0,
        "open_": 3195.0,
        "prev_close": 3185.0,
    }
    data.update(overrides)
    return StockQuote(**data)


def make_mock_kline(**overrides: Any) -> KLine:
    """创建模拟 K 线

    默认值：2024-01-02, close=10.5
    high/low 默认范围足够宽（5.0~20.0），配合 MockCollector 中递增的 close 列。
    """
    data = {
        "date": "2024-01-02",
        "open": 10.0,
        "close": 10.5,
        "high": 20.0,
        "low": 5.0,
        "volume": 1_000_000,
        "amount": 10_500_000.0,
    }
    data.update(overrides)
    return KLine(**data)


def make_mock_stock(**overrides: Any) -> StockInfo:
    """创建模拟股票信息"""
    data = {"code": "000001", "name": "平安银行"}
    data.update(overrides)
    return StockInfo(**data)


def make_mock_news(**overrides: Any) -> NewsItem:
    """创建模拟新闻"""
    data = {
        "code": "000001",
        "title": "测试新闻标题",
        "date": "2024-01-02",
        "content": "这是一条测试新闻内容。",
        "source": "测试源",
        "url": "",
    }
    data.update(overrides)
    return NewsItem(**data)


def make_mock_capital_flow(**overrides: Any) -> CapitalFlowItem:
    """创建模拟资金流向"""
    data = {
        "date": "2024-01-02",
        "main_net_inflow": 1_000_000.0,
        "retail_net_inflow": -500_000.0,
        "institutional_net_inflow": 800_000.0,
    }
    data.update(overrides)
    return CapitalFlowItem(**data)


def make_mock_board(**overrides: Any) -> BoardInfo:
    """创建模拟板块信息"""
    data = {"code": "BK001", "name": "银行", "board_type": "industry"}
    data.update(overrides)
    return BoardInfo(**data)


# ═══════════════════════════════════════════════════════════════════════
# Mock akshare DataFrame 工厂
# ═══════════════════════════════════════════════════════════════════════


def make_board_perf_df(
    rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """创建模拟板块行情 DataFrame（匹配 akshare 列名）

    默认返回 2 行：银行(+1.5%)/券商(-0.5%)
    """
    if rows is None:
        rows = [
            {"板块代码": "BK001", "板块名称": "银行",
             "涨跌幅": 1.5, "主力净流入-净额": 500_000_000.0},
            {"板块代码": "BK002", "板块名称": "券商",
             "涨跌幅": -0.5, "主力净流入-净额": -200_000_000.0},
        ]
    return pd.DataFrame(rows)


def make_board_stocks_df(
    rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """创建模拟板块成分股 DataFrame（匹配 akshare 列名）

    默认返回 6 只成分股，含涨跌分布以便测试 heat/chain_map。
    """
    if rows is None:
        rows = [
            {"代码": "000001", "名称": "平安银行", "现价": 12.5,
             "涨跌幅": 2.0, "主力净流入": 1_000_000.0},
            {"代码": "000002", "名称": "招商银行", "现价": 35.0,
             "涨跌幅": 1.5, "主力净流入": 2_000_000.0},
            {"代码": "000003", "名称": "工商银行", "现价": 5.8,
             "涨跌幅": 0.5, "主力净流入": 500_000.0},
            {"代码": "000004", "名称": "建设银行", "现价": 7.2,
             "涨跌幅": -0.3, "主力净流入": -100_000.0},
            {"代码": "000005", "名称": "中国银行", "现价": 4.5,
             "涨跌幅": 0.2, "主力净流入": 300_000.0},
            {"代码": "000006", "名称": "农业银行", "现价": 3.8,
             "涨跌幅": -0.5, "主力净流入": -200_000.0},
        ]
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# MockCollector — 模拟 DataCollector
# ═══════════════════════════════════════════════════════════════════════


class MockCollector:
    """模拟 DataCollector，所有方法为同步（与原 DataCollector 一致）

    通过属性配置返回数据：
        mock._quotes     — get_realtime_quotes / get_realtime_quote
        mock._stocks     — get_all_stocks
        mock._klines     — get_klines
        mock._news       — get_news
        mock._capital_flow — get_capital_flow
        mock._boards     — get_industry_boards
    """

    def __init__(self) -> None:
        self._quotes: list[StockQuote] = [
            make_mock_quote(code="000001", name="上证指数", price=3200.0, change_pct=0.47),
            make_mock_quote(code="399001", name="深证成指", price=10500.0, change_pct=0.85),
            make_mock_quote(code="399006", name="创业板指", price=2200.0, change_pct=1.2),
        ]
        self._stocks: list[StockInfo] = [
            make_mock_stock(code="000001", name="平安银行"),
            make_mock_stock(code="000002", name="招商银行"),
            make_mock_stock(code="600001", name="中信证券"),
        ]
        self._klines: list[KLine] = [
            make_mock_kline(date=f"2024-01-{i:02d}", close=round(10.0 + i * 0.1, 1))
            for i in range(1, 100)
        ]
        self._news: list[NewsItem] = [
            make_mock_news(title=f"新闻 {i}", date="2024-01-02") for i in range(3)
        ]
        self._capital_flow: list[CapitalFlowItem] = [
            make_mock_capital_flow(date=f"2024-01-{i:02d}") for i in range(5)
        ]
        self._boards: list[BoardInfo] = [
            make_mock_board(code="BK001", name="银行", board_type="industry"),
            make_mock_board(code="BK002", name="券商", board_type="industry"),
        ]

    def get_realtime_quotes(self) -> list[StockQuote]:
        return self._quotes

    def get_realtime_quote(self, code: str) -> StockQuote | None:
        for q in self._quotes:
            if q.code == code:
                return q
        return None

    def get_all_stocks(self) -> list[StockInfo]:
        return self._stocks

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
    ) -> list[KLine]:
        return self._klines

    def get_news(self, code: str) -> list[NewsItem]:
        return self._news

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        return self._capital_flow

    def get_industry_boards(self) -> list[BoardInfo]:
        return self._boards


# ═══════════════════════════════════════════════════════════════════════
# pytest Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def disable_rate_limit(client: TestClient) -> None:
    """所有测试默认关闭限流，避免排队测试误触发 429"""
    client.app.state.limiter.enabled = False
    yield


@pytest.fixture
def mock_collector() -> MockCollector:
    """可配置的 MockCollector 实例

    替换 router 模块级 collector 用：
        with patch("backend.routers.market.collector", mock_collector):
            ...
    """
    return MockCollector()

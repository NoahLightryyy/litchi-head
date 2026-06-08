"""数据层 Pydantic 模型 —— 数据契约（ADR-001/008）

所有跨模块数据传输使用此模块定义的 BaseModel。
"""

from typing import Literal

from pydantic import BaseModel


class StockInfo(BaseModel):
    """A 股股票基本信息"""
    code: str
    name: str
    market: str = ""


class StockQuote(BaseModel):
    """实时行情快照"""
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    amount: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open_: float = 0.0
    prev_close: float = 0.0


class KLine(BaseModel):
    """K 线数据点"""
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float = 0.0


class NewsItem(BaseModel):
    """个股新闻"""
    code: str
    title: str
    date: str
    content: str = ""
    source: str = ""
    url: str = ""


BoardType = Literal["industry", "concept"]


class BoardInfo(BaseModel):
    """板块信息"""
    code: str
    name: str
    board_type: BoardType


__all__ = [
    "BoardInfo",
    "BoardType",
    "KLine",
    "NewsItem",
    "StockInfo",
    "StockQuote",
]

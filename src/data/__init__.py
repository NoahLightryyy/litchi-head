"""数据采集模块 —— A 股行情 + 新闻数据采集

基于 akshare（ADR-003），为辩论引擎和分析师提供数据基础设施。

数据流：
    akshare API → DataCollector → Pydantic Models → 缓存层 → 下游消费者

已实现功能：
    - 全部 A 股代码列表（stock_info_a_code_name，TTL 1h）
    - 全市场实时行情（stock_zh_a_spot_em，TTL 30s）
    - 个股历史 K 线（stock_zh_a_hist，TTL 5min）
    - 个股新闻（stock_news_em，TTL 2min）
    - 行业/概念板块列表（TTL 1h）
    - 透明缓存层（DataCache，TTL 可配置）
"""

from src.data.cache import DataCache
from src.data.collector import DataCollector
from src.data.models import (
    BoardInfo,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
)

__all__ = [
    "BoardInfo",
    "DataCache",
    "DataCollector",
    "KLine",
    "NewsItem",
    "StockInfo",
    "StockQuote",
]

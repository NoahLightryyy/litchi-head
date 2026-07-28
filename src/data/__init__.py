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
    - PD 动态指标体系（行业 → 产业链位置 → 关键指标选择）
    - CNINFO 权威公告证据适配器（显式六态结果）
"""

from src.data.cache import DataCache
from src.data.collector import DataCollector
from src.data.indicators import (
    INDICATOR_DEFS,
    INDICATOR_DEFS_MAP,
    INDUSTRY_CHAIN_MAP,
    REGISTRY,
    DynamicIndicatorSelector,
    IndicatorDef,
    IndustryChainPosition,
    SelectorResult,
    normalize_industry,
)
from src.data.models import (
    AnnouncementItem,
    BoardInfo,
    FinancialMetrics,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
    ValuationMetrics,
)

__all__ = [
    "AnnouncementItem",
    "BoardInfo",
    "DataCache",
    "DataCollector",
    "DynamicIndicatorSelector",
    "FinancialMetrics",
    "INDICATOR_DEFS",
    "INDICATOR_DEFS_MAP",
    "INDUSTRY_CHAIN_MAP",
    "IndicatorDef",
    "IndustryChainPosition",
    "KLine",
    "NewsItem",
    "REGISTRY",
    "SelectorResult",
    "StockInfo",
    "StockQuote",
    "ValuationMetrics",
    "normalize_industry",
]

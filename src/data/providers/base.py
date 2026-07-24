"""数据源抽象层 —— DataSource Protocol

所有数据源实现此协议接口，DataCollector 通过它获取数据。
上层代码不关心数据具体来源（akshare / adata / zzshare …）。

Usage:
    class MySource:
        def get_all_stocks(self) -> list[StockInfo]: ...
        def get_realtime_quotes(self) -> list[StockQuote]: ...
        # ... 实现全部 6 个方法

    collector = DataCollector(source=MySource())
"""

import math
from typing import Protocol

from src.data.models import (
    BoardInfo,
    CapitalFlowItem,
    FinancialMetrics,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
)


class DataSource(Protocol):
    """数据源统一接口

    每个方法返回 Pydantic 模型列表，网络异常时返回空列表。
    方法签名与 DataCollector 保持一致（不含 cache/health 等横切关注点）。
    """

    def get_all_stocks(self) -> list[StockInfo]:
        """获取全部 A 股股票代码和名称"""
        ...

    def get_realtime_quotes(self) -> list[StockQuote]:
        """获取全市场实时行情"""
        ...

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        """获取个股历史 K 线"""
        ...

    def get_news(self, code: str) -> list[NewsItem]:
        """获取个股新闻"""
        ...

    def get_industry_boards(self) -> list[BoardInfo]:
        """获取行业板块列表"""
        ...

    def get_concept_boards(self) -> list[BoardInfo]:
        """获取概念板块列表"""
        ...

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        """获取个股资金流向

        Args:
            code: 股票代码，如 "000001"

        Returns:
            CapitalFlowItem 列表（失败时返回空列表）
        """
        ...

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        """获取个股财务指标

        Args:
            code: 股票代码，如 "000001"

        Returns:
            FinancialMetrics 列表（失败时返回空列表）
        """
        ...

    def get_stock_industry(self, code: str) -> str | None:
        """获取个股所属行业

        返回东方财富行业分类名称（如"银行Ⅱ"、"白酒Ⅱ"），
        用于 PD 动态指标体系按行业选取关键指标。

        Args:
            code: 股票代码，如 "000001"

        Returns:
            行业名称字符串（如"银行Ⅱ"），失败或无法识别时返回 None
        """
        ...


# ── 通用 pandas Series 安全取值函数 ────────────────────────────────────


def safe_str(val: object, default: str = "") -> str:
    """安全提取字符串"""
    if val is None:
        return default
    if hasattr(val, "__len__") and len(val) == 0:  # type: ignore[arg-type]
        return default
    return str(val)


def safe_float(val: object, default: float = 0.0) -> float:
    """安全提取浮点数，NaN → default"""
    if val is None:
        return default
    try:
        result = float(val)  # type: ignore[arg-type]
        if math.isnan(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def safe_int(val: object, default: int = 0) -> int:
    """安全提取整数"""
    if val is None:
        return default
    try:
        return int(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return default


__all__ = [
    "DataSource",
    "FinancialMetrics",
    "safe_float",
    "safe_int",
    "safe_str",
]

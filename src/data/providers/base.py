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

from typing import Protocol

from src.data.models import BoardInfo, KLine, NewsItem, StockInfo, StockQuote


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


# ── 通用 pandas Series 安全取值函数 ────────────────────────────────────


def safe_str(val: object, default: str = "") -> str:
    """安全提取字符串"""
    if val is None:
        return default
    if hasattr(val, "__len__") and len(val) == 0:  # type: ignore[arg-type]
        return default
    return str(val)


def safe_float(val: object, default: float = 0.0) -> float:
    """安全提取浮点数"""
    if val is None:
        return default
    try:
        return float(val)  # type: ignore[arg-type]
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
    "safe_float",
    "safe_int",
    "safe_str",
]

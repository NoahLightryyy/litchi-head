"""adata 数据源实现

adata（v2.9.0+）是免费开源 A 股量化数据库，5 源融合自动切换：
同花顺 + 东方财富 + 新浪 + 腾讯 + 百度。

GitHub: https://github.com/1nchaos/adata

安装：
    pip install adata

注意：
    adata 是可选依赖，未安装时 ADataSource 构造函数会抛出 ImportError。
"""

import logging
from typing import Any

from src.data.models import (
    BoardInfo,
    CapitalFlowItem,
    FinancialMetrics,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
)
from src.data.providers.base import safe_float, safe_int, safe_str

logger = logging.getLogger("data.providers.adata")

try:
    import adata as _adata_mod  # type: ignore[import] # noqa: F401
except ImportError:
    _adata_mod = None  # type: ignore[assignment]


class ADataSource:
    """adata 数据源

    5 源融合（同花顺 + 东方财富 + 新浪 + 腾讯 + 百度），
    一个数据源挂了自动切换到另一个。

    Raises:
        ImportError: adata 库未安装时抛出
    """

    def __init__(self) -> None:
        if _adata_mod is None:
            raise ImportError(
                "adata 未安装，请执行: pip install adata"
            )
        self._adata = _adata_mod

    # ── 股票信息 ─────────────────────────────────────────────────────

    def get_all_stocks(self) -> list[StockInfo]:
        try:
            df = self._adata.stock.info.all_code()
            return [
                StockInfo(
                    code=safe_str(row.get("stock_code", "")),
                    name=safe_str(row.get("stock_name", "")),
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("adata all_code 失败")
            return []

    # ── 实时行情 ─────────────────────────────────────────────────────

    def get_realtime_quotes(self) -> list[StockQuote]:
        try:
            # adata 实时行情需要传入股票代码列表
            # 先获取全部股票代码，然后批量查询
            stocks = self.get_all_stocks()
            codes = [s.code for s in stocks]
            if not codes:
                return []

            df = self._adata.stock.market.list_market_current(
                code_list=codes
            )
            return [_adata_row_to_quote(row) for _, row in df.iterrows()]
        except Exception:
            logger.exception("adata list_market_current 失败")
            return []

    # ── K 线数据 ─────────────────────────────────────────────────────

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        try:
            # adata k_type: 1=日K, 2=周K, 3=月K
            k_map = {"daily": 1, "weekly": 2, "monthly": 3}
            k_type = k_map.get(period, 1)

            kwargs: dict[str, Any] = {
                "stock_code": code,
                "k_type": k_type,
            }
            if start:
                kwargs["start_date"] = start
            if end:
                kwargs["end_date"] = end

            df = self._adata.stock.market.get_market(**kwargs)
            return [_adata_row_to_kline(row) for _, row in df.iterrows()]
        except Exception:
            logger.exception("adata get_market 失败: code=%s", code)
            return []

    # ── 新闻 ─────────────────────────────────────────────────────────

    def get_news(self, code: str) -> list[NewsItem]:
        """adata 暂不直接提供新闻接口，返回空列表"""
        return []

    # ── 板块 ─────────────────────────────────────────────────────────

    def get_industry_boards(self) -> list[BoardInfo]:
        try:
            industry = getattr(self._adata.stock.info, "all_industry", None)
            if industry is None:
                return []
            df = industry()
            return [
                BoardInfo(
                    code=safe_str(row.get("industry_code", "")),
                    name=safe_str(row.get("industry_name", "")),
                    board_type="industry",
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("adata all_industry 失败")
            return []

    def get_concept_boards(self) -> list[BoardInfo]:
        """adata 概念板块接口待确认格式，暂返回空列表"""
        return []

    # ── 资金流向 ─────────────────────────────────────────────────────

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        """adata 暂不直接提供资金流向接口，返回空列表"""
        return []

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        """adata 暂不直接提供财务指标接口，返回空列表"""
        return []


# ── DataFrame → Model 转换函数 ────────────────────────────────────────


def _adata_row_to_quote(row: Any) -> StockQuote:
    """将 adata 实时行情 DataFrame 行转换为 StockQuote"""
    return StockQuote(
        code=safe_str(row.get("stock_code", "")),
        name=safe_str(row.get("stock_name", "")),
        price=safe_float(row.get("latest_price", 0.0)),
        change=safe_float(row.get("change", 0.0)),
        change_pct=safe_float(row.get("change_pct", 0.0)),
        volume=safe_int(row.get("volume", 0)),
        amount=safe_float(row.get("amount", 0.0)),
        high=safe_float(row.get("high", 0.0)),
        low=safe_float(row.get("low", 0.0)),
        open_=safe_float(row.get("open", 0.0)),
        prev_close=safe_float(row.get("pre_close", 0.0)),
    )


def _adata_row_to_kline(row: Any) -> KLine:
    """将 adata K 线 DataFrame 行转换为 KLine"""
    return KLine(
        date=safe_str(row.get("trade_date", "")),
        open=safe_float(row.get("open", 0.0)),
        close=safe_float(row.get("close", 0.0)),
        high=safe_float(row.get("high", 0.0)),
        low=safe_float(row.get("low", 0.0)),
        volume=safe_int(row.get("volume", 0)),
        amount=safe_float(row.get("amount", 0.0)),
    )


__all__ = ["ADataSource"]

"""akshare 数据源实现

从 `collector.py` 抽离的 akshare 原生调用 + DataFrame 转换。
每个方法直接调 akshare API，返回 Pydantic 模型列表。
"""

import logging

import akshare as ak
import pandas as pd

from src.data.models import BoardInfo, CapitalFlowItem, KLine, NewsItem, StockInfo, StockQuote
from src.data.providers.base import safe_float, safe_int, safe_str

logger = logging.getLogger("data.providers.akshare")


def _detect_market(code: str) -> str:
    """根据股票代码判断交易市场

    Args:
        code: 6 位股票代码

    Returns:
        "sh"（上海）/ "sz"（深圳）/ "bj"（北京）
    """
    if not code:
        return "sh"
    if code.startswith(("4", "8")):
        return "bj"
    if code.startswith("6"):
        return "sh"
    return "sz"


class AKShareSource:
    """akshare 数据源

    akshare 是 HTTP 爬虫库，每次调用构造抓取 URL 请求东方财富服务器。
    """

    # ── 股票信息 ─────────────────────────────────────────────────────

    def get_all_stocks(self) -> list[StockInfo]:
        try:
            df: pd.DataFrame = ak.stock_info_a_code_name()
            return [
                StockInfo(code=safe_str(row["code"]), name=safe_str(row["name"]))
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("akshare stock_info_a_code_name 失败")
            return []

    # ── 实时行情 ─────────────────────────────────────────────────────

    def get_realtime_quotes(self) -> list[StockQuote]:
        try:
            df: pd.DataFrame = ak.stock_zh_a_spot_em()
            return [_row_to_quote(row) for _, row in df.iterrows()]
        except Exception:
            logger.exception("akshare stock_zh_a_spot_em 失败")
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
            df: pd.DataFrame = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
            return [_row_to_kline(row) for _, row in df.iterrows()]
        except Exception:
            logger.exception("akshare stock_zh_a_hist 失败: code=%s", code)
            return []

    # ── 新闻 ─────────────────────────────────────────────────────────

    def get_news(self, code: str) -> list[NewsItem]:
        try:
            df: pd.DataFrame = ak.stock_news_em(symbol=code)
            return [_row_to_news(row, code) for _, row in df.iterrows()]
        except Exception:
            logger.exception("akshare stock_news_em 失败: code=%s", code)
            return []

    # ── 板块 ─────────────────────────────────────────────────────────

    def get_industry_boards(self) -> list[BoardInfo]:
        try:
            df: pd.DataFrame = ak.stock_board_industry_name_em()
            return [
                BoardInfo(
                    code=safe_str(row["板块代码"]),
                    name=safe_str(row["板块名称"]),
                    board_type="industry",
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("akshare stock_board_industry_name_em 失败")
            return []

    def get_concept_boards(self) -> list[BoardInfo]:
        try:
            df: pd.DataFrame = ak.stock_board_concept_name_em()
            return [
                BoardInfo(
                    code=safe_str(row["板块代码"]),
                    name=safe_str(row["板块名称"]),
                    board_type="concept",
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("akshare stock_board_concept_name_em 失败")
            return []

    # ── 资金流向 ─────────────────────────────────────────────────────

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        """获取个股资金流向（主力/散户/机构净流入）

        列映射（东方财富接口）：
          日期 → date
          主力净流入-净额 → main_net_inflow
          小单净流入-净额 → retail_net_inflow
          大单净流入-净额 → institutional_net_inflow
        """
        try:
            market = _detect_market(code)
            df: pd.DataFrame = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is None or df.empty:
                return []

            results: list[CapitalFlowItem] = []
            for _, row in df.iterrows():
                try:
                    results.append(
                        CapitalFlowItem(
                            date=safe_str(row.get("日期", "")),
                            main_net_inflow=safe_float(row.get("主力净流入-净额", 0.0)),
                            retail_net_inflow=safe_float(row.get("小单净流入-净额", 0.0)),
                            institutional_net_inflow=safe_float(row.get("大单净流入-净额", 0.0)),
                        )
                    )
                except (ValueError, TypeError):
                    continue
            return results
        except Exception:
            logger.exception("akshare stock_individual_fund_flow 失败: code=%s", code)
            return []


# ── DataFrame → Model 转换函数 ────────────────────────────────────────


def _row_to_quote(row: pd.Series) -> StockQuote:
    """将 akshare 实时行情的 DataFrame 行转换为 StockQuote"""
    return StockQuote(
        code=safe_str(row.get("代码", "")),
        name=safe_str(row.get("名称", "")),
        price=safe_float(row.get("最新价", 0.0)),
        change=safe_float(row.get("涨跌额", 0.0)),
        change_pct=safe_float(row.get("涨跌幅", 0.0)),
        volume=safe_int(row.get("成交量", 0)),
        amount=safe_float(row.get("成交额", 0.0)),
        high=safe_float(row.get("最高", 0.0)),
        low=safe_float(row.get("最低", 0.0)),
        open_=safe_float(row.get("今开", 0.0)),
        prev_close=safe_float(row.get("昨收", 0.0)),
    )


def _row_to_kline(row: pd.Series) -> KLine:
    """将 akshare K 线 DataFrame 行转换为 KLine"""
    return KLine(
        date=safe_str(row.get("日期", "")),
        open=safe_float(row.get("开盘", 0.0)),
        close=safe_float(row.get("收盘", 0.0)),
        high=safe_float(row.get("最高", 0.0)),
        low=safe_float(row.get("最低", 0.0)),
        volume=safe_int(row.get("成交量", 0)),
        amount=safe_float(row.get("成交额", 0.0)),
    )


def _row_to_news(row: pd.Series, code: str) -> NewsItem:
    """将 akshare 新闻 DataFrame 行转换为 NewsItem"""
    return NewsItem(
        code=code,
        title=safe_str(row.get("title", "")),
        date=safe_str(row.get("date", "")),
        content=safe_str(row.get("content", "")),
        source=safe_str(row.get("source", "")),
        url=safe_str(row.get("url", "")),
    )


__all__ = ["AKShareSource"]

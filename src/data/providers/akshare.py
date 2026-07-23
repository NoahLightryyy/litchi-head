"""akshare 数据源实现

从 `collector.py` 抽离的 akshare 原生调用 + DataFrame 转换。
每个方法直接调 akshare API，返回 Pydantic 模型列表。
"""

import logging

import akshare as ak
import pandas as pd

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

    # ── 财务数据 ─────────────────────────────────────────────────────

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        """获取个股财务指标

        使用 akshare stock_financial_analysis_indicator 获取季度财务分析指标。
        返回最近 N 个报告期的列表，最新在前。

        Args:
            code: 股票代码，如 "000001"

        Returns:
            FinancialMetrics 列表，每季度一条
        """
        try:
            df: pd.DataFrame = ak.stock_financial_analysis_indicator(
                symbol=code, start_year="2024",
            )
            if df is None or df.empty:
                return []
            return [_row_to_financial(row, code) for _, row in df.iterrows()]
        except Exception:
            logger.exception(
                "akshare stock_financial_analysis_indicator 失败: code=%s", code,
            )
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


def _row_to_financial(row: pd.Series, code: str) -> FinancialMetrics:
    """将 akshare 财务分析 DataFrame 行转换为 FinancialMetrics

    akshare stock_financial_analysis_indicator 返回约 86 列，
    此函数提取关键指标，缺失列安全默认 0.0。
    """
    return FinancialMetrics(
        stock_code=code,
        report_date=safe_str(row.get("日期", "")),
        eps=safe_float(row.get("摊薄每股收益(元)", 0.0)),
        book_value_per_share=safe_float(row.get("每股净资产_调整后(元)", 0.0)),
        operating_cf_per_share=safe_float(row.get("每股经营性现金流(元)", 0.0)),
        roe=safe_float(row.get("净资产收益率(%)", 0.0)),
        roa=safe_float(row.get("总资产利润率(%)", 0.0)),
        gross_margin=safe_float(row.get("销售毛利率(%)", 0.0)),
        net_profit_margin=safe_float(row.get("销售净利率(%)", 0.0)),
        revenue_growth=safe_float(row.get("主营业务收入增长率(%)", 0.0)),
        net_profit_growth=safe_float(row.get("净利润增长率(%)", 0.0)),
        debt_ratio=safe_float(row.get("资产负债率(%)", 0.0)),
        current_ratio=safe_float(row.get("流动比率", 0.0)),
        quick_ratio=safe_float(row.get("速动比率", 0.0)),
        inventory_turnover=safe_float(row.get("存货周转率(次)", 0.0)),
        asset_turnover=safe_float(row.get("总资产周转率(次)", 0.0)),
        total_assets=safe_float(row.get("总资产(元)", 0.0)),
        operating_revenue=safe_float(row.get("主营业务利润(元)", 0.0)),
    )


__all__ = ["AKShareSource"]

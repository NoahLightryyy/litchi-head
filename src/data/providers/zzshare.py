"""zzshare 数据源实现

zzshare 兼容 Tushare Pro 接口规范，无需 Token、无需积分、完全免费。
接口与 Tushare Pro 一致，将来迁到付费版只需换 Token。

GitHub: https://github.com/zzquant/zzshare

安装：
    pip install git+https://github.com/zzquant/zzshare.git

注意：
    zzshare 是可选依赖，未安装时 ZzshareSource 构造函数会抛出 ImportError。
"""

import logging

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

logger = logging.getLogger("data.providers.zzshare")

try:
    from zzshare import pro as _zz_pro  # type: ignore[import] # noqa: PLC0415
except ImportError:
    _zz_pro = None  # type: ignore[assignment]


class ZzshareSource:
    """zzshare 数据源

    零成本 Tushare Pro 兼容方案：
    - 接口规范与 Tushare Pro 100% 一致
    - 无需申请 Token，无需攒积分
    - 覆盖 40+ 接口：日线、资金流向、板块热度、龙虎榜、情绪指标

    Raises:
        ImportError: zzshare 未安装时抛出
    """

    def __init__(self) -> None:
        if _zz_pro is None:
            raise ImportError(
                "zzshare 未安装，请执行: pip install git+https://github.com/zzquant/zzshare.git"
            )
        self._pro = _zz_pro

    # ── 股票信息 ─────────────────────────────────────────────────────

    def get_all_stocks(self) -> list[StockInfo]:
        try:
            df = self._pro.stock_basic()
            return [
                StockInfo(
                    code=safe_str(row.get("symbol", "")),
                    name=safe_str(row.get("name", "")),
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("zzshare stock_basic 失败")
            return []

    # ── 实时行情 ─────────────────────────────────────────────────────

    def get_realtime_quotes(self) -> list[StockQuote]:
        """zzshare 暂不直接提供全市场实时行情，返回空列表"""
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
            # zzshare 使用 ts_code 格式（如 "000001.SZ"）
            ts_code = _to_ts_code(code)
            kwargs = {
                "ts_code": ts_code,
                "start_date": start.replace("-", "") if start else "",
                "end_date": end.replace("-", "") if end else "",
            }
            if period == "daily":
                df = self._pro.daily(**kwargs)
            elif period == "weekly":
                df = self._pro.weekly(**kwargs)
            elif period == "monthly":
                df = self._pro.monthly(**kwargs)
            else:
                df = self._pro.daily(**kwargs)

            return [_zz_row_to_kline(row) for _, row in df.iterrows()]
        except Exception:
            logger.exception("zzshare daily/weekly/monthly 失败: code=%s", code)
            return []

    # ── 新闻 ─────────────────────────────────────────────────────────

    def get_news(self, code: str) -> list[NewsItem]:
        """zzshare 暂不直接提供新闻接口，返回空列表"""
        return []

    # ── 板块 ─────────────────────────────────────────────────────────

    def get_industry_boards(self) -> list[BoardInfo]:
        try:
            df = self._pro.index_classified()
            return [
                BoardInfo(
                    code=safe_str(row.get("index_code", "")),
                    name=safe_str(row.get("index_name", "")),
                    board_type="industry",
                )
                for _, row in df.iterrows()
            ]
        except Exception:
            logger.exception("zzshare index_classified 失败")
            return []

    def get_concept_boards(self) -> list[BoardInfo]:
        return []

    # ── 资金流向 ─────────────────────────────────────────────────────

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        """zzshare 资金流向接口待接入，返回空列表"""
        return []

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        """获取个股财务指标

        使用 zzshare（Tushare Pro 兼容）fina_indicator 获取财务指标。
        返回所有报告期的列表，最新在前。

        Args:
            code: 股票代码，如 "000001"

        Returns:
            FinancialMetrics 列表，网络异常时返回空列表
        """
        try:
            ts_code = _to_ts_code(code)
            df = self._pro.fina_indicator(ts_code=ts_code)
            if df is None or df.empty:
                return []
            return [_zz_row_to_financial(row, code) for _, row in df.iterrows()]
        except Exception:
            logger.exception("zzshare fina_indicator 失败: code=%s", code)
            return []


# ── 工具函数 ──────────────────────────────────────────────────────────


def _to_ts_code(code: str) -> str:
    """将纯数字代码转为 Tushare ts_code 格式"""
    code = code.strip()
    if "." in code:
        return code  # 已经是 ts_code 格式
    # 6xxxxx → SH, 0xxxxx/3xxxxx → SZ
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


# ── DataFrame → Model 转换函数 ────────────────────────────────────────


def _zz_row_to_kline(row) -> KLine:
    """将 zzshare K 线 DataFrame 行转换为 KLine"""
    # zzshare 兼容 tushare 字段名
    date_key = "trade_date" if "trade_date" in row else "trade_date"
    return KLine(
        date=safe_str(row.get(date_key, "")),
        open=safe_float(row.get("open", 0.0)),
        close=safe_float(row.get("close", 0.0)),
        high=safe_float(row.get("high", 0.0)),
        low=safe_float(row.get("low", 0.0)),
        volume=safe_int(row.get("vol", 0)),
        amount=safe_float(row.get("amount", 0.0)),
    )


def _zz_row_to_financial(row, code: str) -> FinancialMetrics:
    """将 zzshare fina_indicator DataFrame 行转换为 FinancialMetrics

    zzshare 兼容 Tushare Pro fina_indicator 接口返回约 40+ 列财务指标，
    此函数提取 FinancialMetrics 所需的 17 个字段。
    """
    # fina_indicator 使用 end_date 作为报告期
    report_date = safe_str(row.get("end_date", "")) or safe_str(row.get("ann_date", ""))
    return FinancialMetrics(
        stock_code=code,
        report_date=report_date,
        eps=safe_float(row.get("eps", 0.0)),
        book_value_per_share=safe_float(row.get("bps", 0.0)),
        operating_cf_per_share=safe_float(row.get("ocfps", 0.0)),
        roe=safe_float(row.get("roe", 0.0)),
        roa=safe_float(row.get("roa", 0.0)),
        gross_margin=safe_float(row.get("gross_margin", 0.0)),
        net_profit_margin=safe_float(row.get("netprofit_margin", 0.0)),
        revenue_growth=safe_float(row.get("or_yoy", 0.0)),
        net_profit_growth=safe_float(row.get("nprofit_yoy", 0.0)),
        debt_ratio=safe_float(row.get("debt_to_assets", 0.0)),
        current_ratio=safe_float(row.get("current_ratio", 0.0)),
        quick_ratio=safe_float(row.get("quick_ratio", 0.0)),
        inventory_turnover=safe_float(row.get("inv_turnover", 0.0)),
        asset_turnover=safe_float(row.get("assets_turn", 0.0)),
        total_assets=safe_float(row.get("total_assets", 0.0)),
        operating_revenue=safe_float(row.get("oper_rev", 0.0)),
    )


__all__ = ["ZzshareSource"]

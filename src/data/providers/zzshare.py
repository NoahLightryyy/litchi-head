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
        """zzshare 财务指标接口待接入，返回空列表"""
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


__all__ = ["ZzshareSource"]

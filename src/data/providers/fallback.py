"""故障自动切换数据源 —— FallbackSource

当主数据源连续 N 次失败时，自动降级到备用数据源。
备用源也失败时返回空列表（静默降级）。

用法：
    from src.data.providers.adata import ADataSource
    from src.data.providers.akshare import AKShareSource
    from src.data.providers.fallback import FallbackSource

    source = FallbackSource(
        primary=ADataSource(),
        fallback=AKShareSource(),
        max_failures=3,      # 连续 3 次失败后切备用
    )
    collector = DataCollector(source=source)
"""

import logging
from collections import defaultdict

from src.data.models import (
    BoardInfo,
    CapitalFlowItem,
    FinancialMetrics,
    KLine,
    NewsItem,
    StockInfo,
    StockQuote,
)
from src.data.providers.base import DataSource

logger = logging.getLogger("data.providers.fallback")


class FallbackSource:
    """故障自动切换数据源

    主源连续失败超过阈值，自动降级到备用源。
    每个 endpoint 独立维护失败计数 —— K 线挂了不影响行情。

    Args:
        primary: 主数据源
        fallback: 备用数据源
        max_failures: 连续失败次数阈值，达到后切备用（默认 3）
    """

    def __init__(
        self,
        primary: DataSource,
        fallback: DataSource,
        max_failures: int = 3,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._max_failures = max_failures
        # 每个 endpoint 独立记录连续失败次数
        self._consecutive_failures: defaultdict[str, int] = defaultdict(int)
        # 当前是否使用备用源（按 endpoint）
        self._using_fallback: defaultdict[str, bool] = defaultdict(bool)

    # ── 委托方法 ─────────────────────────────────────────────────────

    def get_all_stocks(self) -> list[StockInfo]:
        return self._call("all_stocks", self._primary.get_all_stocks, self._fallback.get_all_stocks)

    def get_realtime_quotes(self) -> list[StockQuote]:
        return self._call(
            "quotes",
            self._primary.get_realtime_quotes,
            self._fallback.get_realtime_quotes,
        )

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        return self._call(
            f"kline:{period}",
            lambda: self._primary.get_klines(
                code, period=period, start=start, end=end, adjust=adjust,
            ),
            lambda: self._fallback.get_klines(
                code, period=period, start=start, end=end, adjust=adjust,
            ),
        )

    def get_news(self, code: str) -> list[NewsItem]:
        return self._call(
            "news",
            lambda: self._primary.get_news(code),
            lambda: self._fallback.get_news(code),
        )

    def get_industry_boards(self) -> list[BoardInfo]:
        return self._call(
            "industry_boards",
            self._primary.get_industry_boards,
            self._fallback.get_industry_boards,
        )

    def get_concept_boards(self) -> list[BoardInfo]:
        return self._call(
            "concept_boards",
            self._primary.get_concept_boards,
            self._fallback.get_concept_boards,
        )

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        return self._call(
            "capital_flow",
            lambda: self._primary.get_capital_flow(code),
            lambda: self._fallback.get_capital_flow(code),
        )

    def get_financials(self, code: str) -> list[FinancialMetrics]:
        return self._call(
            "financials",
            lambda: self._primary.get_financials(code),
            lambda: self._fallback.get_financials(code),
        )

    # ── 核心切换逻辑 ─────────────────────────────────────────────────

    def _call(self, endpoint: str, primary_fn, fallback_fn):
        """执行一次带故障切换的调用

        Args:
            endpoint: endpoint 名称（用于独立计数）
            primary_fn: 主源调用函数
            fallback_fn: 备用源调用函数

        Returns:
            数据列表，两者都失败时返回空列表
        """
        if self._using_fallback[endpoint]:
            # 当前已切到备用 — 每次先尝试恢复主源
            try:
                result = primary_fn()
                self._consecutive_failures[endpoint] = 0
                self._using_fallback[endpoint] = False
                logger.info("主数据源恢复，切回主源: endpoint=%s", endpoint)
                return result
            except Exception:
                logger.debug("主数据源仍未恢复: endpoint=%s", endpoint)

            # 主源仍不可用，使用备用
            try:
                result = fallback_fn()
                # 备用成功 → 保持备用
                return result
            except Exception:
                logger.warning("备用数据源也失败: endpoint=%s", endpoint)
                self._consecutive_failures[endpoint] += 1
                return []

        # 尝试主源
        try:
            result = primary_fn()
            self._consecutive_failures[endpoint] = 0  # 成功则重置计数
            return result
        except Exception:
            self._consecutive_failures[endpoint] += 1
            logger.warning(
                "主数据源失败 (%d/%d): endpoint=%s",
                self._consecutive_failures[endpoint],
                self._max_failures,
                endpoint,
            )

            if self._consecutive_failures[endpoint] >= self._max_failures:
                # 超过阈值，切到备用
                self._using_fallback[endpoint] = True
                logger.info("切到备用数据源: endpoint=%s", endpoint)
                try:
                    return fallback_fn()
                except Exception:
                    logger.warning("备用数据源也失败: endpoint=%s", endpoint)
                    return []

            return []

    @property
    def fallback_mode(self) -> dict[str, bool]:
        """当前各 endpoint 是否使用备用源"""
        return dict(self._using_fallback)

    def reset(self, endpoint: str | None = None) -> None:
        """重置故障计数，切回主源

        Args:
            endpoint: 指定 endpoint，None 则重置全部
        """
        if endpoint:
            self._consecutive_failures[endpoint] = 0
            self._using_fallback[endpoint] = False
        else:
            self._consecutive_failures.clear()
            self._using_fallback.clear()


__all__ = ["FallbackSource"]

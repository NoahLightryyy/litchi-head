"""A 股数据采集器 —— 封装数据源 Provider 层

核心设计：
1. 所有数据源调用通过 DataSource 协议接口，不直接调具体库
2. 缓存层（TTL）减少请求频率
3. 健康监控记录每个 endpoint 的调用次数/失败率/延迟
4. 默认使用 AKShareSource（向后兼容）

用法：
    collector = DataCollector()
    stocks = collector.get_all_stocks()       # 默认 akshare

    # 切换数据源
    from src.data.providers.adata import ADataSource
    collector = DataCollector(source=ADataSource())
"""

import logging
import time
from collections import defaultdict

from src.data.cache import DataCache
from src.data.models import (
    BoardInfo,
    BriefSection,
    CapitalFlowItem,
    KLine,
    MarketBrief,
    NewsItem,
    StockInfo,
    StockQuote,
)
from src.data.providers import AKShareSource, DataSource

logger = logging.getLogger("data.collector")

# ── 默认 TTL 常量（秒） ──────────────────────────────────────────────

TTL_STOCKS = 3600       # 股票列表：1 小时
TTL_QUOTES = 30         # 实时行情：30 秒
TTL_KLINES_DAILY = 300  # 日 K 线：5 分钟
TTL_NEWS = 120          # 新闻：2 分钟
TTL_BOARDS = 3600       # 板块：1 小时
TTL_CAPITAL_FLOW = 300  # 资金流向：5 分钟


# ── 健康监控 ────────────────────────────────────────────────────────


class HealthStats:
    """数据源健康统计

    跟踪每个 endpoint（如 "all_stocks"、"quotes"、"kline"）的调用情况。
    所有 DataCollector 方法通过 _track() 自动记录。

    Thread-safe: 因 GIL，Counter 自增和列表追加在当前环境下安全。
    """

    def __init__(self) -> None:
        self._total: defaultdict[str, int] = defaultdict(int)
        self._success: defaultdict[str, int] = defaultdict(int)
        self._failures: defaultdict[str, int] = defaultdict(int)
        self._last_error: dict[str, str] = {}
        self._last_success_ts: dict[str, float] = {}
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._window_size = 100  # 最多保留近 100 次延迟

    def record_call(self, endpoint: str, duration_ms: float, error: str | None = None) -> None:
        """记录一次调用结果"""
        self._total[endpoint] += 1
        if error:
            self._failures[endpoint] += 1
            self._last_error[endpoint] = error
        else:
            self._success[endpoint] += 1
            self._last_success_ts[endpoint] = time.time()

        bucket = self._latencies[endpoint]
        bucket.append(duration_ms)
        if len(bucket) > self._window_size:
            bucket.pop(0)

    def snapshot(self) -> dict[str, object]:
        """返回当前快照（用于 HTTP 暴露）"""
        now = time.time()
        result: dict[str, object] = {}
        endpoints = sorted(set(self._total) | set(self._success) | set(self._failures))

        for ep in endpoints:
            total = self._total.get(ep, 0)
            fails = self._failures.get(ep, 0)
            lat = self._latencies.get(ep, [])
            result[ep] = {
                "total_calls": total,
                "success": self._success.get(ep, 0),
                "failures": fails,
                "failure_rate": round(fails / total, 4) if total > 0 else 0.0,
                "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else None,
                "last_error": self._last_error.get(ep, None),
                "last_success_ago_s": round(now - self._last_success_ts[ep], 1)
                    if ep in self._last_success_ts else None,
            }

        # 全局汇总
        total_calls = sum(self._total.values())
        total_fails = sum(self._failures.values())
        result["__summary__"] = {
            "total_calls": total_calls,
            "total_failures": total_fails,
            "overall_failure_rate": round(total_fails / total_calls, 4) if total_calls > 0 else 0.0,
            "healthy_endpoints": sum(1 for ep in endpoints if self._failures.get(ep, 0) == 0),
            "failing_endpoints": sum(1 for ep in endpoints if self._failures.get(ep, 0) > 0),
        }
        return result


# ── 全局健康统计实例（单例） ─────────────────────────────────────────

_health_stats = HealthStats()


def get_health_stats() -> HealthStats:
    """获取全局健康统计实例"""
    return _health_stats


# ── DataCollector ────────────────────────────────────────────────────


class DataCollector:
    """A 股数据采集器

    通过 DataSource 协议接口获取数据，提供缓存和健康监控能力。
    默认使用 AKShareSource（向后兼容）。

    可通过 `default_source` 类变量全局配置数据源（生产环境下使用）：

    Args:
        source: 数据源实现，None 则使用 default_source 或 AKShareSource
        cache: 可选的 DataCache 实例，不传则新建
    """

    # 可全局切换的数据源（生产配置用）
    default_source: DataSource | None = None

    def __init__(self, source: DataSource | None = None, cache: DataCache | None = None):
        self._source = source or DataCollector.default_source or AKShareSource()
        self.cache = cache or DataCache()

    # ── 股票信息 ─────────────────────────────────────────────────────

    def get_all_stocks(self) -> list[StockInfo]:
        """获取全部 A 股股票代码和名称

        Cache TTL: 1 小时

        Returns:
            股票信息列表，网络异常时返回空列表
        """
        cached = self.cache.get("all_stocks")
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_all_stocks()
            self.cache.set("all_stocks", result, ttl=TTL_STOCKS)
            _health_stats.record_call("all_stocks", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("all_stocks", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取股票列表失败")
            return []

    # ── 实时行情 ─────────────────────────────────────────────────────

    def get_realtime_quotes(self) -> list[StockQuote]:
        """获取全市场实时行情

        Cache TTL: 30 秒

        Returns:
            行情列表，网络异常时返回空列表
        """
        cached = self.cache.get("all_quotes")
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_realtime_quotes()
            self.cache.set("all_quotes", result, ttl=TTL_QUOTES)
            _health_stats.record_call("quotes", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("quotes", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取实时行情失败")
            return []

    def get_realtime_quote(self, code: str) -> StockQuote | None:
        """获取单只股票实时行情

        从全市场行情中过滤指定股票。
        推荐批量场景使用 get_realtime_quotes() 后自行过滤。

        Args:
            code: 股票代码，如 "000001"

        Returns:
            行情对象，未找到或网络异常返回 None
        """
        quotes = self.get_realtime_quotes()
        for q in quotes:
            if q.code == code:
                return q
        return None

    # ── K 线数据 ─────────────────────────────────────────────────────

    def get_klines(
        self,
        code: str,
        period: str = "daily",
        start: str = "",
        end: str = "",
        adjust: str = "qfq",
    ) -> list[KLine]:
        """获取个股历史 K 线

        Cache TTL: 5 分钟（日线）

        Args:
            code: 股票代码，如 "000001"
            period: 周期 "daily" / "weekly" / "monthly"
            start: 开始日期 "YYYY-MM-DD"，默认取全部
            end: 结束日期 "YYYY-MM-DD"，默认取全部
            adjust: 复权方式 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)

        Returns:
            K 线列表，网络异常时返回空列表
        """
        cache_key = f"klines:{code}:{period}:{adjust}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_klines(
                code, period=period, start=start, end=end, adjust=adjust,
            )
            ttl = TTL_KLINES_DAILY if period == "daily" else 60
            self.cache.set(cache_key, result, ttl=ttl)
            _health_stats.record_call(f"kline:{period}", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call(f"kline:{period}", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取 K 线失败: code=%s", code)
            return []

    # ── 新闻 ─────────────────────────────────────────────────────────

    def get_news(self, code: str) -> list[NewsItem]:
        """获取个股新闻

        Cache TTL: 2 分钟

        Args:
            code: 股票代码，如 "000001"

        Returns:
            新闻列表，网络异常时返回空列表
        """
        cache_key = f"news:{code}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_news(code)
            self.cache.set(cache_key, result, ttl=TTL_NEWS)
            _health_stats.record_call("news", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("news", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取新闻失败: code=%s", code)
            return []

    # ── 板块 ─────────────────────────────────────────────────────────

    def get_industry_boards(self) -> list[BoardInfo]:
        """获取行业板块列表

        Cache TTL: 1 小时

        Returns:
            行业板块列表，网络异常时返回空列表
        """
        cached = self.cache.get("industry_boards")
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_industry_boards()
            self.cache.set("industry_boards", result, ttl=TTL_BOARDS)
            _health_stats.record_call("industry_boards", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("industry_boards", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取行业板块列表失败")
            return []

    def get_concept_boards(self) -> list[BoardInfo]:
        """获取概念板块列表

        Cache TTL: 1 小时

        Returns:
            概念板块列表，网络异常时返回空列表
        """
        cached = self.cache.get("concept_boards")
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_concept_boards()
            self.cache.set("concept_boards", result, ttl=TTL_BOARDS)
            _health_stats.record_call("concept_boards", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("concept_boards", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取概念板块列表失败")
            return []

    # ── 资金流向 ─────────────────────────────────────────────────────

    def get_capital_flow(self, code: str) -> list[CapitalFlowItem]:
        """获取个股资金流向

        Cache TTL: 5 分钟

        Args:
            code: 股票代码，如 "000001"

        Returns:
            CapitalFlowItem 列表，网络异常时返回空列表
        """
        cache_key = f"capital_flow:{code}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        t0 = time.time()
        try:
            result = self._source.get_capital_flow(code)
            self.cache.set(cache_key, result, ttl=TTL_CAPITAL_FLOW)
            _health_stats.record_call("capital_flow", (time.time() - t0) * 1000)
            return result
        except Exception as e:
            _health_stats.record_call("capital_flow", (time.time() - t0) * 1000, error=str(e))
            logger.exception("获取资金流向失败: code=%s", code)
            return []


# ── 市场简报 ────────────────────────────────────────────────────────────


def format_market_brief(
    stock_code: str,
    stock_name: str,
    quote: StockQuote | None = None,
    klines: list[KLine] | None = None,
    news: list[NewsItem] | None = None,
) -> str:
    """生成结构化市场简报（C1 分区输出）

    按 4 层分区输出：行情层 / 新闻层 / 情绪层 / 基本面层。
    各层使用 ``----- 层名 -----`` 视觉分隔线，让 LLM 能按需聚焦。
    情绪层和基本面层为占位区段，待后续 C2/C3 接入实际数据源。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        quote: 个股实时行情（已过滤）
        klines: K 线数据
        news: 新闻列表

    Returns:
        格式化文本，以 "📊 市场简报" 开头
    """
    brief = MarketBrief(stock_code=stock_code, stock_name=stock_name)

    # ── 行情层 ──
    quote_lines: list[str] = []
    has_quote = False

    if quote is not None:
        has_quote = True
        parts = [f"最新价 {quote.price:.2f} 元"]
        if quote.change_pct:
            parts.append(f"涨幅 {quote.change_pct:+.2f}%")
        parts.append(f"成交量 {quote.volume:,} 手")
        quote_lines.append(" | ".join(parts))

        kp_parts: list[str] = []
        if quote.open_:
            kp_parts.append(f"今开 {quote.open_:.2f}")
        if quote.prev_close:
            kp_parts.append(f"昨收 {quote.prev_close:.2f}")
        if quote.high:
            kp_parts.append(f"最高 {quote.high:.2f}")
        if quote.low:
            kp_parts.append(f"最低 {quote.low:.2f}")
        if kp_parts:
            quote_lines.append(" | ".join(kp_parts))

    if klines and len(klines) >= 2:
        closes = [k.close for k in klines if k.close > 0]
        if len(closes) >= 2:
            has_quote = True
            avg_price = sum(closes) / len(closes)
            quote_lines.append(
                f"近 {len(klines)} 个交易日 | "
                f"收盘价 {closes[-1]:.2f} → {closes[0]:.2f} | "
                f"均价 {avg_price:.2f}"
            )

    brief.sections["quotes"] = BriefSection(
        title="行情层",
        content="\n".join(quote_lines) if quote_lines else "暂无行情数据",
        has_data=has_quote,
    )

    # ── 新闻层 ──
    news_lines: list[str] = []
    has_news = bool(news)
    if news:
        for n in news[:5]:
            news_lines.append(f"• {n.title or '(无标题)'}")
    if not news_lines:
        news_lines.append("暂无新闻数据")

    brief.sections["news"] = BriefSection(
        title="新闻层",
        content="\n".join(news_lines),
        has_data=has_news,
    )

    # ── 情绪层（占位） ──
    brief.sections["sentiment"] = BriefSection(
        title="情绪层",
        content="暂无情绪数据",
        has_data=False,
    )

    # ── 基本面层（占位） ──
    brief.sections["fundamentals"] = BriefSection(
        title="基本面层",
        content="暂无基本面数据",
        has_data=False,
    )

    return brief.to_text()


__all__ = ["DataCollector", "format_market_brief", "get_health_stats", "HealthStats"]

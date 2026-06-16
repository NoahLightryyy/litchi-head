"""A 股数据采集器 —— 封装 akshare 调用

核心设计：
1. 所有 akshare 调用通过缓存层，减少请求频率
2. 返回 Pydantic 模型（数据契约，遵循 ADR-001/008）
3. 错误处理：网络异常返回空列表，不抛异常（"尽力而为"原则）
4. 日志记录所有操作和异常
5. 健康监控：每个 endpoint 记录调用次数、失败次数、延迟，可对外暴露

用法：
    collector = DataCollector()
    stocks = collector.get_all_stocks()
    quotes = collector.get_realtime_quotes()
"""

import logging
import time
from collections import defaultdict

import akshare as ak
import pandas as pd

from src.data.cache import DataCache
from src.data.models import (
    BoardInfo,
    BriefSection,
    KLine,
    MarketBrief,
    NewsItem,
    StockInfo,
    StockQuote,
)

logger = logging.getLogger("data.collector")

# ── 默认 TTL 常量（秒） ──────────────────────────────────────────────

TTL_STOCKS = 3600       # 股票列表：1 小时
TTL_QUOTES = 30         # 实时行情：30 秒
TTL_KLINES_DAILY = 300  # 日 K 线：5 分钟
TTL_NEWS = 120          # 新闻：2 分钟
TTL_BOARDS = 3600       # 板块：1 小时


# ── 健康监控 ────────────────────────────────────────────────────────


class HealthStats:
    """数据源健康统计

    跟踪每个 endpont（如 "all_stocks"、"quotes"、"kline"）的调用情况。
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

        # 延迟记录（滑动窗口）
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

    封装 akshare 调用，提供类型化返回值和缓存能力。
    所有方法均为同步，内部使用 requests 阻塞调用（akshare 原生模式）。

    Args:
        cache: 可选的 DataCache 实例，不传则新建
    """

    def __init__(self, cache: DataCache | None = None):
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
            df = ak.stock_info_a_code_name()
            result = [
                StockInfo(code=str(row["code"]), name=str(row["name"]))
                for _, row in df.iterrows()
            ]
            self.cache.set("all_stocks", result, ttl=TTL_STOCKS)
            _health_stats.record_call("all_stocks", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call("all_stocks", (time.time() - t0) * 1000, error="获取股票列表失败")
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
            df = ak.stock_zh_a_spot_em()
            result = [_row_to_quote(row) for _, row in df.iterrows()]
            self.cache.set("all_quotes", result, ttl=TTL_QUOTES)
            _health_stats.record_call("quotes", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call("quotes", (time.time() - t0) * 1000, error="获取实时行情失败")
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
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust=adjust,
            )
            result = [_row_to_kline(row) for _, row in df.iterrows()]
            ttl = TTL_KLINES_DAILY if period == "daily" else 60
            self.cache.set(cache_key, result, ttl=ttl)
            _health_stats.record_call(f"kline:{period}", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call(f"kline:{period}", (time.time() - t0) * 1000, error=f"获取 K 线失败 code={code}")
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
            df = ak.stock_news_em(symbol=code)
            result = [_row_to_news(row, code) for _, row in df.iterrows()]
            self.cache.set(cache_key, result, ttl=TTL_NEWS)
            _health_stats.record_call("news", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call("news", (time.time() - t0) * 1000, error=f"获取新闻失败 code={code}")
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
            df = ak.stock_board_industry_name_em()
            result = [
                BoardInfo(
                    code=str(row["板块代码"]),
                    name=str(row["板块名称"]),
                    board_type="industry",
                )
                for _, row in df.iterrows()
            ]
            self.cache.set("industry_boards", result, ttl=TTL_BOARDS)
            _health_stats.record_call("industry_boards", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call("industry_boards", (time.time() - t0) * 1000, error="获取行业板块列表失败")
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
            df = ak.stock_board_concept_name_em()
            result = [
                BoardInfo(
                    code=str(row["板块代码"]),
                    name=str(row["板块名称"]),
                    board_type="concept",
                )
                for _, row in df.iterrows()
            ]
            self.cache.set("concept_boards", result, ttl=TTL_BOARDS)
            _health_stats.record_call("concept_boards", (time.time() - t0) * 1000)
            return result
        except Exception:
            _health_stats.record_call("concept_boards", (time.time() - t0) * 1000, error="获取概念板块列表失败")
            logger.exception("获取概念板块列表失败")
            return []


# ── DataFrame → Model 转换函数 ────────────────────────────────────────


def _row_to_quote(row: pd.Series) -> StockQuote:
    """将 akshare 实时行情的 DataFrame 行转换为 StockQuote"""
    return StockQuote(
        code=_safe_str(row, "代码"),
        name=_safe_str(row, "名称"),
        price=_safe_float(row, "最新价"),
        change=_safe_float(row, "涨跌额"),
        change_pct=_safe_float(row, "涨跌幅"),
        volume=_safe_int(row, "成交量"),
        amount=_safe_float(row, "成交额"),
        high=_safe_float(row, "最高"),
        low=_safe_float(row, "最低"),
        open_=_safe_float(row, "今开"),
        prev_close=_safe_float(row, "昨收"),
    )


def _row_to_kline(row: pd.Series) -> KLine:
    """将 akshare K 线 DataFrame 行转换为 KLine"""
    return KLine(
        date=_safe_str(row, "日期"),
        open=_safe_float(row, "开盘"),
        close=_safe_float(row, "收盘"),
        high=_safe_float(row, "最高"),
        low=_safe_float(row, "最低"),
        volume=_safe_int(row, "成交量"),
        amount=_safe_float(row, "成交额"),
    )


def _row_to_news(row: pd.Series, code: str) -> NewsItem:
    """将 akshare 新闻 DataFrame 行转换为 NewsItem"""
    return NewsItem(
        code=code,
        title=_safe_str(row, "title"),
        date=_safe_str(row, "date"),
        content=_safe_str(row, "content"),
        source=_safe_str(row, "source"),
        url=_safe_str(row, "url"),
    )


def _safe_str(row: pd.Series, key: str) -> str:
    """安全地从 Series 提取 str 值"""
    try:
        val = row.get(key, "")
        if val is None or (hasattr(val, "__len__") and len(val) == 0):
            return ""
        return str(val)
    except (ValueError, TypeError):
        return ""


def _safe_float(row: pd.Series, key: str) -> float:
    """安全地从 Series 提取 float 值"""
    try:
        val: object = row.get(key, 0.0)
        if val is None:
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(row: pd.Series, key: str) -> int:
    """安全地从 Series 提取 int 值"""
    try:
        val: object = row.get(key, 0)
        if val is None:
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


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

        # 关键价位
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

    # 近期走势（并入行情层）
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


__all__ = ["DataCollector", "format_market_brief"]

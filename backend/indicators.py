"""技术指标计算模块 —— MA / RSI / MACD / Bollinger Bands

全部从 K 线数据（list[dict]）离线计算，无外部依赖。
"""

from __future__ import annotations

import math
from typing import Any


# ── 通用辅助 ──────────────────────────────────────────────────────


def _sma(values: list[float], period: int) -> list[float | None]:
    """简单移动平均

    Args:
        values: 输入序列（最新在末尾）
        period: 窗口大小

    Returns:
        与 values 等长，前 period-1 个为 None
    """
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period
    return result


def _ema(values: list[float], period: int) -> list[float | None]:
    """指数移动平均

    Args:
        values: 输入序列（最新在末尾）
        period: 窗口大小

    Returns:
        与 values 等长，前 period-1 个为 None
    """
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    multiplier = 2.0 / (period + 1)
    # 第一个 EMA 用 SMA 种子
    ema = sum(values[:period]) / period
    result[period - 1] = ema
    for i in range(period, len(values)):
        ema = (values[i] - ema) * multiplier + ema
        result[i] = ema
    return result


def _stddev(values: list[float], period: int) -> list[float | None]:
    """滚动标准差

    Args:
        values: 输入序列（最新在末尾）
        period: 窗口大小

    Returns:
        与 values 等长，前 period-1 个为 None
    """
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        result[i] = math.sqrt(variance)
    return result


# ── 核心指标 ──────────────────────────────────────────────────────


def calc_ma(
    klines: list[dict[str, Any]], periods: list[int] | None = None
) -> dict[str, list[float | None]]:
    """计算多周期移动平均线

    Args:
        klines: K 线列表，每项含 'close'
        periods: 周期列表，默认 [5, 10, 20, 60]

    Returns:
        {"ma5": [...], "ma10": [...], ...}
    """
    if periods is None:
        periods = [5, 10, 20, 60]
    closes = [float(k["close"]) for k in klines]
    return {f"ma{p}": _sma(closes, p) for p in periods}


def calc_rsi(
    klines: list[dict[str, Any]], period: int = 14
) -> list[float | None]:
    """相对强弱指标 RSI

    Args:
        klines: K 线列表，每项含 'close'
        period: 周期，默认 14

    Returns:
        与 klines 等长，前 period 个为 None
    """
    closes = [float(k["close"]) for k in klines]
    result: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    # 计算每日变化
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # 首周期 SMA 种子
    avg_gain = sum(max(d, 0) for d in deltas[:period]) / period
    avg_loss = sum(max(-d, 0) for d in deltas[:period]) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - 100.0 / (1.0 + rs)

    # 后续用 EMA 递推
    for i in range(period, len(deltas)):
        gain = max(deltas[i], 0)
        loss = max(-deltas[i], 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100.0 - 100.0 / (1.0 + rs)

    return result


def calc_macd(
    klines: list[dict[str, Any]],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float | None]]:
    """MACD 指标

    Args:
        klines: K 线列表，每项含 'close'
        fast: 快线周期，默认 12
        slow: 慢线周期，默认 26
        signal: 信号线周期，默认 9

    Returns:
        {"macd": [...], "signal": [...], "histogram": [...]}
    """
    closes = [float(k["close"]) for k in klines]
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    macd_line: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]  # type: ignore[operator]

    # 信号线 = MACD 的 EMA
    macd_values: list[float] = [v for v in macd_line if v is not None]
    sig = _ema(macd_values, signal) if macd_values else []

    signal_line: list[float | None] = [None] * len(closes)
    histogram: list[float | None] = [None] * len(closes)
    # 找到第一个非 None 的 macd 位置
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), -1)
    for j, s in enumerate(sig):
        idx = first_valid + j
        if idx < len(closes) and macd_line[idx] is not None and s is not None:
            signal_line[idx] = s
            macd_val: float = macd_line[idx]  # pyright: ignore[reportAssignmentType]
            histogram[idx] = macd_val - s

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calc_bollinger(
    klines: list[dict[str, Any]], period: int = 20, multiplier: float = 2.0
) -> dict[str, list[float | None]]:
    """布林带

    Args:
        klines: K 线列表，每项含 'close'
        period: 周期，默认 20
        multiplier: 标准差倍数，默认 2.0

    Returns:
        {"upper": [...], "middle": [...], "lower": [...]}
    """
    closes = [float(k["close"]) for k in klines]
    middle = _sma(closes, period)
    std = _stddev(closes, period)

    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if middle[i] is not None and std[i] is not None:
            upper[i] = middle[i] + multiplier * std[i]  # type: ignore[operator]
            lower[i] = middle[i] - multiplier * std[i]  # type: ignore[operator]

    return {"upper": upper, "middle": middle, "lower": lower}


def _latest_bollinger(
    bollinger: dict[str, list[float | None]], last: int
) -> dict[str, float | None]:
    """安全提取布林带最新值（绕 Pyright None 类型收窄）"""
    upper_raw = bollinger["upper"][last] if last >= 0 else None
    middle_raw = bollinger["middle"][last] if last >= 0 else None
    lower_raw = bollinger["lower"][last] if last >= 0 else None
    return {
        "upper": round(upper_raw, 2) if isinstance(upper_raw, (int, float)) else None,
        "middle": round(middle_raw, 2) if isinstance(middle_raw, (int, float)) else None,
        "lower": round(lower_raw, 2) if isinstance(lower_raw, (int, float)) else None,
    }


# ── 聚合接口 ──────────────────────────────────────────────────────


def calc_all(klines: list[dict[str, Any]]) -> dict[str, Any]:
    """计算全部技术指标

    Args:
        klines: K 线列表（最新在末尾），每项含 'close'

    Returns:
        包含 ma/rsi/macd/bollinger 的完整字典
    """
    ma = calc_ma(klines)
    rsi = calc_rsi(klines)
    macd = calc_macd(klines)
    bollinger = calc_bollinger(klines)

    # 取最新值摘要
    last = len(klines) - 1
    latest_rsi = None
    if last >= 0 and rsi[last] is not None:
        latest_rsi = round(float(rsi[last]), 2)  # type: ignore[arg-type]

    latest_macd = None
    latest_signal = None
    latest_histogram = None
    if last >= 0:
        if macd["macd"][last] is not None:
            latest_macd = round(float(macd["macd"][last]), 4)  # type: ignore[arg-type]
        if macd["signal"][last] is not None:
            latest_signal = round(float(macd["signal"][last]), 4)  # type: ignore[arg-type]
        if macd["histogram"][last] is not None:
            latest_histogram = round(float(macd["histogram"][last]), 4)  # type: ignore[arg-type]

    return {
        "ma": {k: (v[-1] if v and v[-1] is not None else None) for k, v in ma.items()},
        "ma_series": ma,
        "rsi": latest_rsi,
        "rsi_series": rsi,
        "macd": {
            "value": latest_macd,
            "signal": latest_signal,
            "histogram": latest_histogram,
        },
        "macd_series": macd,
        "bollinger": _latest_bollinger(bollinger, last),
        "bollinger_series": bollinger,
    }

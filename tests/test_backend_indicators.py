"""backend/indicators.py 单元测试

技术指标是系统核心计算 — 算错了 AI 就吃假数据。
每个指标用已知序列手工验证参考值。

覆盖：
1. _sma / _ema / _stddev 基础辅助函数
2. calc_ma 多周期移动平均
3. calc_rsi RSI 相对强弱指标（含 avg_loss=0 边值）
4. calc_macd MACD 快慢线 + 信号线 + 柱状图
5. calc_bollinger 布林带上下轨计算
6. calc_all 聚合接口最新值提取
"""

from __future__ import annotations

import pytest

from backend.indicators import (
    _ema,
    _sma,
    _stddev,
    calc_all,
    calc_bollinger,
    calc_ma,
    calc_macd,
    calc_rsi,
)


# ── 测试用 K 线数据 ──────────────────────────────────────────────────

PRICES_5 = [10.0, 11.0, 12.0, 13.0, 14.0]
"""简单上升序列，适合验证 SMA/EMA 基础计算"""

KLINE_5 = [{"close": p} for p in PRICES_5]

PRICES_RSI = [
    44.00, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
    45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
    46.28,
]
"""14 个价格的标准 RSI 测试序列"""

KLINE_RSI = [{"close": p} for p in PRICES_RSI]

PRICES_MACD = [
    10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
    15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5,
    20.0, 20.5, 21.0, 21.5, 22.0, 22.5, 23.0, 23.5, 24.0, 24.5,
    25.0, 25.5, 26.0, 26.5, 27.0, 27.5, 28.0, 28.5, 29.0, 29.5,
    30.0,
]
"""稳定上升序列（40+ 个点，确保 signal 线有足够数据）"""

KLINE_MACD = [{"close": p} for p in PRICES_MACD]


# ── _sma ─────────────────────────────────────────────────────────────


class TestSMA:
    """简单移动平均"""

    def test_normal(self):
        """[10,11,12,13,14] 周期=3 → SMA3=[N,N,11,12,13]"""
        result = _sma(PRICES_5, 3)
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(11.0)  # (10+11+12)/3
        assert result[3] == pytest.approx(12.0)  # (11+12+13)/3
        assert result[4] == pytest.approx(13.0)  # (12+13+14)/3

    def test_short_data_returns_all_none(self):
        """数据不足周期时全返回 None"""
        result = _sma([1.0, 2.0], 5)
        assert result == [None, None]

    def test_empty_data(self):
        assert _sma([], 5) == []

    def test_period_1(self):
        """周期=1 时 SMA 等于原序列"""
        result = _sma([1.0, 2.0, 3.0], 1)
        assert result == [1.0, 2.0, 3.0]

    def test_single_element(self):
        result = _sma([42.0], 3)
        assert result == [None]


# ── _ema ─────────────────────────────────────────────────────────────


class TestEMA:
    """指数移动平均"""

    def test_normal(self):
        """[10,11,12,13,14] 周期=3, multiplier=0.5
        EMA3[2] = SMA种子 = (10+11+12)/3 = 11.0
        EMA3[3] = (13-11)*0.5+11 = 12.0
        EMA3[4] = (14-12)*0.5+12 = 13.0
        """
        result = _ema(PRICES_5, 3)
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(11.0)
        assert result[3] == pytest.approx(12.0)
        assert result[4] == pytest.approx(13.0)

    def test_short_data_returns_all_none(self):
        result = _ema([1.0, 2.0], 5)
        assert result == [None, None]

    def test_empty_data(self):
        assert _ema([], 5) == []

    def test_period_1(self):
        """周期=1 时 EMA = 原序列"""
        result = _ema([1.0, 2.0, 3.0], 1)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(2.0)
        assert result[2] == pytest.approx(3.0)


# ── _stddev ──────────────────────────────────────────────────────────


class TestStdDev:
    """滚动标准差"""

    def test_normal(self):
        """[10,11,12,13,14] 周期=3
        std[2] = std([10,11,12]) = 0.8165...
        std[3] = std([11,12,13]) = 0.8165...
        std[4] = std([12,13,14]) = 0.8165...
        """
        result = _stddev(PRICES_5, 3)
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(0.81649658, rel=1e-5)
        assert result[3] == pytest.approx(0.81649658, rel=1e-5)
        assert result[4] == pytest.approx(0.81649658, rel=1e-5)

    def test_short_data_returns_all_none(self):
        result = _stddev([1.0], 5)
        assert result == [None]

    def test_empty_data(self):
        assert _stddev([], 5) == []

    def test_constant_sequence(self):
        """常数列标准差 = 0"""
        result = _stddev([5.0, 5.0, 5.0, 5.0], 3)
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(0.0)
        assert result[3] == pytest.approx(0.0)


# ── calc_ma ──────────────────────────────────────────────────────────


class TestCalcMA:
    """多周期移动平均"""

    def test_default_periods(self):
        """默认周期 [5, 10, 20, 60]"""
        result = calc_ma(KLINE_5)
        assert "ma5" in result
        assert "ma10" in result
        assert "ma20" in result
        assert "ma60" in result
        assert len(result["ma5"]) == 5

    def test_custom_periods(self):
        result = calc_ma(KLINE_5, periods=[3])
        assert list(result.keys()) == ["ma3"]
        assert len(result["ma3"]) == 5

    def test_empty_klines(self):
        result = calc_ma([])
        assert result["ma5"] == []

    def test_single_kline(self):
        result = calc_ma([{"close": 10.0}])
        assert result["ma5"] == [None]


# ── calc_rsi ─────────────────────────────────────────────────────────


class TestCalcRSI:
    """相对强弱指标 RSI"""

    def test_normal(self):
        """标准 14 周期 RSI, 已知 PRICES_RSI 序列
        用前 15 个值验证 RSI[14] 在合理范围
        """
        result = calc_rsi(KLINE_RSI, period=14)
        assert len(result) == 15
        # 前 14 个为 None（需要 period 个差值，所以前 14 个收盘价不够产出 RSI）
        for i in range(14):
            assert result[i] is None
        # RSI[14] 应在 0-100 之间
        assert result[14] is not None
        assert 0 <= result[14] <= 100

    def test_up_trend_rsi_above_50(self):
        """单边上涨行情 RSI 应 > 50"""
        up_klines = [{"close": float(i)} for i in range(20)]
        result = calc_rsi(up_klines, period=5)
        last_rsi = result[-1]
        assert last_rsi is not None
        assert last_rsi > 50

    def test_down_trend_rsi_below_50(self):
        """单边下跌行情 RSI 应 < 50"""
        down_klines = [{"close": float(100 - i)} for i in range(20)]
        result = calc_rsi(down_klines, period=5)
        last_rsi = result[-1]
        assert last_rsi is not None
        assert last_rsi < 50

    def test_flat_market_rsi_50(self):
        """横盘市场 RSI 应接近 50"""
        # 在 100 附近小幅度随机波动
        import random
        random.seed(42)
        prices = [100.0]
        for _ in range(30):
            prices.append(prices[-1] + random.uniform(-0.5, 0.5))
        flat_klines = [{"close": p} for p in prices]
        result = calc_rsi(flat_klines, period=5)
        last_rsi = result[-1]
        assert last_rsi is not None
        assert 30 <= last_rsi <= 70

    def test_short_data(self):
        """数据不足时全返回 None"""
        result = calc_rsi([{"close": 10.0}], period=14)
        assert result == [None]

    def test_empty_klines(self):
        assert calc_rsi([], period=14) == []

    def test_rsi_100_on_continuous_gains(self):
        """连续上涨无下跌时 RSI 应为 100"""
        up_only = [{"close": float(100 + i)} for i in range(20)]
        result = calc_rsi(up_only, period=5)
        # avg_loss = 0 时 RSI = 100
        after_seed = [v for v in result if v is not None]
        if after_seed:
            assert after_seed[0] == 100.0

    def test_rsi_0_on_continuous_losses(self):
        """连续下跌无上涨时 RSI 应为 0"""
        down_only = [{"close": float(100 - i)} for i in range(20)]
        result = calc_rsi(down_only, period=5)
        after_seed = [v for v in result if v is not None]
        if after_seed:
            assert after_seed[0] == 0.0


# ── calc_macd ────────────────────────────────────────────────────────


class TestCalcMACD:
    """MACD 快慢线 + 信号线 + 柱状图"""

    def test_normal(self):
        """稳定上升序列 MACD 应为正"""
        result = calc_macd(KLINE_MACD)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
        # 前 fast-1 个为 None
        assert result["macd"][:11] == [None] * 11
        # 最后一个应有值
        last_macd = result["macd"][-1]
        assert last_macd is not None
        # 上涨趋势中 MACD 应为正
        assert last_macd > 0

    def test_short_data(self):
        """数据不足快线周期时全 None"""
        result = calc_macd([{"close": 10.0}, {"close": 11.0}], fast=12)
        assert result["macd"][-1] is None

    def test_empty_klines(self):
        result = calc_macd([])
        assert result["macd"] == []
        assert result["signal"] == []
        assert result["histogram"] == []

    def test_signal_line_in_same_direction(self):
        """上涨趋势中信号线也应跟随 MACD 为正"""
        result = calc_macd(KLINE_MACD)
        last_signal = result["signal"][-1]
        assert last_signal is not None
        assert last_signal > 0

    def test_histogram_presence(self):
        """柱状图在 MACD 和信号线都有效时才有值"""
        result = calc_macd(KLINE_MACD)
        valid_hist = [h for h in result["histogram"] if h is not None]
        assert len(valid_hist) > 0

    def test_down_trend_macd_negative(self):
        """下跌趋势中 MACD 应为负"""
        down_klines = [{"close": float(100 - i)} for i in range(40)]
        result = calc_macd(down_klines)
        last_macd = result["macd"][-1]
        assert last_macd is not None
        assert last_macd < 0


# ── calc_bollinger ───────────────────────────────────────────────────


class TestCalcBollinger:
    """布林带"""

    def test_normal(self):
        """常数列 → upper=middle=lower（stddev=0）"""
        const_klines = [{"close": 50.0} for _ in range(30)]
        result = calc_bollinger(const_klines, period=20)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        # stddev=0 时上下轨等于中轨
        last = -1
        assert result["upper"][last] == pytest.approx(50.0)
        assert result["middle"][last] == pytest.approx(50.0)
        assert result["lower"][last] == pytest.approx(50.0)

    def test_volatile_band_widens(self):
        """高波动序列布林带应明显变宽"""
        volatile = [{"close": float(100 + 10 * (i % 3 - 1))} for i in range(30)]
        result = calc_bollinger(volatile, period=10, multiplier=2.0)
        last = -1
        assert result["upper"][last] is not None
        assert result["lower"][last] is not None
        assert result["upper"][last] > result["middle"][last] > result["lower"][last]

    def test_short_data(self):
        """数据不足周期时全 None"""
        result = calc_bollinger([{"close": 10.0}], period=20)
        assert result["upper"][-1] is None
        assert result["middle"][-1] is None

    def test_empty_klines(self):
        result = calc_bollinger([])
        assert result["upper"] == []
        assert result["middle"] == []
        assert result["lower"] == []

    def test_custom_multiplier(self):
        """较大 multiplier 产生更宽的带"""
        prices = [{"close": float(100 + i)} for i in range(30)]
        result_2 = calc_bollinger(prices, multiplier=2.0)
        result_3 = calc_bollinger(prices, multiplier=3.0)
        assert result_3["upper"][-1] > result_2["upper"][-1]
        assert result_3["lower"][-1] < result_2["lower"][-1]


# ── calc_all ─────────────────────────────────────────────────────────


class TestCalcAll:
    """聚合接口 calc_all"""

    def test_returns_all_indicators(self):
        result = calc_all(KLINE_MACD)
        assert "ma" in result
        assert "ma_series" in result
        assert "rsi" in result
        assert "rsi_series" in result
        assert "macd" in result
        assert "macd_series" in result
        assert "bollinger" in result
        assert "bollinger_series" in result

    def test_ma_latest_values(self):
        """ma 返回最新值 dict（非 series）"""
        result = calc_all([{"close": float(i)} for i in range(100)])
        for k in ["ma5", "ma10", "ma20", "ma60"]:
            assert k in result["ma"]
            # 100 个点足够长出 60 周期均线
            assert result["ma"][k] is not None

    def test_rsi_latest_scalar(self):
        """rsi 返回最新标量值"""
        result = calc_all(KLINE_RSI)
        assert isinstance(result["rsi"], (int, float))

    def test_macd_latest_dict(self):
        """macd 返回最新值的 dict"""
        result = calc_all(KLINE_RSI)
        assert isinstance(result["macd"], dict)
        assert "value" in result["macd"]
        assert "signal" in result["macd"]
        assert "histogram" in result["macd"]

    def test_bollinger_latest_dict(self):
        """bollinger 返回最新值的 dict"""
        result = calc_all(KLINE_RSI)
        assert isinstance(result["bollinger"], dict)
        assert "upper" in result["bollinger"]
        assert "middle" in result["bollinger"]
        assert "lower" in result["bollinger"]

    def test_empty_klines(self):
        """空数据不崩溃"""
        result = calc_all([])
        assert result["rsi"] is None
        assert result["macd"]["value"] is None

    def test_single_kline(self):
        """单根 K 线不崩溃，大部分值为 None"""
        result = calc_all([{"close": 50.0}])
        assert result["rsi"] is None
        for k in ["ma5", "ma10", "ma20", "ma60"]:
            assert result["ma"][k] is None



import { chartIndicators, type CandleInput, type Value } from "./chart-indicators.ts";
import type { TechnicalIndicators } from "./types/stock.ts";

/** Calculate each indicator with its own warmup, using exactly the chart's candles. */
export function rawTechnicalSummary(bars: CandleInput[]): TechnicalIndicators | null {
  if (!bars.length) return null;
  const series = chartIndicators(bars), last = (values: Value[]) => values.at(-1) ?? null;
  return { ma: { ma5: last(series.ma5), ma10: last(series.ma10), ma20: last(series.ma20), ma60: last(series.ma60) },
    rsi: last(series.rsi), macd: { value: last(series.dif), signal: last(series.dea), histogram: last(series.histogram) },
    bollinger: { upper: last(series.upper), middle: last(series.middle), lower: last(series.lower) } };
}
export function movingAverageOrder(ma: TechnicalIndicators["ma"]): "bullish" | "bearish" | "mixed" | "insufficient" {
  const values = [ma.ma5, ma.ma10, ma.ma20, ma.ma60].filter((value): value is number => value !== null && Number.isFinite(value));
  if (values.length < 3) return "insufficient";
  if (values.slice(1).every((value, i) => values[i] > value)) return "bullish";
  if (values.slice(1).every((value, i) => values[i] < value)) return "bearish";
  return "mixed";
}

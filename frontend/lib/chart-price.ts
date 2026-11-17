import type { CandleInput } from "./chart-indicators.ts";
import type { candleChange } from "./chart-navigation.ts";

export type PricePrecision = 2 | 3;

/** Price labels and series scale use the same precision; percentages remain two decimals. */
export function priceSeriesFormat(precision: PricePrecision = 2) {
  return { type: "price" as const, precision, minMove: 10 ** -precision };
}

export function candlePriceFields(
  candle: CandleInput,
  change: ReturnType<typeof candleChange>,
  priceUnit = "元",
  precision: PricePrecision = 2,
): Record<string, string> {
  const signed = (value: number, digits: number) => `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
  return {
    date: candle.date,
    close: candle.close.toFixed(precision),
    open: candle.open.toFixed(precision),
    high: candle.high.toFixed(precision),
    low: candle.low.toFixed(precision),
    change: change ? `${signed(change.amount, precision)} ${priceUnit}  (${signed(change.percent, 2)}%)` : "—",
    baseline: change ? "较前一根收盘" : "缺少前收盘价",
  };
}

import type { parseRawDaily } from "./raw-daily";

type Bar = ReturnType<typeof parseRawDaily>["bars"][number];
export type DisplayPeriod = "daily" | "weekly" | "monthly";
export const periodLabels = {daily: "日线", weekly: "周线", monthly: "月线"} as const;

/** Input is an already validated, ordered, single-source RAW daily series. */
export function aggregateRawPeriod(bars: Bar[], period: DisplayPeriod): Bar[] {
  if (period === "daily") return bars;
  const result: Bar[] = [];
  let previousKey = "";
  for (const bar of bars) {
    const date = new Date(`${bar.date}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7);
    const key = period === "weekly" ? date.toISOString().slice(0, 10) : bar.date.slice(0, 7);
    if (key !== previousKey) {
      result.push({...bar});
      previousKey = key;
    } else {
      const bucket = result[result.length - 1];
      bucket.date = bar.date; // Last observed trading day, not an invented calendar date.
      bucket.high = Math.max(bucket.high, bar.high);
      bucket.low = Math.min(bucket.low, bar.low);
      bucket.close = bar.close;
      bucket.volume += bar.volume;
    }
  }
  return result;
}

import type { PriceWindow } from "./chart-zoom";
import type { FiveDayDisplay } from "./five-day-display";
import type { IntradayBattlefield } from "./types/stock";

/** An HTTP 200 with no usable series is a failed refresh, not a replacement chart. */
export class IntradayUnavailableError extends Error {
  readonly data: IntradayBattlefield;
  constructor(data: IntradayBattlefield) {
    super("当日分时来源暂不可用");
    this.name = "IntradayUnavailableError";
    this.data = data;
  }
}

export function requireIntradayDisplay(data: IntradayBattlefield, code: string): IntradayBattlefield {
  if (data.symbol !== code) throw new Error("分时证券代码不一致");
  if (!data.usable || !data.price_points.length) throw new IntradayUnavailableError(data);
  return data;
}

export function shanghaiDate(milliseconds: number): string {
  return new Date(milliseconds + 8 * 3600000).toISOString().slice(0, 10);
}

/** Slice existing validated minute history; never construct bars/volume or claim realtime. */
export function latestMinuteSession(data: FiveDayDisplay | undefined, code: string, now = Date.now()) {
  if (!data || data.symbol !== code || data.status !== "partial" || !data.points.length) return null;
  const day = data.days.at(-1);
  if (!day) return null;
  const points = data.points.filter(point => shanghaiDate(Date.parse(point.timestamp)) === day);
  const asOf = points.at(-1)?.timestamp;
  if (!asOf || Date.parse(asOf) > now) return null;
  return { day, points, asOf, isToday: day === shanghaiDate(now), incomplete: data.incomplete_days.includes(day) };
}

export function automaticPriceWindow(
  selected: PriceWindow | null, unavailable: boolean, backupPending: boolean, backupUsable: boolean,
): PriceWindow {
  return selected ?? (unavailable && !backupPending && !backupUsable ? "daily" : "intraday");
}

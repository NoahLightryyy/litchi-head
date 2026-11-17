import type { MarketEnvelope, MarketMeta, SectorItem } from "./types/market.ts";

export interface SectorFeedState {
  data?: MarketEnvelope<SectorItem[]>;
  isError: boolean;
  isPaused: boolean;
}

/** Source notes describe scope, not request failures or unusable values. */
export const SECTOR_SCOPE_NOTES = new Set([
  "BOARD_SNAPSHOT_MAY_BE_DELAYED", "BOARD_INDUSTRY_LEVELS_MIXED",
  "BOARD_CATALOG_QUOTE_MISSING", "SINA_BOARD_BASIS", "SOURCE_SERVICE_TIME_ONLY",
]);

/** The API aggregates both categories; a failure in one must not age the other. */
export function sectorCategoryMeta(meta: MarketMeta | undefined, category: string): MarketMeta | undefined {
  if (!meta || (category !== "industry" && category !== "concept")) return meta;
  const otherCategoryFailed = meta.failed_sources.length > 0 &&
    meta.failed_sources.every(source => (source === "industry" || source === "concept") && source !== category);
  const hidden = new Set(category === "concept" ? ["BOARD_INDUSTRY_LEVELS_MIXED", "BOARD_CATALOG_QUOTE_MISSING"] : []);
  if (otherCategoryFailed) {
    hidden.add("BOARD_HISTORY_ONLY");
    hidden.add("BOARD_REFRESH_FAILED");
  }
  return { ...meta,
    status: otherCategoryFailed && meta.status === "stale" ? "partial" : meta.status,
    failed_sources: otherCategoryFailed ? [] : meta.failed_sources,
    limitations: meta.limitations.filter(item => !hidden.has(item.code)),
  };
}

export function sectorFeedPriority(feed: SectorFeedState, category = "all"): number {
  if (!feed.data?.data.some(item => category === "all" || item.category === category)) return 3;
  const meta = sectorCategoryMeta(feed.data.meta, category)!;
  if (feed.isError || feed.isPaused || meta.status === "stale" ||
    meta.limitations.some(item => item.code === "BOARD_HISTORY_ONLY")) return 2;
  const sina = feed.data.data.every(item => item.source === "sina");
  const relevantFailure = meta.failed_sources.some(source => category === "all" ||
    source === category || (source !== "industry" && source !== "concept"));
  if (relevantFailure || meta.missing_codes.length || meta.limitations.some(item =>
    !SECTOR_SCOPE_NOTES.has(item.code) && !(sina && item.code === "FUND_FLOW_UNAVAILABLE"))) return 1;
  return 0;
}

export function preferredSectorSource(
  eastmoney: SectorFeedState, sina: SectorFeedState, category = "all",
): SectorItem["source"] {
  return sectorFeedPriority(sina, category) < sectorFeedPriority(eastmoney, category)
    ? "sina" : "eastmoney";
}

/** Always display timestamps in the market's timezone, independent of browser locale. */
export function sectorTimeRange(items: SectorItem[], source: SectorItem["source"]): string {
  const times = items.map(item => source === "sina" ? item.service_updated_at : item.as_of);
  const dates = times.filter((value): value is string => !!value)
    .map(value => new Date(value)).filter(value => Number.isFinite(value.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());
  if (!dates.length) return "来源未提供";
  const format = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  });
  const start = format.format(dates[0]);
  const end = format.format(dates[dates.length - 1]);
  return `${start === end ? start : `${start} — ${end}`}（北京时间）${dates.length < items.length ? "；部分时间未提供" : ""}`;
}

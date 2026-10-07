export const rankingPeriods = [
  ["latest", "最近交易日 · 单日"], ["previous", "上一交易日 · 单日"],
  ["3", "近3个交易日"], ["5", "近5个交易日"], ["10", "近10个交易日"],
  ["20", "近20个交易日"], ["60", "近60个交易日"],
] as const;
export type RankingPeriod = typeof rankingPeriods[number][0];
export type RankingMetric = "change" | "main_net" | "gross_in";
export interface RankingResult {
  metric: RankingMetric; period: RankingPeriod; status: "ready" | "partial" | "unavailable";
  data: {code:string;name:string;value:number;price:number|null;quoted_at:string}[];
  start_date:string|null;end_date:string|null;fetched_at:string;source:string;scope:string;
  unit:"percent"|"CNY";cached:boolean;reason:string;
}
export function parseRankingResult(value: unknown, metric: RankingMetric, period: RankingPeriod): RankingResult {
  const data = value as RankingResult;
  const validTime = (s: unknown) => typeof s === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(s) && Number.isFinite(Date.parse(s));
  const validDate = (s: unknown) => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) && Number.isFinite(Date.parse(s));
  if (!data || data.metric !== metric || data.period !== period || !Array.isArray(data.data)
    || !["ready","partial","unavailable"].includes(data.status)
    || data.unit !== (metric === "change" ? "percent" : "CNY") || !validTime(data.fetched_at)
    || typeof data.scope !== "string" || typeof data.reason !== "string" || typeof data.source !== "string") throw new Error("榜单口径校验失败");
  if (data.data.length && (!validDate(data.start_date) || !validDate(data.end_date) || data.start_date! > data.end_date!)) throw new Error("榜单区间校验失败");
  const seen = new Set<string>();
  for (const row of data.data) {
    if (!row || !/^\d{6}$/.test(row.code) || !row.name || seen.has(row.code) || !Number.isFinite(row.value)
      || (row.price !== null && (!Number.isFinite(row.price) || row.price <= 0)) || !validTime(row.quoted_at)) throw new Error("榜单行校验失败");
    const day = new Date(Date.parse(row.quoted_at)+8*3600000).toISOString().slice(0,10);
    if (day !== data.end_date) throw new Error("榜单日期不匹配");
    seen.add(row.code);
  }
  if (data.status === "unavailable" && data.data.length) throw new Error("不可用榜单不能夹带其他周期数据");
  return data;
}

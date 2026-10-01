export interface FiveDayDisplay {
  symbol: string; source: "tencent"; price_basis: "unverified_raw"; verification: "single_source";
  status: "partial" | "empty" | "failed"; fetched_at: string; days: string[];
  points: {timestamp: string; close: number}[]; incomplete_days: string[]; missing_days: string[];
  error_code: string | null;
}
const stamp = (s: unknown): s is string => typeof s === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(s) && Number.isFinite(Date.parse(s));
export function parseFiveDay(value: unknown, symbol: string): FiveDayDisplay {
  const fail = () => { throw new Error("五日分时数据格式不兼容"); };
  if (!value || typeof value !== "object") return fail();
  const v = value as FiveDayDisplay;
  if (v.symbol !== symbol || v.source !== "tencent" || v.price_basis !== "unverified_raw" ||
    v.verification !== "single_source" || !["partial", "empty", "failed"].includes(v.status) ||
    !stamp(v.fetched_at) || !Array.isArray(v.days) || v.days.length > 5 ||
    !v.days.every(d => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d)) ||
    v.days.some((d,i) => i > 0 && d <= v.days[i-1]) ||
    !Array.isArray(v.points) || !Array.isArray(v.incomplete_days) || !Array.isArray(v.missing_days) ||
    !v.incomplete_days.every(d => v.days.includes(d)) || !v.missing_days.every(d => typeof d === "string") ||
    !(v.error_code === null || typeof v.error_code === "string")) return fail();
  let previous = -Infinity;
  const seenDays = new Set<string>();
  for (const p of v.points) {
    if (!p || !stamp(p.timestamp) || !Number.isFinite(p.close) || p.close <= 0) return fail();
    const t = Date.parse(p.timestamp);
    const day = new Date(t + 8 * 3600000).toISOString().slice(0,10);
    if (t <= previous || t > Date.parse(v.fetched_at) || !v.days.includes(day)) return fail();
    previous = t; seenDays.add(day);
  }
  if ((v.status === "partial") !== (v.points.length > 0) || seenDays.size !== v.days.length) return fail();
  return v;
}

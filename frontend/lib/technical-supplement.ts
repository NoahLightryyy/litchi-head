/** Current research facts, separate from immutable historical AI opinions. */
export interface TechnicalSupplement {
  stock_code: string; status: "available" | "unavailable"; fetched_at: string;
  sources: string[]; diagnostics: Record<string, string>; methodology: string;
  adjusted: {
    status: "available" | "unavailable"; price_basis: "provider_qfq_current"; source: "tencent";
    fetched_at: string | null; data_start: string | null; data_end: string | null; bar_count: number;
    reason: string | null; methodology: string;
    indicators: { trade_date: string; ma: Record<string, number | null>; rsi14: number | null;
      macd: Record<string, number | null>; kdj: Record<string, number | null> }[];
  };
  volume: {
    status: "available" | "partial" | "unavailable"; data_date: string | null; sample_bars: number;
    volume_basis: "raw_shares"; latest_shares: number | null;
    previous5_mean_shares: number | null; previous20_mean_shares: number | null;
    ratio_to_previous5: number | null; ratio_to_previous20: number | null;
    comparison: "above_both" | "below_both" | "equal_both" | "mixed" | "insufficient";
    methodology: string;
  };
}
const record = (x: unknown): Record<string, unknown> => {
  if (!x || typeof x !== "object" || Array.isArray(x)) throw new Error("补充资料格式不完整");
  return x as Record<string, unknown>;
};
const validDate = (x: unknown): x is string => typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x)
  && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0, 10) === x;
const finite = (x: unknown) => typeof x === "number" && Number.isFinite(x);
const nonnegative = (x: unknown) => x === null || (finite(x) && (x as number) >= 0);
export function parseTechnicalSupplement(value: unknown, code: string): TechnicalSupplement {
  const x = record(value), a = record(x.adjusted), v = record(x.volume);
  const fail = () => { throw new Error("复权或成交量资料未通过校验，请稍后重试"); };
  if (x.stock_code !== code || !["available", "unavailable"].includes(String(x.status))
      || typeof x.fetched_at !== "string" || !Number.isFinite(Date.parse(x.fetched_at))
      || !Array.isArray(x.sources) || !x.sources.every(s => typeof s === "string")
      || typeof x.methodology !== "string") fail();
  if (a.price_basis !== "provider_qfq_current" || a.source !== "tencent"
      || !["available", "unavailable"].includes(String(a.status)) || !Array.isArray(a.indicators)
      || !Number.isSafeInteger(a.bar_count) || (a.bar_count as number) < 0
      || typeof a.methodology !== "string" || !(a.reason === null || typeof a.reason === "string")) fail();
  let previous = "";
  for (const item of a.indicators as unknown[]) {
    const p = record(item);
    if (!validDate(p.trade_date) || p.trade_date <= previous
        || !(p.rsi14 === null || finite(p.rsi14))) fail();
    previous = String(p.trade_date);
    for (const key of ["ma", "macd", "kdj"]) {
      if (!Object.values(record(p[key])).every(n => n === null || finite(n))) fail();
    }
  }
  if (a.status === "available" && (!validDate(a.data_start) || !validDate(a.data_end)
      || String(a.data_start) > String(a.data_end) || previous !== a.data_end
      || !(Number(a.bar_count) > 0) || typeof a.fetched_at !== "string"
      || !Number.isFinite(Date.parse(a.fetched_at)))) fail();
  if (v.volume_basis !== "raw_shares" || !["available", "partial", "unavailable"].includes(String(v.status))
      || !["above_both", "below_both", "equal_both", "mixed", "insufficient"].includes(String(v.comparison))
      || !Number.isSafeInteger(v.sample_bars) || Number(v.sample_bars) < 0 || typeof v.methodology !== "string") fail();
  for (const key of ["latest_shares", "previous5_mean_shares", "previous20_mean_shares", "ratio_to_previous5", "ratio_to_previous20"]) {
    if (!nonnegative(v[key])) fail();
  }
  if (v.status !== "unavailable" && (!validDate(v.data_date) || !Number.isSafeInteger(v.latest_shares))) fail();
  if (v.status === "available" && (Number(v.sample_bars) < 21
      || v.ratio_to_previous5 === null || v.ratio_to_previous20 === null)) fail();
  if (a.status === "available" && v.status !== "unavailable" && a.data_end !== v.data_date) fail();
  if (!Object.values(record(x.diagnostics)).every(item => typeof item === "string")) fail();
  return x as unknown as TechnicalSupplement;
}
export function volumeComparisonText(v: TechnicalSupplement["volume"]): string {
  const text = {
    above_both: "成交量高于前5日和前20日平均水平，但仅凭放量不能确认上涨或反转。",
    below_both: "成交量低于前5日和前20日平均水平：数据已有，但放量条件还没出现。",
    equal_both: "成交量与两个窗口的均量持平，暂未观察到量能增加。",
    mixed: "与两个窗口相比表现不一致，还不能笼统地说持续放量。",
    insufficient: "历史长度或有效成交量不足，暂不能完成两个窗口的比较。",
  };
  return text[v.comparison];
}

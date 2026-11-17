import type { CandleInput } from "./chart-indicators.ts";
import type { EtfDetail } from "./etf-display.ts";

export interface EtfKline {
  schema_version: 1;
  identity: EtfDetail["identity"];
  status: "ready" | "empty" | "unavailable";
  source: "tencent" | "sina" | null;
  price_basis: "raw";
  price_unit: "CNY";
  price_tick: 0.001;
  volume_unit: "fund_units";
  verification: "single_source";
  fetched_at: string;
  requested_start: string;
  requested_end: string;
  data_start: string | null;
  data_end: string | null;
  bars: CandleInput[];
  diagnostics: { source: "tencent" | "sina"; status: "success" | "empty" | "failed"; error_code: string | null }[];
  limitations: string[];
}
const date = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
const stamp = (value: unknown): value is string => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const price = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value > 0 && Math.abs(value * 1000 - Math.round(value * 1000)) < 1e-7;

export function parseEtfKline(value: unknown, code: string): EtfKline {
  const data = value as EtfKline;
  const fail = (): never => { throw new Error("ETF K线响应无法确认，请重试。"); };
  const identity = data?.identity;
  if (!data || data.schema_version !== 1 || !/^\d{6}$/.test(code) || !identity
    || identity.code !== code || identity.instrument_type !== "etf" || !["SH", "SZ"].includes(identity.exchange)
    || identity.symbol !== identity.exchange.toLowerCase() + code || typeof identity.name !== "string" || !identity.name.trim()
    || !["ready", "empty", "unavailable"].includes(data.status) || !["tencent", "sina", null].includes(data.source)
    || data.price_basis !== "raw" || data.price_unit !== "CNY" || data.price_tick !== 0.001
    || data.volume_unit !== "fund_units" || data.verification !== "single_source"
    || !stamp(data.fetched_at) || !date(data.requested_start) || !date(data.requested_end)
    || data.requested_start > data.requested_end
    || data.requested_end > new Date(Date.parse(data.fetched_at) + 8 * 3600_000).toISOString().slice(0, 10)
    || !Array.isArray(data.bars) || data.bars.length > 730 || !Array.isArray(data.diagnostics)
    || !Array.isArray(data.limitations) || !data.limitations.every(item => typeof item === "string")
    || (data.bars.length > 0) !== (data.status === "ready") || (data.bars.length > 0) !== (data.source !== null)) return fail();
  let previous = "";
  for (const bar of data.bars) {
    if (!bar || !date(bar.date) || bar.date <= previous || bar.date < data.requested_start || bar.date > data.requested_end
      || ![bar.open, bar.high, bar.low, bar.close].every(price)
      || bar.high < Math.max(bar.open, bar.close, bar.low) || bar.low > Math.min(bar.open, bar.close)
      || !Number.isSafeInteger(bar.volume) || bar.volume < 0) return fail();
    previous = bar.date;
  }
  if (data.data_start !== (data.bars[0]?.date ?? null) || data.data_end !== (data.bars.at(-1)?.date ?? null)) return fail();
  for (const diagnostic of data.diagnostics) {
    if (!diagnostic || !["tencent", "sina"].includes(diagnostic.source)
      || !["success", "empty", "failed"].includes(diagnostic.status)
      || ![null, "request_timeout", "upstream_request_failed", "invalid_upstream_payload"].includes(diagnostic.error_code)) return fail();
  }
  return data;
}

/** Source outages preserve the previous successful chart for this ETF. Empty is a separate valid result. */
export function requireEtfKline(value: unknown, code: string): EtfKline {
  const data = parseEtfKline(value, code);
  if (data.status === "unavailable") throw new Error("ETF 历史行情暂不可用，请重试。");
  return data;
}

/** Snapshot phase comes from fetch time in Beijing, never the viewer's current clock. */
export function etfKlineSnapshotNote(data: EtfKline): string {
  if (!data.data_end) return "";
  const fetchedInBeijing = new Date(Date.parse(data.fetched_at) + 8 * 3600_000);
  if (data.data_end !== fetchedInBeijing.toISOString().slice(0, 10)) {
    return `当前来源日线截至 ${data.data_end}；可点“刷新K线”获取更新。`;
  }
  if (fetchedInBeijing.getUTCHours() < 15) {
    return `${data.data_end} 当日日线（采集时尚未收盘）。收盘价栏为当时最新价，价格和成交量仍会变化。`;
  }
  return `已含 ${data.data_end} 当日日线（收盘后采集），以上游返回为准。`;
}

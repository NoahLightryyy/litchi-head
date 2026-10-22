export type EtfDetail = {
  schema_version: 1;
  identity: {code: string; symbol: string; exchange: "SH" | "SZ"; name: string; instrument_type: "etf"};
  quote: null | {price: number; previous_close: number; change: number; change_pct: number; open: number | null; high: number | null; low: number | null; quoted_at: string; source_name: string};
  status: "ready" | "partial";
  source: "sina";
  source_url: string;
  catalog_fetched_at: string;
  fetched_at: string;
  limitations: string[];
};
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("ETF响应格式无效");
  return value as Record<string, unknown>;
}
function stamp(value: unknown): value is string {
  return typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}
export function parseEtfDetail(raw: unknown, code: string): EtfDetail {
  const data = object(raw), identity = object(data.identity);
  if (data.schema_version !== 1 || data.source !== "sina" || !/^\d{6}$/.test(code)
    || identity.code !== code || identity.instrument_type !== "etf"
    || !["SH", "SZ"].includes(String(identity.exchange))
    || identity.symbol !== String(identity.exchange).toLowerCase() + code
    || typeof identity.name !== "string" || !identity.name.trim()) throw new Error("ETF身份校验失败");
  if (!["ready", "partial"].includes(String(data.status)) || !stamp(data.catalog_fetched_at) || !stamp(data.fetched_at)
    || !Array.isArray(data.limitations) || !data.limitations.every(x => typeof x === "string")
    || data.source_url !== "https://vip.stock.finance.sina.com.cn/fund_center/index.html#jjhqetf") throw new Error("ETF来源校验失败");
  if (data.quote !== null) {
    const q = object(data.quote);
    if (!positive(q.price) || !positive(q.previous_close) || !stamp(q.quoted_at)
      || Date.parse(q.quoted_at) > Date.parse(data.fetched_at) + 5000
      || typeof q.source_name !== "string" || !q.source_name.trim()
      || ![q.change,q.change_pct].every(x => typeof x === "number" && Number.isFinite(x))
      || ![q.open,q.high,q.low].every(x => x === null || positive(x))) throw new Error("ETF行情校验失败");
    if (Math.abs(Number(q.change) - (q.price-q.previous_close)) > 0.000001
      || Math.abs(Number(q.change_pct) - (q.price/q.previous_close-1)*100) > 0.000001
      || q.high !== null && q.low !== null && (Number(q.low) > q.price || Number(q.high) < q.price)) throw new Error("ETF行情数值不一致");
  }
  if ((data.status === "ready") !== (data.quote !== null)) throw new Error("ETF状态与行情不一致");
  return data as EtfDetail;
}

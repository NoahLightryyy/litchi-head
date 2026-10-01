export const FUNDAMENTAL_ROWS = [
  {label: "盈利 · 营业收入", key: "revenue"},
  {label: "盈利 · 毛利率", key: "gross_margin"},
  {label: "盈利 · 归母净利润", key: "parent_profit"},
  {label: "盈利 · 期末权益回报率（未年化）", key: "return_on_ending_equity"},
  {label: "成长 · 营业收入同比", key: "revenue_growth"},
  {label: "成长 · 归母净利润同比", key: "parent_profit_growth"},
  {label: "现金流 · 经营现金流净额", key: "operating_cash_flow"},
  {label: "风险 · 资产负债率", key: "debt_ratio"},
  {label: "估值分母 · 营业收入TTM", key: "revenue_ttm"},
  {label: "估值分母 · 归母净利润TTM", key: "parent_profit_ttm"},
  {label: "估值 · PE", key: "pe"},
  {label: "估值 · PB", key: "pb"},
  {label: "估值 · PS", key: "ps"},
] as const;
export type MetricKey = typeof FUNDAMENTAL_ROWS[number]["key"];
export type Metric = {value: number | null; unit: string; basis: string; reason: string | null};
export type Statement = {kind: "lrb" | "fzb" | "llb"; report_date: string; published_at: string | null; source_url: string; currency: "CNY"; scope: "合并期末"; amounts: Record<string, number | null>};
export type Research = {
  schema_version: 1; stock_code: string; status: "available" | "partial" | "stale" | "unavailable";
  report_date: string | null; fetched_at: string | null; source: "sina_consolidated_statements";
  verification: "single_source"; statements: Statement[]; metrics: Partial<Record<MetricKey, Metric>>;
  warnings: string[]; retryable: boolean;
};
function validDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
export function checkedResearch(value: unknown, code: string): Research {
  const data = value as Research;
  if (!data || data.schema_version !== 1 || data.stock_code !== code ||
      !["available", "partial", "stale", "unavailable"].includes(data.status) ||
      data.source !== "sina_consolidated_statements" || data.verification !== "single_source" ||
      !Array.isArray(data.statements) || !Array.isArray(data.warnings) ||
      data.warnings.some(s => typeof s !== "string") || typeof data.retryable !== "boolean" ||
      !data.metrics || typeof data.metrics !== "object") throw new Error("研究接口身份或版本不兼容");
  if (data.status !== "unavailable" && (!validDate(data.report_date) ||
      typeof data.fetched_at !== "string" || !Number.isFinite(Date.parse(data.fetched_at))))
    throw new Error("研究时间缺失");
  for (const statement of data.statements) {
    if (!statement || !validDate(statement.report_date) ||
        (statement.published_at !== null && !validDate(statement.published_at)) ||
        !["lrb", "fzb", "llb"].includes(statement.kind) || statement.scope !== "合并期末" || statement.currency !== "CNY" ||
        typeof statement.source_url !== "string" || !statement.source_url.startsWith("https://quotes.sina.cn/"))
      throw new Error("报表口径或来源不兼容");
  }
  for (const {key} of FUNDAMENTAL_ROWS) {
    const metric = data.metrics[key];
    if (data.status === "unavailable" && !metric) continue;
    if (!metric || (metric.value !== null && (typeof metric.value !== "number" || !Number.isFinite(metric.value))) ||
        typeof metric.unit !== "string" || typeof metric.basis !== "string" ||
        (metric.value === null && typeof metric.reason !== "string")) throw new Error("研究指标格式无效");
  }
  return data;
}
export function displayMetric(metric: Metric | undefined): string {
  if (!metric || metric.value === null) return "—";
  return metric.unit === "元" ? `${(metric.value / 1e8).toFixed(2)}亿` : `${metric.value.toFixed(2)}${metric.unit}`;
}
export function publicationDate(data: Research | undefined): string {
  const rows = data?.statements.filter(s => s.report_date === data.report_date) ?? [];
  if (!rows.length) return "—";
  const dates = [...new Set(rows.map(s => s.published_at ?? "未提供"))];
  return dates.join(" / ");
}

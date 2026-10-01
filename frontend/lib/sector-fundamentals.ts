import type { FinancialMetrics, ValuationMetrics } from "./types/stock.ts";

export const FUNDAMENTAL_ROWS = [
  {label: "盈利 · ROE", key: "roe", unit: "%"},
  {label: "盈利 · 毛利率", key: "gross_margin", unit: "%"},
  {label: "成长 · 营收增长", key: "revenue_growth", unit: "%"},
  {label: "成长 · 净利润增长", key: "net_profit_growth", unit: "%"},
  {label: "现金流 · 每股经营现金流", key: "operating_cf_per_share", unit: "元"},
  {label: "财务风险 · 资产负债率", key: "debt_ratio", unit: "%"},
] as const;

function validDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
export function latestFinancial(value: unknown, code: string): FinancialMetrics | null {
  if (!Array.isArray(value)) throw new Error("财务格式不兼容");
  for (const row of value) {
    if (!row || row.stock_code !== code || !validDate(row.report_date) ||
        FUNDAMENTAL_ROWS.some(({key}) => typeof row[key] !== "number" || !Number.isFinite(row[key]))) {
      throw new Error("财务身份、报告期或指标无效");
    }
  }
  return [...value].sort((a, b) => b.report_date.localeCompare(a.report_date))[0] ?? null;
}
export function checkedValuation(value: ValuationMetrics | null, code: string): ValuationMetrics | null {
  if (value === null) return null;
  if (!value || value.stock_code !== code || !validDate(value.report_date) ||
      [value.pe, value.pb, value.ps].some(n => typeof n !== "number" || !Number.isFinite(n))) {
    throw new Error("估值身份或指标无效");
  }
  return value;
}
export function displayMetric(value: unknown, unit = ""): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value === 0 ? "0（待核验）" : `${value.toFixed(2)}${unit}`;
}

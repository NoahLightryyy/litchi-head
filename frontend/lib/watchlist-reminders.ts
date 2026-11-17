import { api } from "./api/client.ts";
import { readEntryPlan, type EntryPlanResult, type HorizonEntryPlan } from "./entry-plan.ts";
import { debateInstrumentMatches } from "./debate-instrument.ts";
import { readSearchCompanies, type ComparisonCompany } from "./screening.ts";
import type { ResearchEntry } from "./research-list.ts";
import type { StockQuote } from "./types/stock.ts";
import type { DebateHistoryItem } from "./types/debate.ts";

/** Price movement is an observation, never a buy signal or a portfolio return. */
export function checkedWatchQuote(value: unknown, code: string): StockQuote | null {
  if (value === null) return null;
  if (!value || typeof value !== "object") throw new Error("报价暂时无法读取");
  const q = value as StockQuote;
  if (q.code !== code || typeof q.name !== "string" || !q.name.trim()
    || !Number.isFinite(q.price) || q.price <= 0 || !Number.isFinite(q.change_pct)
    || !(q.fetched_at === null || (typeof q.fetched_at === "string" && Number.isFinite(Date.parse(q.fetched_at))))) {
    throw new Error("报价和这只股票没有对上，请稍后刷新");
  }
  return q;
}
export function priceReminder(quote: StockQuote): { title: string; detail: string } {
  if (quote.change_pct > 0) return { title: `比前一交易日收盘上涨 ${quote.change_pct.toFixed(2)}%`, detail: "涨了不等于现在买就合适，先看看下面的买入提醒。" };
  if (quote.change_pct < 0) return { title: `比前一交易日收盘下跌 ${Math.abs(quote.change_pct).toFixed(2)}%`, detail: "跌了不等于便宜。先看看公司出了什么变化，再考虑是否加钱。" };
  return { title: "与前一交易日收盘基本持平", detail: "只看涨跌还看不出机会，可以继续查看公司的消息和分析。" };
}
export function planReminder(plan: HorizonEntryPlan): { title: string; detail: string } {
  if (plan.status === "consider") return { title: "出现过值得留意的买入信号", detail: "当时的条件已满足，先确认现在是否还成立，再决定要不要买。" };
  if (plan.status === "waiting") return { title: "买入条件还没凑齐", detail: "先别急着出手，等下面列出的变化出现后再看。" };
  return { title: "还看不准，先别急", detail: "当时的信息还不够，暂时不能判断是不是买入机会。" };
}
export function addWatchEntry(entries: ResearchEntry[], company: ComparisonCompany, now: string): ResearchEntry[] {
  // Selecting an already saved company must never erase its personal note.
  if (entries.some(entry => entry.code === company.code)) return entries;
  return [...entries, { ...company, note: "", updatedAt: now }];
}
export async function searchWatchStocks(query: string, signal: AbortSignal): Promise<ComparisonCompany[]> {
  // Use the stock directory: a six-digit quote alone cannot distinguish an ETF from a stock.
  return readSearchCompanies(await api.get<unknown>("/stocks/search", { q: query }, { signal }));
}
export interface WatchResearch { plan: EntryPlanResult | null; latestStatus: DebateHistoryItem["status"] | "none" }
export function latestWatchResearch(value: unknown, code: string): { latestStatus: WatchResearch["latestStatus"]; completed: DebateHistoryItem | null } {
  if (!Array.isArray(value)) throw new Error("上次分析暂时无法读取");
  const records = value.filter(item => debateInstrumentMatches(item, code, "stock"));
  for (const record of records) {
    if (typeof record.session_id !== "string" || !record.session_id.trim()
      || !["queued", "running", "completed", "failed"].includes(record.status)
      || typeof record.created_at !== "string" || !Number.isFinite(Date.parse(record.created_at))) throw new Error("分析记录不完整，请稍后刷新");
  }
  records.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return { latestStatus: records[0]?.status ?? "none", completed: records.find(item => item.status === "completed") ?? null };
}
/** All calls are GETs. Opening a watchlist cannot trigger paid analysis. */
export async function readWatchResearch(code: string, signal: AbortSignal): Promise<WatchResearch> {
  const history = latestWatchResearch(await api.get<unknown>("/debate/history", { stock_code: code, instrument_type: "stock", offset: "0" }, { signal }), code);
  const plan = history.completed ? await readEntryPlan({ sessionId: history.completed.session_id, stockCode: code, instrumentType: "stock" }, signal) : null;
  return { latestStatus: history.latestStatus, plan };
}

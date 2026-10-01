import { api } from "./client";
import type { StockQuote, KLineData, CapitalFlow, StockSearchResult, TechnicalIndicators, FinancialMetrics, ValuationMetrics, DynamicIndicators, IntradayBattlefield } from "@/lib/types/stock";
import { parseIntradayBattlefield } from "@/lib/intraday-contract";

/** 搜索股票/板块 */
export async function searchStocks(query: string): Promise<StockSearchResult[]> {
  return api.get("/stocks/search", { q: query });
}

/** 个股实时行情 */
export async function fetchQuote(code: string): Promise<StockQuote> {
  return api.get(`/stocks/${code}/quote`);
}

/** K 线数据 */
export async function fetchKline(
  code: string,
  period: string = "daily",
  start?: string,
  end?: string,
  signal?: AbortSignal
): Promise<KLineData[]> {
  const params: Record<string, string> = { period };
  if (start) params.start = start;
  if (end) params.end = end;
  return api.get(`/stocks/${code}/kline`, params, {signal});
}

/** 资金流向 */
export async function fetchCapitalFlow(code: string): Promise<CapitalFlow[]> {
  return api.get(`/stocks/${code}/capital-flow`);
}

/** 技术指标（MA/RSI/MACD/布林带） */
export async function fetchTechnicalIndicators(
  code: string,
  period: string = "daily"
): Promise<TechnicalIndicators | null> {
  return api.get(`/stocks/${code}/technical-indicators`, { period });
}

/** 个股财务指标（ROE/毛利率/负债率等） */
export async function fetchFinancials(code: string, signal?: AbortSignal): Promise<FinancialMetrics[]> {
  return api.get(`/stocks/${code}/financials`, undefined, { signal });
}

/** 个股估值比率（PE/PB/PS） */
export async function fetchValuation(code: string, signal?: AbortSignal): Promise<ValuationMetrics | null> {
  return api.get(`/stocks/${code}/valuation`, undefined, { signal });
}

/** 个股动态关键指标（按行业注册表） */
export async function fetchIndicators(code: string): Promise<DynamicIndicators> {
  return api.get(`/stocks/${code}/indicators`);
}

/** 分时曲线、战况与数据源诊断。 */
export async function fetchIntradayBattlefield(
  code: string,
): Promise<IntradayBattlefield> {
  const response: unknown = await api.post("/v1/evidence/intraday/battlefield", {
    symbol: code,
  });
  return parseIntradayBattlefield(response);
}

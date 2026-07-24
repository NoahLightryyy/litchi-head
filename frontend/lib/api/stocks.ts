import { api } from "./client";
import type { StockQuote, KLineData, NewsItem, CapitalFlow, StockSearchResult, TechnicalIndicators, FinancialMetrics, ValuationMetrics, DynamicIndicators } from "@/lib/types/stock";

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
  end?: string
): Promise<KLineData[]> {
  const params: Record<string, string> = { period };
  if (start) params.start = start;
  if (end) params.end = end;
  return api.get(`/stocks/${code}/kline`, params);
}

/** 个股新闻 */
export async function fetchNews(code: string): Promise<NewsItem[]> {
  return api.get(`/stocks/${code}/news`);
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
export async function fetchFinancials(code: string): Promise<FinancialMetrics[]> {
  return api.get(`/stocks/${code}/financials`);
}

/** 个股估值比率（PE/PB/PS） */
export async function fetchValuation(code: string): Promise<ValuationMetrics | null> {
  return api.get(`/stocks/${code}/valuation`);
}

/** 个股动态关键指标（按行业注册表） */
export async function fetchIndicators(code: string): Promise<DynamicIndicators> {
  return api.get(`/stocks/${code}/indicators`);
}

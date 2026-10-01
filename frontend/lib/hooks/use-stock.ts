"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchQuote, fetchKline, fetchCapitalFlow, fetchTechnicalIndicators, fetchFinancials, fetchValuation, fetchIndicators, fetchIntradayBattlefield, searchStocks } from "@/lib/api/stocks";
import { useDebounce } from "./use-debounce";

/* ── 搜索（300ms 防抖） ── */
export function useStockSearch(query: string) {
  const debouncedQuery = useDebounce(query, 300);
  return useQuery({
    queryKey: ["stocks", "search", debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  });
}

/* ── 个股行情 ── */
export function useStockQuote(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "quote"],
    queryFn: () => fetchQuote(code),
    refetchInterval: 30_000,
    staleTime: 15_000,
    enabled: !!code,
  });
}

/* ── K 线数据 ── */
export function useKline(code: string, period: string = "daily") {
  return useQuery({
    queryKey: ["stocks", code, "kline", period],
    queryFn: ({signal}) => fetchKline(code, period, undefined, undefined, AbortSignal.any([signal, AbortSignal.timeout(15000)])),
    retry: false,
    staleTime: 60_000,
    enabled: !!code,
  });
}

/* ── 技术指标 ── */
export function useTechnicalIndicators(code: string, period: string = "daily") {
  return useQuery({
    queryKey: ["stocks", code, "technical-indicators", period],
    queryFn: () => fetchTechnicalIndicators(code, period),
    staleTime: 120_000,
    enabled: !!code,
  });
}

/* ── 资金流向 ── */
export function useCapitalFlow(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "capital-flow"],
    queryFn: () => fetchCapitalFlow(code),
    staleTime: 60_000,
    enabled: !!code,
  });
}

/* ── 财务指标 ── */
export function useFinancials(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "financials"],
    queryFn: () => fetchFinancials(code),
    staleTime: 300_000,
    enabled: !!code,
  });
}

/* ── 估值比率 ── */
export function useValuation(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "valuation"],
    queryFn: () => fetchValuation(code),
    staleTime: 300_000,
    enabled: !!code,
  });
}

/* ── 动态关键指标（行业感知） ── */
export function useIndicators(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "indicators"],
    queryFn: () => fetchIndicators(code),
    staleTime: 300_000,
    enabled: !!code,
  });
}

/** 分时行情每 30 秒刷新，且不会因单一来源而阻断数据展示。 */
export function useIntradayBattlefield(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "intraday-battlefield"],
    queryFn: () => fetchIntradayBattlefield(code),
    refetchInterval: 30_000,
    staleTime: 15_000,
    enabled: !!code,
  });
}

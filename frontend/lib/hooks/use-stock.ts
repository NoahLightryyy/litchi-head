"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchQuote, fetchKline, fetchNews, fetchCapitalFlow, fetchTechnicalIndicators, searchStocks } from "@/lib/api/stocks";
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
    queryFn: () => fetchKline(code, period),
    staleTime: 60_000,
    enabled: !!code,
  });
}

/* ── 个股新闻 ── */
export function useStockNews(code: string) {
  return useQuery({
    queryKey: ["stocks", code, "news"],
    queryFn: () => fetchNews(code),
    staleTime: 120_000,
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

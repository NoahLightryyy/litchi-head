"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMarketIndices, fetchSectors, fetchMacroBrief, fetchSectorDetail, fetchHotNews } from "@/lib/api/market";

const SECTOR_REQUEST_TIMEOUT_MS = 18_000;

/* ── 三大指数 ── */
export function useMarketIndices() {
  return useQuery({
    queryKey: ["market", "indices"],
    queryFn: fetchMarketIndices,
    refetchInterval: 30_000,      // 30 秒刷新
    staleTime: 15_000,
  });
}

/* ── 指数摘要 ── */
export function useMacroBrief() {
  return useQuery({
    queryKey: ["market", "brief"],
    queryFn: fetchMacroBrief,
    refetchInterval: 300_000,     // 5 分钟刷新
    staleTime: 120_000,
  });
}

/* ── 板块排行 ── */
export function useSectors(sort: string = "fund_flow", source: "eastmoney" | "sina" = "eastmoney") {
  return useQuery({
    queryKey: ["market", "sectors", source, sort],
    queryFn: ({ signal }) => fetchSectors(
      sort,
      AbortSignal.any([signal, AbortSignal.timeout(SECTOR_REQUEST_TIMEOUT_MS)]),
      source,
    ),
    retry: false,
    refetchInterval: 60_000,      // 1 分钟刷新
    staleTime: 30_000,
  });
}

/* ── 板块详情 + 产业链 ── */
export function useSectorDetail(sectorId: string) {
  return useQuery({
    queryKey: ["market", "sector", sectorId],
    queryFn: () => fetchSectorDetail(sectorId),
    retry: false,
    staleTime: 60_000,
    enabled: !!sectorId,
  });
}

/* ── 热点快讯 ── */
export function useHotNews() {
  return useQuery({
    queryKey: ["market", "hot-news"],
    queryFn: fetchHotNews,
    refetchInterval: 120_000,     // 2 分钟刷新
    staleTime: 60_000,
  });
}

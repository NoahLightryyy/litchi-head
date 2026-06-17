"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchMarketIndices, fetchSectors, fetchMacroBrief, fetchSectorDetail } from "@/lib/api/market";

/* ── 三大指数 ── */
export function useMarketIndices() {
  return useQuery({
    queryKey: ["market", "indices"],
    queryFn: fetchMarketIndices,
    refetchInterval: 30_000,      // 30 秒刷新
    staleTime: 15_000,
  });
}

/* ── AI 宏观简报 ── */
export function useMacroBrief() {
  return useQuery({
    queryKey: ["market", "brief"],
    queryFn: fetchMacroBrief,
    refetchInterval: 300_000,     // 5 分钟刷新
    staleTime: 120_000,
  });
}

/* ── 板块排行 ── */
export function useSectors(sort: string = "fund_flow") {
  return useQuery({
    queryKey: ["market", "sectors", sort],
    queryFn: () => fetchSectors(sort),
    refetchInterval: 60_000,      // 1 分钟刷新
    staleTime: 30_000,
  });
}

/* ── 板块详情 + 产业链 ── */
export function useSectorDetail(sectorId: string) {
  return useQuery({
    queryKey: ["market", "sector", sectorId],
    queryFn: () => fetchSectorDetail(sectorId),
    staleTime: 60_000,
    enabled: !!sectorId,
  });
}

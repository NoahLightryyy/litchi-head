import { api } from "./client";
import type { MarketIndex, SectorItem, MacroBrief, SectorDetail, ChainAnalysis, HotNewsItem } from "@/lib/types/market";

/** 三大指数行情 */
export async function fetchMarketIndices(): Promise<MarketIndex[]> {
  return api.get("/market/indices");
}

/** AI 宏观简报 */
export async function fetchMacroBrief(): Promise<MacroBrief> {
  return api.get("/market/brief");
}

/** 板块排行 */
export async function fetchSectors(sort: string = "fund_flow"): Promise<SectorItem[]> {
  return api.get("/market/sectors", { sort });
}

/** 板块详情 + 产业链分析 */
export async function fetchSectorDetail(sectorId: string): Promise<SectorDetail> {
  return api.get(`/market/sector/${sectorId}`);
}

/** 热点快讯 */
export async function fetchHotNews(): Promise<HotNewsItem[]> {
  return api.get("/market/hot-news");
}

import { api } from "./client";
import type { MarketEnvelope, MarketIndex, SectorItem, MacroBrief, SectorDetail, HotNewsItem } from "@/lib/types/market";
import {
  parseHotNewsEnvelope,
  parseIndicesEnvelope,
  parseMacroBriefEnvelope,
  parseSectorsEnvelope,
} from "@/lib/market-contract";

/** 三大指数行情 */
export async function fetchMarketIndices(): Promise<MarketEnvelope<MarketIndex[]>> {
  return parseIndicesEnvelope(await api.getRaw("/market/indices"));
}

/** AI 宏观简报 */
export async function fetchMacroBrief(): Promise<MarketEnvelope<MacroBrief | null>> {
  return parseMacroBriefEnvelope(await api.getRaw("/market/brief"));
}

/** 板块排行 */
export async function fetchSectors(sort: string = "fund_flow"): Promise<MarketEnvelope<SectorItem[]>> {
  return parseSectorsEnvelope(await api.getRaw("/market/sectors", { sort }));
}

/** 板块详情 + 产业链分析 */
export async function fetchSectorDetail(sectorId: string): Promise<SectorDetail> {
  return api.get(`/market/sector/${sectorId}`);
}

/** 热点快讯 */
export async function fetchHotNews(): Promise<MarketEnvelope<HotNewsItem[]>> {
  return parseHotNewsEnvelope(await api.getRaw("/market/hot-news"));
}

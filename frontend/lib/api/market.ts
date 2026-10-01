import { loadSectorFeed } from "@/lib/sector-feed";
import { api } from "./client";
import type { MarketEnvelope, MarketIndex, SectorItem, MacroBrief, SectorDetail, HotNewsItem } from "@/lib/types/market";
import {
  parseHotNewsEnvelope,
  parseIndicesEnvelope,
  parseMacroBriefEnvelope,
  parseSectorDetailEnvelope,
  parseSectorsEnvelope,
  parseSinaMembersEnvelope,
} from "@/lib/market-contract";

/** 三大指数行情 */
export async function fetchMarketIndices(): Promise<MarketEnvelope<MarketIndex[]>> {
  return parseIndicesEnvelope(await api.getRaw("/market/indices"));
}

/** 指数摘要 */
export async function fetchMacroBrief(): Promise<MarketEnvelope<MacroBrief | null>> {
  return parseMacroBriefEnvelope(await api.getRaw("/market/brief"));
}

/** 板块排行 */
export async function fetchSectors(
  sort: string = "fund_flow",
  signal?: AbortSignal,
): Promise<MarketEnvelope<SectorItem[]>> {
  return loadSectorFeed(
    async () => parseSectorsEnvelope(await api.getRaw("/market/sectors", { sort }, { signal })),
    async () => parseSectorsEnvelope(await api.getRaw("/market/sectors", { sort, source: "sina" }, { signal })),
    signal,
  );
}

/** 板块详情 + 产业链分析 */
export async function fetchSectorDetail(sectorId: string): Promise<MarketEnvelope<SectorDetail>> {
  return parseSectorDetailEnvelope(await api.getRaw(`/market/sector/${sectorId}`));
}

/** 热点快讯 */
export async function fetchHotNews(): Promise<MarketEnvelope<HotNewsItem[]>> {
  return parseHotNewsEnvelope(await api.getRaw("/market/hot-news"));
}

export async function fetchSinaSectors(signal?: AbortSignal) {
  return parseSectorsEnvelope(await api.getRaw("/market/sectors", { source: "sina", sort: "net_flow" }, { signal }));
}

export async function fetchSinaMembers(code: string, page: number, signal?: AbortSignal) {
  return parseSinaMembersEnvelope(await api.getRaw(`/market/sina/sector/${encodeURIComponent(code)}/stocks`, { page: String(page) }, { signal }), code, page);
}

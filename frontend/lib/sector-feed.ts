import type { MarketEnvelope, SectorItem } from "./types/market.ts";

/** Keep each funding metric bound to its requested supplier and taxonomy. */
export async function loadSectorFeed(
  source: SectorItem["source"],
  read: () => Promise<MarketEnvelope<SectorItem[]>>,
): Promise<MarketEnvelope<SectorItem[]>> {
  const result = await read();
  if (result.data.some((item) => item.source !== source)) {
    throw new Error("板块响应来源与请求不一致");
  }
  return result;
}

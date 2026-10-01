import type { MarketEnvelope, SectorItem } from "./types/market.ts";

/** A fallback changes board taxonomy: only explicit upstream failure permits it. */
export async function loadSectorFeed(
  primary: () => Promise<MarketEnvelope<SectorItem[]>>,
  alternative: () => Promise<MarketEnvelope<SectorItem[]>>,
  signal?: AbortSignal,
): Promise<MarketEnvelope<SectorItem[]>> {
  try {
    return await primary();
  } catch (error) {
    if (signal?.aborted || typeof error !== "object" || error === null ||
      !("status" in error) || error.status !== 503 ||
      !("code" in error) || error.code !== "MARKET_SECTORS_FAILED") throw error;
    const result = await alternative();
    return { ...result, meta: { ...result.meta,
      failed_sources: [...new Set([...result.meta.failed_sources, "eastmoney"])],
    } };
  }
}

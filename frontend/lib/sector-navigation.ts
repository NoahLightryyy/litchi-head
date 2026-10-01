import type { SectorItem } from "./types/market.ts";

export function sectorHref(sector: Pick<SectorItem, "source" | "id">): string {
  return sector.source === "sina" ? `/sector/sina/${encodeURIComponent(sector.id.slice(5))}` : `/sector/${encodeURIComponent(sector.id)}`;
}

export function compareSinaSector(sector: SectorItem, items: SectorItem[]) {
  const peers = items.filter(s => s.source === "sina" && s.category === sector.category);
  return {
    total: peers.length,
    changeRank: 1 + peers.filter(s => s.change_pct > sector.change_pct).length,
    flowRank: sector.net_flow == null ? null : 1 + peers.filter(s => s.net_flow != null && s.net_flow > sector.net_flow!).length,
  };
}

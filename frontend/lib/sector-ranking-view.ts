import type { SectorItem } from "@/lib/types/market";

export const DEFAULT_VISIBLE_SECTOR_COUNT = 10;

export function visibleSectorItems(
  sectors: SectorItem[],
  visibleCount: number = DEFAULT_VISIBLE_SECTOR_COUNT,
): SectorItem[] {
  return sectors.slice(0, Math.max(DEFAULT_VISIBLE_SECTOR_COUNT, Math.floor(visibleCount)));
}

export function hiddenSectorCount(sectors: SectorItem[], visibleCount: number): number {
  return Math.max(0, sectors.length - visibleSectorItems(sectors, visibleCount).length);
}

/** All rows share a scale; the baseline is zero and each direction has half the track. */
export function sectorChangeScale(sectors: SectorItem[]): number {
  return Math.max(1, ...sectors.map((item) => Math.abs(item.change_pct)));
}

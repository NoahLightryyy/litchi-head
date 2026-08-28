import type { SectorItem } from "@/lib/types/market";

export const DEFAULT_VISIBLE_SECTOR_COUNT = 10;

export function visibleSectorItems(
  sectors: SectorItem[],
  expanded: boolean,
): SectorItem[] {
  return expanded ? sectors : sectors.slice(0, DEFAULT_VISIBLE_SECTOR_COUNT);
}

export function hiddenSectorCount(sectors: SectorItem[], expanded: boolean): number {
  return expanded ? 0 : Math.max(0, sectors.length - DEFAULT_VISIBLE_SECTOR_COUNT);
}

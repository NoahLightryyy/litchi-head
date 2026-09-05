import type { SectorItem } from "@/lib/types/market";

export const SECTOR_PAGE_SIZE = 10;

/** Filter the entire received ranking before slicing; keep upstream ranks and order. */
export function sectorPage(sectors: SectorItem[], query: string, requestedPage: number) {
  const term = query.trim().toLocaleLowerCase();
  const matches = term ? sectors.filter((item) =>
    item.name.toLocaleLowerCase().includes(term) || item.id.toLocaleLowerCase().includes(term),
  ) : sectors;
  const pageCount = Math.max(1, Math.ceil(matches.length / SECTOR_PAGE_SIZE));
  const page = Math.min(pageCount, Math.max(1, Number.isFinite(requestedPage) ? Math.floor(requestedPage) : 1));
  const offset = (page - 1) * SECTOR_PAGE_SIZE;
  return { items: matches.slice(offset, offset + SECTOR_PAGE_SIZE), page, pageCount,
    total: matches.length, start: matches.length ? offset + 1 : 0,
    end: Math.min(offset + SECTOR_PAGE_SIZE, matches.length) };
}

/** All rows share a scale; the baseline is zero and each direction has half the track. */
export function sectorChangeScale(sectors: SectorItem[]): number {
  return Math.max(1, ...sectors.map((item) => Math.abs(item.change_pct)));
}

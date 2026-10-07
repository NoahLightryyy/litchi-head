import type { SectorItem } from "./types/market.ts";

export interface ComparisonCompany {
  code: string;
  name: string;
}

/** /stocks/search returns StockInfo (code/name/market), without a type field. */
export function readSearchCompanies(value: unknown): ComparisonCompany[] {
  if (!Array.isArray(value)) throw new Error("Invalid stock search response");
  const companies = new Map<string, ComparisonCompany>();
  for (const row of value) {
    if (!row || typeof row !== "object" || typeof row.code !== "string" ||
      !/^\d{6}$/.test(row.code) || typeof row.name !== "string" || !row.name.trim()) {
      throw new Error("Invalid stock search company");
    }
    companies.set(row.code, { code: row.code, name: row.name.trim() });
  }
  return [...companies.values()];
}

export function matchingBoards(boards: SectorItem[], query: string): SectorItem[] {
  const keyword = query.trim().toLocaleLowerCase();
  if (!keyword) return [];
  return boards.filter((board) => board.source === "eastmoney" &&
    (board.name.toLocaleLowerCase().includes(keyword) || board.id.toLowerCase().includes(keyword)))
    .sort((a, b) => Number(b.name.toLocaleLowerCase() === keyword) -
      Number(a.name.toLocaleLowerCase() === keyword) || a.name.localeCompare(b.name, "zh-CN"));
}

export function addComparisonCompany(
  selected: ComparisonCompany[], company: ComparisonCompany,
): ComparisonCompany[] {
  if (!/^\d{6}$/.test(company.code) || selected.some((item) => item.code === company.code) ||
    selected.length >= 4) return selected;
  return [...selected, company];
}

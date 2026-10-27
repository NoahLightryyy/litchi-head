export interface StockIdentity { code: string; name: string }

/** Identity is independent from a quote; never borrow a previous symbol's name. */
export function findStockIdentity(code: string, rows: unknown): StockIdentity | null {
  if (!/^[0-9]{6}$/.test(code) || !Array.isArray(rows)) return null;
  const row = rows.find(item => item && item.code === code && typeof item.name === "string"
    && item.name.trim() && item.name.trim() !== code && (!item.type || item.type === "stock"));
  return row ? { code, name: row.name.trim() } : null;
}

export function stockDisplayName(code: string, quote: unknown, identity: unknown): string {
  return findStockIdentity(code, [quote])?.name ?? findStockIdentity(code, [identity])?.name ?? code;
}

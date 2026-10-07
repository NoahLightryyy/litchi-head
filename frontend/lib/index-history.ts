import type { CandleInput } from "./chart-indicators";
export const indexNames: Record<string, string> = {sh000001:"上证指数",sz399001:"深证成指",sz399006:"创业板指"};
export function parseIndexHistory(raw: unknown, symbol: string): {bars:CandleInput[]; fetched_at:string} {
  const r = raw as {symbol?:string;source?:string;price_unit?:string;volume_unit?:string;fetched_at?:string;bars?:CandleInput[]};
  if (!r || !indexNames[symbol] || r.symbol !== symbol || r.source !== "tencent" || r.price_unit !== "points" || r.volume_unit !== "source_native" || typeof r.fetched_at !== "string" || !Number.isFinite(Date.parse(r.fetched_at)) || !Array.isArray(r.bars) || !r.bars.length) throw new Error("Invalid index history");
  let previous = "";
  for (const b of r.bars) {
    if (!b || typeof b.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(b.date) || b.date <= previous || ![b.open,b.high,b.low,b.close,b.volume].every(v=>typeof v === "number" && Number.isFinite(v)) || b.low <= 0 || b.volume < 0 || b.low > Math.min(b.open,b.close) || b.high < Math.max(b.open,b.close)) throw new Error("Invalid index candle");
    previous = b.date;
  }
  return {bars:r.bars,fetched_at:r.fetched_at};
}

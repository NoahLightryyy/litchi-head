import { parseResearchList } from "./research-list.ts";
import { parseHoldings } from "./portfolio.ts";
type Store = { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void };
export function restorePersonalRecords(store: Store, data: { watchlist: unknown; holdings: unknown }) {
  const watch = JSON.stringify(parseResearchList(JSON.stringify(data.watchlist)));
  const holdings = JSON.stringify(parseHoldings(JSON.stringify(data.holdings)));
  const keys = ["litchi.research-list.v1", "litchi.holdings.v1"] as const;
  const previous = keys.map((key) => store.getItem(key));
  try { store.setItem(keys[0],watch); store.setItem(keys[1],holdings); }
  catch {
    try { keys.forEach((key,index)=>{ if(previous[index]===null) store.removeItem(key); else store.setItem(key,previous[index]!); }); }
    catch { throw new Error("恢复和回滚均失败，请保留备份文件并检查浏览器存储。"); }
    throw new Error("恢复失败，已保留原记录。");
  }
}

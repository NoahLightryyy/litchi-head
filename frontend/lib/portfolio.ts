export interface Holding { id: string; kind: "stock" | "fund"; code: string; name: string; account: string; sector: string; value: number; cost: number | null; asOf: string }
export function parseHoldings(raw: string | null): Holding[] {
  if (raw === null) return [];
  const value: unknown = JSON.parse(raw);
  if (!Array.isArray(value) || value.length > 500) throw new Error("持仓格式无效");
  const ids = new Set<string>();
  return value.map((item: unknown) => {
    if (!item || typeof item !== "object") throw new Error("持仓记录无效");
    const x = item as Record<string, unknown>;
    if (typeof x.id !== "string" || !x.id || ids.has(x.id) || (x.kind !== "stock" && x.kind !== "fund") ||
        typeof x.code !== "string" || !/^\d{6}$/.test(x.code) ||
        ["name", "account", "sector"].some((key) => typeof x[key] !== "string" || (x[key] as string).length > 100) || !String(x.name).trim() ||
        typeof x.value !== "number" || !Number.isFinite(x.value) || x.value < 0 ||
        (x.cost !== null && (typeof x.cost !== "number" || !Number.isFinite(x.cost) || x.cost < 0)) ||
        typeof x.asOf !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(x.asOf) || !Number.isFinite(Date.parse(x.asOf)) ||
        new Date(x.asOf).toISOString().slice(0,10) !== x.asOf) throw new Error("持仓记录无效");
    ids.add(x.id); return x as unknown as Holding;
  });
}
export function portfolioSummary(entries: Holding[]) {
  const total = entries.reduce((sum, entry) => sum + entry.value, 0);
  const groups = new Map<string, number>();
  for (const entry of entries) { const label = entry.sector.trim() || "未分类"; groups.set(label, (groups.get(label) ?? 0) + entry.value); }
  return { total, groups: [...groups.entries()].sort((a, b) => b[1] - a[1]),
    largestWeight: total > 0 ? Math.max(...entries.map((entry) => entry.value / total)) : null,
    costComplete: entries.length > 0 && entries.every((entry) => entry.cost !== null),
    cost: entries.reduce((sum, entry) => sum + (entry.cost ?? 0), 0) };
}

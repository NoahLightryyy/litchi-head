export type DiscoveryHit = {code: string; name: string; kind: "stock" | "industry" | "concept" | "etf"};
export type DiscoveryResults = {data: DiscoveryHit[]; total: number; failed_sources: string[]};
export function discoveryHref(hit: DiscoveryHit): string {
  return hit.kind === "etf" ? `/etf/${hit.code}` : hit.kind === "stock" ? `/stock/${hit.code}` : `/sector/${hit.code}`;
}
export function parseDiscoveryResults(raw: unknown): DiscoveryResults {
  if (!raw || typeof raw !== "object") throw new Error("搜索响应无效");
  const r = raw as DiscoveryResults;
  if (!Array.isArray(r.data) || !Number.isInteger(r.total) || r.total < r.data.length
    || !Array.isArray(r.failed_sources) || !r.failed_sources.every(x => typeof x === "string")) throw new Error("搜索响应无效");
  for (const hit of r.data) {
    if (!hit || typeof hit.name !== "string" || !hit.name.trim() || typeof hit.code !== "string"
      || !["etf","stock","industry","concept"].includes(hit.kind)
      || !(hit.kind === "etf" || hit.kind === "stock" ? /^\d{6}$/ : /^BK\d+$/).test(hit.code)) throw new Error("搜索证券身份无效");
  }
  return r;
}

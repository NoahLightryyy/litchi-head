export type NewsKind = "announcement" | "report" | "mention";
export interface DisplayNewsItem {
  id: string; title: string; kind: NewsKind;
  published_at: string | null; time_precision: "date" | "second" | "unknown";
  association: "official_code" | "title_match" | "excerpt_match";
  provenance: {source: string; publisher: string; url: string}[];
}
export interface NewsDisplay {
  schema_version: 1; symbol: string; company_name: string | null;
  status: "ready" | "partial" | "empty" | "failed";
  start_date: string; end_date: string; fetched_at: string; cached: boolean;
  items: DisplayNewsItem[]; purpose: "display_only";
  sources: {source: "eastmoney" | "cninfo"; status: "success" | "partial" | "empty" | "failed";
    matched: number; scanned: number; total_candidates: number | null; error_code: string | null}[];
}
const object = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null;
const text = (x: unknown): x is string => typeof x === "string" && x.trim().length > 0 && !/^(nan|null|none)$/i.test(x);
const zoned = (x: unknown): x is string => text(x) && /(?:Z|[+-]\d\d:\d\d)$/.test(x) && Number.isFinite(Date.parse(x));
const day = (x: unknown): x is string => text(x) && /^\d{4}-\d{2}-\d{2}$/.test(x) && Number.isFinite(Date.parse(x)) && new Date(x).toISOString().slice(0,10) === x;
const integer = (x: unknown): x is number => typeof x === "number" && Number.isSafeInteger(x) && x >= 0;
function safeUrl(value: unknown): boolean {
  if (!text(value)) return false;
  try { const u = new URL(value); return ["http:", "https:"].includes(u.protocol) && !!u.hostname && !u.username; } catch { return false; }
}
export function parseNewsDisplay(raw: unknown, symbol: string): NewsDisplay {
  if (!object(raw) || raw.schema_version !== 1 || raw.symbol !== symbol || raw.purpose !== "display_only" ||
      !(raw.company_name === null || text(raw.company_name)) || !zoned(raw.fetched_at) ||
      !day(raw.start_date) || !day(raw.end_date) || raw.start_date > raw.end_date || typeof raw.cached !== "boolean" ||
      !["ready", "partial", "empty", "failed"].includes(String(raw.status)) || !Array.isArray(raw.items) || !Array.isArray(raw.sources)) throw new Error("新闻接口格式不兼容");
  const ids = new Set<string>();
  for (const item of raw.items) {
    if (!object(item) || !text(item.id) || ids.has(item.id) || !text(item.title) ||
        !["announcement", "report", "mention"].includes(String(item.kind)) ||
        !["official_code", "title_match", "excerpt_match"].includes(String(item.association)) ||
        !Array.isArray(item.provenance) || !item.provenance.length ||
        !item.provenance.every(p => object(p) && ["eastmoney", "cninfo"].includes(String(p.source)) && text(p.publisher) && safeUrl(p.url))) throw new Error("新闻条目无效");
    const validTime = item.time_precision === "unknown" ? item.published_at === null :
      item.time_precision === "date" ? day(item.published_at) : item.time_precision === "second" && zoned(item.published_at);
    const fetchedDay = new Date(Date.parse(raw.fetched_at) + 8 * 3600000).toISOString().slice(0, 10);
    const futureTime = item.time_precision === "date" ? String(item.published_at) > fetchedDay :
      item.published_at !== null && Date.parse(String(item.published_at)) > Date.parse(raw.fetched_at);
    if (!validTime || futureTime) throw new Error("新闻时间无效");
    if ((item.kind === "announcement") !== (item.association === "official_code") ||
        (item.kind === "mention") !== (item.association === "excerpt_match")) throw new Error("新闻关联类型无效");
    ids.add(item.id);
  }
  const seenSources = new Set<string>();
  for (const s of raw.sources) {
    if (!object(s) || !["eastmoney", "cninfo"].includes(String(s.source)) || seenSources.has(String(s.source)) ||
        !["success", "partial", "empty", "failed"].includes(String(s.status)) ||
        !integer(s.matched) || !integer(s.scanned) || s.matched > s.scanned ||
        !(s.total_candidates === null || integer(s.total_candidates)) || !(s.error_code === null || text(s.error_code))) throw new Error("新闻来源状态无效");
    seenSources.add(String(s.source));
  }
  if (seenSources.size !== 2 || (["empty", "failed"].includes(String(raw.status)) && raw.items.length) ||
      (raw.status === "ready" && !raw.items.length)) throw new Error("新闻状态与内容不一致");
  return raw as unknown as NewsDisplay;
}
export function newsPage(items: DisplayNewsItem[], kind: NewsKind | "all", keyword: string, page: number) {
  const query = keyword.trim().toLocaleLowerCase();
  const filtered = items.filter(n => (kind === "all" || n.kind === kind) && n.title.toLocaleLowerCase().includes(query));
  const pages = Math.max(1, Math.ceil(filtered.length / 10));
  const current = Math.max(1, Math.min(pages, page));
  return {items: filtered.slice((current - 1) * 10, current * 10), current, pages, total: filtered.length};
}
export function publicationLabel(item: DisplayNewsItem): string {
  if (item.published_at === null) return "发布时间未提供";
  if (item.time_precision === "date") return `${item.published_at}（公告日期）`;
  return new Date(item.published_at).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai", hour12: false});
}

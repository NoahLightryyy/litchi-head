import type { Subject } from "./policy-capital.ts";

export type RelatedKeywordOrigin = "name" | "business" | "expanded" | "user" | "code";
export interface RelatedDocument {
  id: string;
  title: string;
  url: string;
  publisher: string;
  published_at: string;
  excerpt: string;
  source: "policy_archive" | "news_archive";
  category: "policy" | "report";
  relevance: "direct" | "topic";
  matched_keywords: string[];
  reason: string;
}
export interface RelatedResearchResult {
  schema_version: 1;
  subject_kind: Subject["kind"];
  subject_id: string;
  subject_name: string;
  query: string;
  status: "ready" | "partial" | "empty" | "unavailable";
  keywords: { term: string; origin: RelatedKeywordOrigin }[];
  data: RelatedDocument[];
  sources: { source: "policy_archive" | "news_archive" | "company_profile"; status: "ok" | "unavailable" | "not_requested"; message: string }[];
  searched_at: string;
  window_days: 365;
  limitations: string[];
}
export type RelatedResearchRequest = { kind: Subject["kind"]; code: string; name: string; q: string };
export function relatedResearchRequest(subject: Subject & { name: string }, query: string): RelatedResearchRequest {
  return { kind: subject.kind, code: subject.code, name: subject.name.trim(), q: query.trim() };
}
export const relatedResearchKey = (request: RelatedResearchRequest) => ["related-research", request.kind, request.code, request.name, request.q] as const;
export const relatedResearchQueryPolicy = {
  retry: false, staleTime: 60_000, refetchOnMount: false, refetchOnWindowFocus: false, refetchOnReconnect: false,
} as const;

const nonempty = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(nonempty);
const instant = (value: unknown): value is string => nonempty(value) && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const publishedDate = (value: unknown): value is string => nonempty(value)
  && ((/^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value))) || instant(value));
function validUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}

export function parseRelatedResearch(value: unknown, request: RelatedResearchRequest): RelatedResearchResult {
  const result = value as RelatedResearchResult;
  const fail = (): never => { throw new Error("相关资料响应无法确认，请重试检索。"); };
  if (!result || result.schema_version !== 1 || result.subject_kind !== request.kind
    || result.subject_id !== request.code || result.subject_name !== request.name || result.query !== request.q
    || !["ready", "partial", "empty", "unavailable"].includes(result.status)
    || result.window_days !== 365 || !instant(result.searched_at)
    || !Array.isArray(result.keywords) || result.keywords.length > 12
    || !Array.isArray(result.data) || result.data.length > 12
    || !Array.isArray(result.sources) || !strings(result.limitations)
    || (result.data.length > 0) !== ["ready", "partial"].includes(result.status)) return fail();
  for (const keyword of result.keywords) {
    if (!keyword || !nonempty(keyword.term) || keyword.term.length > 80
      || !["name", "business", "expanded", "user", "code"].includes(keyword.origin)) return fail();
  }
  const ids = new Set<string>();
  for (const item of result.data) {
    if (!item || !nonempty(item.id) || ids.has(item.id) || !nonempty(item.title) || !validUrl(item.url)
      || !nonempty(item.publisher) || !publishedDate(item.published_at)
      || typeof item.excerpt !== "string" || item.excerpt.length > 600
      || !["policy_archive", "news_archive"].includes(item.source)
      || !["policy", "report"].includes(item.category) || !["direct", "topic"].includes(item.relevance)
      || !strings(item.matched_keywords) || !item.matched_keywords.length || !nonempty(item.reason)) return fail();
    ids.add(item.id);
  }
  for (const source of result.sources) {
    if (!source || !["policy_archive", "news_archive", "company_profile"].includes(source.source)
      || !["ok", "unavailable", "not_requested"].includes(source.status) || typeof source.message !== "string") return fail();
  }
  return result;
}

/** HTTP 200 can still mean source failure; preserve an earlier result for this exact query. */
export function requireRelatedResearch(value: unknown, request: RelatedResearchRequest): RelatedResearchResult {
  const result = parseRelatedResearch(value, request);
  if (result.status === "unavailable") throw new Error("相关资料库暂不可用，请稍后重试。");
  return result;
}

export async function fetchRelatedResearch(request: RelatedResearchRequest, signal: AbortSignal): Promise<RelatedResearchResult> {
  const base = process.env.NEXT_PUBLIC_API_URL || "/api";
  const response = await fetch(`${base}/research/related?${new URLSearchParams(request)}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(16_000)]),
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    throw new Error(typeof detail === "string" ? detail
      : response.status === 422 ? "检索条件有误，请输入有效关键词后重试（HTTP 422）。"
        : `相关资料检索失败（HTTP ${response.status}），请重试。`);
  }
  return requireRelatedResearch(body, request);
}

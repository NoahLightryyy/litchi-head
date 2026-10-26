import { api } from "./api/client.ts";
import { parseRelatedResearch, type RelatedResearchRequest, type RelatedResearchResult } from "./related-research.ts";

export interface RelatedInference { text: string; basis: "inference" }
export interface RelatedEvent {
  title: string;
  source_ids: string[];
  summary: { text: string; basis: "reported"; quotes: { source_id: string; field: "title" | "excerpt"; quote: string }[] };
  impact_direction: "positive" | "negative" | "mixed" | "unclear";
  impact_path: RelatedInference;
  affected_scope: RelatedInference;
  duration: RelatedInference;
  market_reaction: RelatedInference;
  business_realization: RelatedInference;
  subject_relation: RelatedInference;
  watchpoints: string[];
}
export interface RelatedInterpretationResult {
  schema_version: 1;
  subject_kind: RelatedResearchRequest["kind"];
  subject_id: string;
  subject_name: string;
  query: string;
  generated_at: string;
  model: string;
  prompt_version: string;
  review_status: "ai_unreviewed";
  purpose: "related_material_context_only";
  status: "interpreted" | "no_relevant_events";
  snapshot_sha256: string;
  snapshot: RelatedResearchResult;
  analysis: {
    overview: string;
    events: RelatedEvent[];
    excluded_sources: { source_id: string; reason: string }[];
    limitations: string[];
  };
}

export const INTERPRETATION_DIMENSIONS = [
  ["impact_path", "产业怎样受影响"], ["affected_scope", "涉及哪些范围"],
  ["duration", "影响可能持续多久"], ["market_reaction", "市场情绪反应"],
  ["business_realization", "经营兑现节奏"], ["subject_relation", "与当前标的的关系"],
] as const;
export const INTERPRETATION_DIRECTION = { positive: "偏正面", negative: "偏负面", mixed: "影响有利有弊", unclear: "方向尚不明确" };
export const relatedInterpretationKey = (request: RelatedResearchRequest) => ["related-interpretation", request.kind, request.code, request.q.trim()] as const;
export const relatedInterpretationQueryPolicy = { retry: false, staleTime: 60_000, refetchOnWindowFocus: false } as const;

function check(value: unknown): asserts value {
  if (!value) throw new Error("资料解读与当前标的、引用或资料快照不一致，请重新读取。");
}
function object(value: unknown, keys: string[]): Record<string, unknown> {
  check(value && typeof value === "object" && !Array.isArray(value));
  const record = value as Record<string, unknown>;
  check(Object.keys(record).length === keys.length && keys.every((key) => Object.hasOwn(record, key)));
  return record;
}
function text(value: unknown, max = Infinity): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max;
}
function strings(value: unknown, min: number, max: number): value is string[] {
  return Array.isArray(value) && value.length >= min && value.length <= max && value.every((item) => text(item));
}
function timestamp(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  return new Date(`${value.slice(0, 10)}T00:00:00Z`).toISOString().slice(0, 10) === value.slice(0, 10);
}

/** Interpretations bind to kind/code/query; a later display-name change is not a new identity. */
export function parseRelatedInterpretation(value: unknown, request: RelatedResearchRequest): RelatedInterpretationResult | null {
  if (value === null) return null;
  const result = object(value, ["schema_version", "subject_kind", "subject_id", "subject_name", "query", "generated_at", "model", "prompt_version", "review_status", "purpose", "status", "snapshot_sha256", "snapshot", "analysis"]);
  check(result.schema_version === 1 && result.subject_kind === request.kind && ["stock", "etf", "sector"].includes(String(result.subject_kind)));
  check(result.subject_id === request.code && result.query === request.q.trim() && text(result.subject_name));
  check(typeof result.subject_id === "string" && (result.subject_kind === "sector" ? /^(?:BK\d{4}|sina:[A-Za-z0-9_]+)$/.test(result.subject_id) : /^\d{6}$/.test(result.subject_id)));
  check(result.review_status === "ai_unreviewed" && result.purpose === "related_material_context_only");
  check(["interpreted", "no_relevant_events"].includes(String(result.status)) && timestamp(result.generated_at) && text(result.model) && text(result.prompt_version));
  check(typeof result.snapshot_sha256 === "string" && /^[0-9a-f]{64}$/.test(result.snapshot_sha256));
  // Stored source names belong to the saved snapshot, not the current quote's display name.
  const snapshot = parseRelatedResearch(result.snapshot, { ...request, name: result.subject_name, q: request.q.trim() });
  check(snapshot.data.length > 0);
  const sources = new Map(snapshot.data.map((source) => [source.id, source]));
  const used = new Set<string>();
  const analysis = object(result.analysis, ["overview", "events", "excluded_sources", "limitations"]);
  check(text(analysis.overview, 600) && strings(analysis.limitations, 1, 8));
  check(Array.isArray(analysis.events) && analysis.events.length <= 6 && (analysis.events.length > 0) === (result.status === "interpreted"));
  for (const rawEvent of analysis.events) {
    const event = object(rawEvent, ["title", "source_ids", "summary", "impact_direction", ...INTERPRETATION_DIMENSIONS.map(([key]) => key), "watchpoints"]);
    check(text(event.title, 120) && strings(event.source_ids, 1, 12) && new Set(event.source_ids).size === event.source_ids.length);
    for (const id of event.source_ids) { check(sources.has(id) && !used.has(id)); used.add(id); }
    check(["positive", "negative", "mixed", "unclear"].includes(String(event.impact_direction)) && strings(event.watchpoints, 1, 4));
    for (const [key] of INTERPRETATION_DIMENSIONS) {
      const inference = object(event[key], ["text", "basis"]);
      check(inference.basis === "inference" && text(inference.text, 600));
    }
    const summary = object(event.summary, ["text", "basis", "quotes"]);
    check(summary.basis === "reported" && text(summary.text, 600) && Array.isArray(summary.quotes) && summary.quotes.length >= 1 && summary.quotes.length <= 4);
    for (const rawQuote of summary.quotes) {
      const quote = object(rawQuote, ["source_id", "field", "quote"]);
      check(text(quote.source_id) && event.source_ids.includes(quote.source_id));
      check((quote.field === "title" || quote.field === "excerpt") && text(quote.quote, 300) && quote.quote.length >= 2);
      check(sources.get(quote.source_id)![quote.field].includes(quote.quote));
    }
  }
  check(Array.isArray(analysis.excluded_sources) && analysis.excluded_sources.length <= 12);
  for (const rawExcluded of analysis.excluded_sources) {
    const excluded = object(rawExcluded, ["source_id", "reason"]);
    check(text(excluded.source_id) && text(excluded.reason, 240) && sources.has(excluded.source_id) && !used.has(excluded.source_id));
    used.add(excluded.source_id);
  }
  check(used.size === sources.size);
  return result as unknown as RelatedInterpretationResult;
}

function endpoint(request: RelatedResearchRequest): string {
  const params = new URLSearchParams({ kind: request.kind, code: request.code, name: request.name.trim(), q: request.q.trim() });
  return `/research/related/interpretation?${params}`;
}
export async function readRelatedInterpretation(request: RelatedResearchRequest, signal?: AbortSignal): Promise<RelatedInterpretationResult | null> {
  const raw = await api.getRaw<unknown>(endpoint(request), undefined, { signal });
  return parseRelatedInterpretation(raw, request);
}
export async function generateRelatedInterpretation(request: RelatedResearchRequest, refresh: boolean): Promise<RelatedInterpretationResult> {
  const raw = await api.postRaw<unknown>(endpoint(request), { refresh }, { signal: AbortSignal.timeout(130_000) });
  const result = parseRelatedInterpretation(raw, request);
  if (!result) throw new Error("尚未取得资料解读，请读取已保存结果或稍后重试。");
  return result;
}

/** A newer retrieval time alone is not a change to the material actually interpreted. */
export function relatedSnapshotChanged(saved: RelatedInterpretationResult, current?: RelatedResearchResult): boolean {
  if (!current) return false;
  if (current.subject_kind !== saved.subject_kind || current.subject_id !== saved.subject_id || current.query !== saved.query) return true;
  const content = (snapshot: RelatedResearchResult) => JSON.stringify([...snapshot.data].sort((a, b) => a.id.localeCompare(b.id)));
  return content(saved.snapshot) !== content(current);
}

export function copyableRelatedInterpretation(result: RelatedInterpretationResult): string {
  const sources = new Map(result.snapshot.data.map((source) => [source.id, source]));
  const lines = [
    `${result.subject_name} · ${result.subject_id} · 资料研究要点`,
    "AI 解读，未经人工复核；资料整理与条件性推断，不是已核验事实或买卖指令。",
    `查询：${result.query || "自动提词"}；生成：${result.generated_at}；资料快照检索：${result.snapshot.searched_at}`,
    result.analysis.overview,
  ];
  for (const event of result.analysis.events) {
    lines.push("", event.title, `资料概况：${event.summary.text}`, `影响方向（推断）：${INTERPRETATION_DIRECTION[event.impact_direction]}`);
    for (const [key, label] of INTERPRETATION_DIMENSIONS) lines.push(`${label}（AI 推断）：${event[key].text}`);
    lines.push(`后续核查：${event.watchpoints.join("；")}`);
    for (const id of event.source_ids) {
      const source = sources.get(id)!;
      lines.push(`来源：${source.title}｜${source.publisher}｜${source.published_at}｜${source.url}`);
    }
  }
  lines.push("", `资料限制：${result.analysis.limitations.join("；")}`);
  return lines.join("\n");
}

import { api } from "./api/client.ts";
import type { InstrumentType } from "./types/debate.ts";

export type EntryHorizon = "short" | "medium" | "long";
export interface EntryPlanIdentity { sessionId: string; stockCode: string; instrumentType: InstrumentType }
export interface EntryEvidence {
  id: string; kind: "analysis" | "quote" | "daily"; title: string; data_time: string; content: string;
}
export interface HorizonEntryPlan {
  horizon: EntryHorizon;
  status: "consider" | "waiting" | "insufficient";
  summary: string;
  conditions: { condition: string; status: "met" | "unmet" | "unknown"; explanation: string; evidence_ids: string[] }[];
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  price_basis: string;
  price_evidence_ids: string[];
  invalidation: string[];
  batches: { budget_pct: number; trigger: string }[];
  position_note: string;
  limitations: string[];
}
export interface EntryPlanResult {
  schema_version: 1;
  session_id: string;
  source_session_id: string;
  source_research_generated_at: string;
  stock_code: string;
  instrument_type: InstrumentType;
  stock_name: string;
  generated_at: string;
  model: string;
  evidence: EntryEvidence[];
  gaps: string[];
  cached: boolean;
  purpose: "conditional_research_plan";
  status_basis: "ai_review_of_dated_evidence";
  plans: HorizonEntryPlan[];
}

function check(value: unknown): asserts value {
  if (!value) throw new Error("入场计划数据不完整或与当前标的不一致，请重新读取。");
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
function strings(value: unknown, min = 0, max = Infinity): value is string[] {
  return Array.isArray(value) && value.length >= min && value.length <= max && value.every((item) => text(item));
}
function timestamp(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  const date = value.slice(0, 10);
  return new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) === date;
}
const positive = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value > 0;

export function parseEntryPlan(value: unknown, identity: EntryPlanIdentity): EntryPlanResult {
  const item = object(value, ["schema_version", "session_id", "source_session_id", "source_research_generated_at", "stock_code", "instrument_type", "stock_name", "generated_at", "model", "evidence", "gaps", "cached", "purpose", "status_basis", "plans"]);
  check(item.schema_version === 1 && item.purpose === "conditional_research_plan" && item.status_basis === "ai_review_of_dated_evidence");
  check(text(item.session_id, 100) && item.session_id === identity.sessionId && item.source_session_id === identity.sessionId);
  check(typeof item.stock_code === "string" && /^\d{6}$/.test(item.stock_code) && item.stock_code === identity.stockCode);
  check(["stock", "etf"].includes(String(item.instrument_type)) && item.instrument_type === identity.instrumentType);
  check(text(item.stock_name) && text(item.model) && timestamp(item.generated_at) && timestamp(item.source_research_generated_at));
  check(typeof item.cached === "boolean" && strings(item.gaps));
  check(Array.isArray(item.evidence) && item.evidence.length > 0);
  const sources = new Map<string, EntryEvidence>();
  for (const raw of item.evidence) {
    const source = object(raw, ["id", "kind", "title", "data_time", "content"]);
    check(text(source.id, 100) && !sources.has(source.id) && ["analysis", "quote", "daily"].includes(String(source.kind)));
    check(text(source.title, 200) && text(source.data_time, 100) && text(source.content, 120000));
    sources.set(source.id, source as unknown as EntryEvidence);
  }
  function references(value: unknown, min: number): asserts value is string[] {
    check(strings(value, min, 8));
    check(new Set(value).size === value.length && value.every((id) => sources.has(id)));
  }
  check(Array.isArray(item.plans) && item.plans.length === 3);
  const horizons = new Set<string>();
  for (const raw of item.plans) {
    const plan = object(raw, ["horizon", "status", "summary", "conditions", "entry_low", "entry_high", "stop_loss", "price_basis", "price_evidence_ids", "invalidation", "batches", "position_note", "limitations"]);
    check(typeof plan.horizon === "string" && ["short", "medium", "long"].includes(plan.horizon) && !horizons.has(plan.horizon));
    horizons.add(plan.horizon);
    check(["consider", "waiting", "insufficient"].includes(String(plan.status)) && text(plan.summary, 600));
    check(text(plan.price_basis, 600) && text(plan.position_note, 600) && strings(plan.invalidation, 1, 5) && strings(plan.limitations, 1, 6));
    check(Array.isArray(plan.conditions) && plan.conditions.length >= 1 && plan.conditions.length <= 6);
    for (const rawCondition of plan.conditions) {
      const condition = object(rawCondition, ["condition", "status", "explanation", "evidence_ids"]);
      check(text(condition.condition, 400) && text(condition.explanation, 600) && ["met", "unmet", "unknown"].includes(String(condition.status)));
      references(condition.evidence_ids, 1);
      if (condition.status !== "unknown") check(condition.evidence_ids.every((id) => sources.get(id)!.kind !== "analysis"));
    }
    references(plan.price_evidence_ids, 0);
    const prices = [plan.entry_low, plan.entry_high, plan.stop_loss];
    if (prices.some((price) => price !== null)) {
      check(positive(plan.entry_low) && positive(plan.entry_high) && positive(plan.stop_loss));
      check(plan.stop_loss < plan.entry_low && plan.entry_low <= plan.entry_high);
      check(plan.price_evidence_ids.some((id) => ["quote", "daily"].includes(sources.get(id)!.kind)));
    }
    if (plan.status === "consider") check(plan.entry_low !== null && plan.conditions.every((condition) => (condition as { status: string }).status === "met"));
    check(Array.isArray(plan.batches) && plan.batches.length >= 1 && plan.batches.length <= 4);
    let sum = 0;
    for (const rawBatch of plan.batches) {
      const batch = object(rawBatch, ["budget_pct", "trigger"]);
      check(positive(batch.budget_pct) && batch.budget_pct <= 100 && text(batch.trigger, 400));
      check(/^\d+(?:\.\d{1,2})?$/.test(String(batch.budget_pct)));
      sum += batch.budget_pct;
    }
    check(Math.abs(sum - 100) <= 0.000001);
  }
  return item as unknown as EntryPlanResult;
}

/** GET never starts research; POST sends only the explicit refresh choice. */
export async function readEntryPlan(identity: EntryPlanIdentity, signal?: AbortSignal): Promise<EntryPlanResult | null> {
  const raw = await api.getRaw<unknown>(`/debate/${encodeURIComponent(identity.sessionId)}/entry-plan`, undefined, { signal });
  return raw === null ? null : parseEntryPlan(raw, identity);
}
export async function generateEntryPlan(identity: EntryPlanIdentity, refresh: boolean, signal?: AbortSignal): Promise<EntryPlanResult> {
  const raw = await api.postRaw<unknown>(`/debate/${encodeURIComponent(identity.sessionId)}/entry-plan`, { refresh }, { signal });
  return parseEntryPlan(raw, identity);
}

export const ENTRY_HORIZONS: Record<EntryHorizon, string> = { short: "短期 · 1–5 个交易日", medium: "中期 · 1–3 个月", long: "长期 · 1–3 年" };
export const ENTRY_STATUS = { consider: "可关注入场条件", waiting: "等待条件满足", insufficient: "依据不足，继续观察" };
export const CONDITION_STATUS = { met: "按所示数据已满足", unmet: "尚未满足", unknown: "尚无法判断" };

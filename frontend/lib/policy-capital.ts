export type Subject = { kind: "sector" | "stock" | "etf"; code: string; name?: string };
export type Claim = { id: string; text: string; assessment: "supported" | "inferred" | "insufficient" | "contradicted"; evidence_ids: string[]; limitations: string[] };
export type Evidence = { id: string; title: string; url: string; publisher: string; published_date: string; authored_date: string | null; effective_date: string | null; locator: string; summary: string; retrieved_at: string };
export type EvidencePackage = { schema_version: 1; package_id: string; subject_kind: Subject["kind"]; subject_id: string; status: "partial" | "verified_scope"; evidence: Evidence[]; claims: Claim[]; gaps: string[]; holdings: { etf_symbol: string; as_of: string; published_date: string; coverage: string; evidence_id: string; holdings: { symbol: string; nav_weight_pct: string }[] }[] };
export type Job = { job_id: string; status: "queued" | "running" | "succeeded" | "failed"; result: null | { evidence_package_id: string; subject_kind: Subject["kind"]; subject_id: string; claims: Claim[]; conditions: string[]; counterarguments: string[]; gaps: string[]; generated_at: string; model: string; prompt_version: string; estimated_cost_cny: string }; error: null | { code: string; message: string; retryable: boolean } };
export type Preview = { status: "ready" | "blocked"; evidence_package_id: string; quantity: number | null; estimated_cost: string | null; remaining_cash: string | null; gaps: string[] };
export const packageId = (s: Subject) => `v1-${s.kind}-${s.code}`;
export const jobStorageKey = (s: Subject) => `policy-capital:job:v1:${s.kind}:${s.code}`;
export const decimal = (v: unknown): v is string => typeof v === "string" && /^\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v);
export const positiveDecimal = (v: unknown): v is string => decimal(v) && /[1-9]/.test(v.split(/[eE]/)[0]);
function assert(ok: unknown): asserts ok { if (!ok) throw new Error("服务端响应不符合冻结契约，已停止展示或计算，请刷新核验。"); }
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === "string");
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v));
const instant = (v: unknown): v is string => typeof v === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(v) && !Number.isNaN(Date.parse(v));
export function parseSaved(raw: string): { jobId?: string; key: string; budget: string } {
  const s = JSON.parse(raw); assert(s && typeof s.key === "string" && s.key.length >= 8 && s.key.length <= 128 && positiveDecimal(s.budget) && (s.jobId === undefined || typeof s.jobId === "string" && s.jobId.length > 0)); return s;
}
function claimsValid(claims: Claim[], p: EvidencePackage) {
  assert(Array.isArray(claims));
  const ids = new Set(p.evidence.map(e => e.id));
  const seen = new Set<string>();
  for (const c of claims) {
    assert(c && typeof c.id === "string" && !seen.has(c.id)); seen.add(c.id);
    assert(typeof c.text === "string" && ["supported", "inferred", "insufficient", "contradicted"].includes(c.assessment));
    assert(Array.isArray(c.evidence_ids) && c.evidence_ids.every(id => ids.has(id)));
    assert(Array.isArray(c.limitations) && c.limitations.every(x => typeof x === "string"));
    assert(!["supported", "contradicted"].includes(c.assessment) || c.evidence_ids.length);
    assert(c.assessment === "supported" || c.limitations.length);
  }
}
export function parsePackage(raw: unknown, s: Subject): EvidencePackage {
  const p = raw as EvidencePackage;
  assert(p && p.schema_version === 1 && p.package_id === packageId(s) && p.subject_kind === s.kind && p.subject_id === s.code);
  assert(Array.isArray(p.evidence) && Array.isArray(p.holdings) && strings(p.gaps));
  assert(new Set(p.evidence.map(e => e.id)).size === p.evidence.length);
  for (const e of p.evidence) { assert(e && typeof e.id === "string" && typeof e.title === "string" && typeof e.url === "string" && /^https?:\/\//.test(e.url) && typeof e.publisher === "string" && typeof e.locator === "string" && typeof e.summary === "string" && date(e.published_date) && (e.authored_date === null || date(e.authored_date)) && (e.effective_date === null || date(e.effective_date)) && instant(e.retrieved_at)); }
  assert(p.status === "partial" ? p.gaps.length : p.status === "verified_scope" && p.evidence.length && !p.gaps.length);
  claimsValid(p.claims, p);
  for (const h of p.holdings) { assert(/^\d{6}$/.test(h.etf_symbol) && (p.subject_kind !== "etf" || h.etf_symbol === p.subject_id)); assert(date(h.as_of) && date(h.published_date) && h.published_date >= h.as_of && ["top_ten", "full_disclosure", "other_subset"].includes(h.coverage)); assert(p.evidence.some(e => e.id === h.evidence_id)); assert(Array.isArray(h.holdings) && h.holdings.every(x => /^\d{6}$/.test(x.symbol) && decimal(x.nav_weight_pct) && Number(x.nav_weight_pct) <= 100)); assert(new Set(h.holdings.map(x => x.symbol)).size === h.holdings.length && h.holdings.reduce((sum,x) => sum + Number(x.nav_weight_pct),0) <= 100); }
  return p;
}
export function parseJob(raw: unknown, p: EvidencePackage): Job {
  const j = raw as Job;
  assert(j && typeof j.job_id === "string" && ["queued", "running", "succeeded", "failed"].includes(j.status));
  assert((j.status === "succeeded") === (j.result != null) && (j.status === "failed") === (j.error != null));
  if (j.result) { const r = j.result; assert(r.evidence_package_id === p.package_id && r.subject_kind === p.subject_kind && r.subject_id === p.subject_id); claimsValid(r.claims, p); assert(decimal(r.estimated_cost_cny)); assert([r.conditions,r.counterarguments,r.gaps].every(strings)); assert(instant(r.generated_at) && typeof r.model === "string" && r.model.length > 0 && typeof r.prompt_version === "string" && r.prompt_version.length > 0); }
  if (j.error) assert(typeof j.error.message === "string" && ["SOURCE_UNAVAILABLE", "BUDGET_EXCEEDED", "MODEL_FAILED", "INTERRUPTED"].includes(j.error.code) && j.error.retryable === (j.error.code !== "BUDGET_EXCEEDED"));
  return j;
}
export function parsePreview(raw: unknown, id: string): Preview {
  const p = raw as Preview; assert(p && p.evidence_package_id === id && strings(p.gaps));
  if (p.status === "blocked") assert(p.quantity === null && p.estimated_cost === null && p.remaining_cash === null && p.gaps.length);
  else assert(p.status === "ready" && Number.isInteger(p.quantity) && p.quantity! > 0 && decimal(p.estimated_cost) && decimal(p.remaining_cash) && !p.gaps.length);
  return p;
}
export class ResearchApiError extends Error { status: number; constructor(status: number, message: string) { super(message); this.status = status; } }
export async function researchFetch(path: string, init?: RequestInit): Promise<unknown> {
  const base = process.env.NEXT_PUBLIC_API_URL || "/api";
  const signal = init?.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000);
  const response = await fetch(`${base}/research${path}`, { ...init, signal, headers: { "Content-Type": "application/json", ...init?.headers } });
  const body = await response.json();
  if (!response.ok) throw new ResearchApiError(response.status, body.message || body.error?.message || `请求失败（${response.status}）`);
  return body;
}

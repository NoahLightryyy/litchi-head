import type { AgentAnalysis } from "./types/debate.ts";

export const HORIZONS = { short: "短期 · 未来 1–5 个交易日", medium: "中期 · 未来 1–3 个月", long: "长期 · 未来 1–3 年" } as const;
export type Horizon = keyof typeof HORIZONS;
export interface HorizonOpinion {
  horizon: Horizon;
  status: "supported" | "insufficient";
  direction: "Bullish" | "Bearish" | "Neutral" | null;
  thesis: string;
  assumptions: string[];
  invalidation: string[];
  review_on: string;
  review_trigger: string;
  evidence: string[];
  limitations: string;
}
const text = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const list = (value: unknown): value is string[] => Array.isArray(value) && value.length > 0 && value.every(text);
const day = (date: Date) => new Intl.DateTimeFormat("en-CA", {timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).format(date);
const dateMs = (value: string) => {
  const ms = Date.parse(value);
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(ms) && new Date(ms).toISOString().slice(0,10) === value ? ms : NaN;
};

export function horizonView(a: AgentAnalysis, horizon: Horizon, now = new Date()): { opinion: HorizonOpinion | null; eligible: boolean; reason: string } {
  const opinions = a.horizons;
  const missing = (reason: string) => ({opinion: null, eligible:false, reason});
  if (!a.success) return missing("该流派分析未完成");
  if (!Array.isArray(opinions) || opinions.length !== 3 || Object.keys(HORIZONS).some(key => opinions.filter(item => item?.horizon === key).length !== 1)) return missing("缺少完整三周期记录，请重新分析；不能从流派名称推断期限");
  const opinion = opinions.find(item => item.horizon === horizon)!;
  if (!["supported","insufficient"].includes(opinion.status) || ![opinion.thesis,opinion.review_trigger,opinion.limitations].every(text) || ![opinion.assumptions,opinion.invalidation,opinion.evidence].every(list)) return missing("条件或证据缺项，不能显示方向结论");
  const generated = new Date(a.research_generated_at ?? "");
  const review = typeof opinion.review_on === "string" ? dateMs(opinion.review_on) : NaN;
  if (!Number.isFinite(generated.getTime()) || !Number.isFinite(review) || generated > now) return missing("研究起点或复核日期无效");
  const start = dateMs(day(generated));
  if (review < start || review - start > ({short:7,medium:93,long:366}[horizon] * 86400000)) return missing("复核日期不符合本周期要求");
  if (review < dateMs(day(now))) return {opinion,eligible:false,reason:"已过最迟复核日期，需要重新分析"};
  if (opinion.status === "insufficient") return {opinion,eligible:false,reason:"该周期证据不足，未形成方向结论"};
  if (!["Bullish","Bearish","Neutral"].includes(opinion.direction ?? "")) return missing("缺少有效方向结论");
  return {opinion,eligible:true,reason:"条件成立时的研究观点；尚未持续监测条件是否变化"};
}

export function horizonConsensus(analyses: AgentAnalysis[], horizon: Horizon, now = new Date()): string {
  if (analyses.length !== 5 || new Set(analyses.map(a=>a.agent_name)).size !== 5 || analyses.some(a=>!horizonView(a,horizon,now).eligible)) return "条件或证据未齐，不形成方向共识";
  const directions = new Set(analyses.map(a=>horizonView(a,horizon,now).opinion?.direction));
  if (directions.size > 1) return "流派存在分歧";
  return `条件性一致：${directionLabel([...directions][0])}`;
}
export function directionLabel(value: unknown): string { return value === "Bullish" ? "看涨" : value === "Bearish" ? "看跌" : value === "Neutral" ? "中性" : "未形成方向"; }

/** Distribution of usable opinions, never a calibrated return probability. */
export function horizonDistribution(analyses: AgentAnalysis[], horizon: Horizon, now = new Date()) {
  const counts = { Bullish: 0, Bearish: 0, Neutral: 0 };
  const identities = new Map<string, number>();
  for (const a of analyses) identities.set(a.agent_name, (identities.get(a.agent_name) ?? 0) + 1);
  let unavailable = 0;
  for (const [name, duplicates] of identities) {
    const a = analyses.find(item => item.agent_name === name)!;
    const view = horizonView(a, horizon, now);
    if (!name.trim() || duplicates !== 1 || !view.eligible || !view.opinion?.direction) {
      unavailable++;
    } else {
      counts[view.opinion.direction]++;
    }
  }
  const total = identities.size;
  return { counts, unavailable, total, eligible: total - unavailable };
}

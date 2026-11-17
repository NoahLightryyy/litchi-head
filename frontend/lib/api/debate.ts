import { api } from "./client";
import type { DebateHistoryItem, DebateRequest, DebateStatus, DebateResult, TrustReport, InstrumentType } from "@/lib/types/debate";
import { debateInstrumentMatches, parseDebateRun } from "@/lib/debate-instrument";

/** 触发辩论 */
export async function runDebate(req: DebateRequest): Promise<{ session_id: string }> {
  return parseDebateRun(await api.post<unknown>("/debate/run", req), req);
}

/** 查询辩论状态 */
export async function fetchDebateStatus(sessionId: string): Promise<DebateStatus> {
  return api.get(`/debate/status/${sessionId}`);
}

/** 获取辩论结果 */
export async function fetchDebateResult(sessionId: string): Promise<DebateResult | null> {
  return api.get(`/debate/result/${sessionId}`);
}

/** 大师信任度报告 */
export async function fetchTrustReport(agentName: string): Promise<TrustReport> {
  return api.get(`/trust/report/${agentName}`);
}

/** 信任度排行 */
export async function fetchTrustLeaderboard(): Promise<TrustReport[]> {
  return api.get("/trust/leaderboard");
}

/** Persisted history; reading it never starts a new analysis. */
export async function fetchDebateHistory(stockCode: string, offset = 0, instrumentType: InstrumentType = "stock"): Promise<DebateHistoryItem[]> {
  const data = await api.get<unknown>("/debate/history", { stock_code: stockCode, instrument_type: instrumentType, offset: String(offset) });
  if (!Array.isArray(data)) throw new Error("分析历史响应无效");
  return data.filter(item => debateInstrumentMatches(item, stockCode, instrumentType)) as DebateHistoryItem[];
}

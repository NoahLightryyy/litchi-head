import { api } from "./client";
import type { DebateRequest, DebateStatus, DebateResult, TrustReport } from "@/lib/types/debate";

/** 触发辩论 */
export async function runDebate(req: DebateRequest): Promise<{ session_id: string }> {
  return api.post("/debate/run", req);
}

/** 查询辩论状态 */
export async function fetchDebateStatus(sessionId: string): Promise<DebateStatus> {
  return api.get(`/debate/status/${sessionId}`);
}

/** 获取辩论结果 */
export async function fetchDebateResult(sessionId: string): Promise<DebateResult> {
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

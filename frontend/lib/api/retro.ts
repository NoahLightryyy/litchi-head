import { api } from "./client";
import type { RetroRecord, RetroSummary, RefreshResult } from "@/lib/types/retro";

/** 查询复盘记录列表 */
export async function fetchRetroRecords(
  params?: {
    stock_code?: string;
    outcome?: string;
    limit?: number;
    offset?: number;
  }
): Promise<RetroRecord[]> {
  const query: Record<string, string> = {};
  if (params?.stock_code) query.stock_code = params.stock_code;
  if (params?.outcome) query.outcome = params.outcome;
  if (params?.limit) query.limit = String(params.limit);
  if (params?.offset) query.offset = String(params.offset);
  return api.get("/retro/records", Object.keys(query).length ? query : undefined);
}

/** 获取复盘聚合统计 */
export async function fetchRetroSummary(): Promise<RetroSummary> {
  return api.get("/retro/summary");
}

/** 更新用户操作 */
export async function updateRetroAction(
  recordId: string,
  action: string
): Promise<RetroRecord> {
  return api.put(`/retro/${recordId}/action`, { action });
}

/** 更新实际结果 */
export async function updateRetroOutcome(
  recordId: string,
  returnPct: number,
  price: number
): Promise<RetroRecord> {
  return api.put(`/retro/${recordId}/outcome`, {
    return_pct: returnPct,
    price,
  });
}

/** 批量刷新 pending 记录 */
export async function refreshRetroRecords(): Promise<RefreshResult> {
  return api.post("/retro/refresh");
}

/** 删除复盘记录 */
export async function deleteRetroRecord(recordId: string): Promise<void> {
  return api.del(`/retro/${recordId}`);
}

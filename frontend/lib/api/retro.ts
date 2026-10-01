import { api } from "./client";
import type { RetroRecord, RetroSummary } from "@/lib/types/retro";

/** 查询复盘记录列表 */
export async function fetchRetroRecords(
  params?: {
    stock_code?: string;
    outcome?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal,
): Promise<RetroRecord[]> {
  const query: Record<string, string> = {};
  if (params?.stock_code) query.stock_code = params.stock_code;
  if (params?.outcome) query.outcome = params.outcome;
  if (params?.limit) query.limit = String(params.limit);
  if (params?.offset) query.offset = String(params.offset);
  return api.get("/retro/records", Object.keys(query).length ? query : undefined,
    {signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(15000)])});
}

/** 获取复盘聚合统计 */
export async function fetchRetroSummary(signal?: AbortSignal): Promise<RetroSummary> {
  return api.get("/retro/summary", undefined,
    {signal: AbortSignal.any([...(signal ? [signal] : []), AbortSignal.timeout(15000)])});
}

/** 删除复盘记录 */
export async function deleteRetroRecord(recordId: string): Promise<void> {
  return api.del(`/retro/${recordId}`);
}

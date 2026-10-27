import { api } from "./api/client.ts";
import type { RetroRecord } from "./types/retro.ts";

export interface RetroObservation {
  record_id: string; stock_code: string;
  status: "observed" | "waiting" | "unavailable" | "not_found";
  message: string; recorded_date: string | null; baseline_date: string | null; latest_date: string | null;
  baseline_price: number | null; latest_price: number | null; change_pct: number | null;
  alignment: "same" | "opposite" | "flat" | "no_direction" | null;
  source: "tencent"; price_basis: "raw"; baseline_method: "first_available_close_on_or_after_record_date";
  fetched_at: string | null;
}
export const observationLabel = { same: "目前与判断同向", opposite: "目前与判断反向", flat: "收盘价暂未变化", no_direction: "当时未给明确方向" };
export async function readRetroObservations(records: Pick<RetroRecord, "record_id" | "stock_code">[], signal: AbortSignal): Promise<RetroObservation[]> {
  const raw = await api.get<unknown>("/retro/observations", { record_ids: records.map(r => r.record_id).join(",") }, { signal });
  if (!Array.isArray(raw) || raw.length !== records.length) throw new Error("市场观察暂时不完整，请刷新");
  const seen = new Set<string>();
  for (const item of raw) {
    const record = records.find(r => r.record_id === item?.record_id);
    if (!record || seen.has(item.record_id) || (item.status !== "not_found" && record.stock_code !== item.stock_code)
      || !["observed", "waiting", "unavailable", "not_found"].includes(item.status)
      || item.source !== "tencent" || item.price_basis !== "raw" || typeof item.message !== "string"
      || item.baseline_method !== "first_available_close_on_or_after_record_date") throw new Error("市场观察和研究记录没有对上");
    seen.add(item.record_id);
    if (item.status === "observed" && (
      !/^\d{4}-\d{2}-\d{2}$/.test(item.baseline_date) || !/^\d{4}-\d{2}-\d{2}$/.test(item.latest_date)
      || item.latest_date <= item.baseline_date || !Number.isFinite(item.baseline_price) || item.baseline_price <= 0
      || !Number.isFinite(item.latest_price) || item.latest_price <= 0 || !Number.isFinite(item.change_pct)
      || Math.abs(item.change_pct - (item.latest_price / item.baseline_price - 1) * 100) > 0.00011
      || !Object.hasOwn(observationLabel, item.alignment))) throw new Error("市场观察的价格或日期不完整");
  }
  return raw;
}

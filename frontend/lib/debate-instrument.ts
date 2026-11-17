import type { DebateRequest, InstrumentType } from "./types/debate.ts";

/** Legacy persisted records without a type belong only to stock research. */
export function debateInstrumentMatches(value: unknown, code: string, instrumentType: InstrumentType): boolean {
  if (!value || typeof value !== "object") return false;
  const item = value as { stock_code?: unknown; instrument_type?: unknown };
  return item.stock_code === code && (item.instrument_type === undefined ? "stock" : item.instrument_type) === instrumentType;
}
export const debateHistoryKey = (code: string, instrumentType: InstrumentType, offset = 0) => ["debate", "history", instrumentType, code, offset] as const;
export const debateResultKey = (sessionId: string | null, instrumentType: InstrumentType) => ["debate", "result", instrumentType, sessionId] as const;

export function debateRequest(code: string, name: string, instrumentType: InstrumentType): DebateRequest {
  return { stock_code: code, instrument_type: instrumentType, question: `${name} ${instrumentType === "etf" ? "ETF 投资分析" : "投资分析"}` };
}

export function parseDebateRun(value: unknown, request: DebateRequest): { session_id: string } {
  if (!value || typeof value !== "object") throw new Error("分析会话响应无效");
  const data = value as { session_id?: unknown; status?: unknown; instrument_type?: unknown };
  if (!debateInstrumentMatches(value, request.stock_code, request.instrument_type ?? "stock")
    || data.instrument_type !== (request.instrument_type ?? "stock")
    || typeof data.session_id !== "string" || !data.session_id.trim() || data.status !== "completed") {
    throw new Error("分析会话与当前标的不一致");
  }
  return { session_id: data.session_id };
}

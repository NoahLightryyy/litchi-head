export const thsFundPeriods = [
  ["latest", "即时"], ["3", "3日"], ["5", "5日"], ["10", "10日"], ["20", "20日"],
] as const;
export type ThsFundPeriod = typeof thsFundPeriods[number][0];

export interface ThsFundResult {
  source: "ths";
  metric: "net_inflow";
  period: ThsFundPeriod;
  unit: "CNY";
  status: "partial" | "unavailable";
  data: { code: string; name: string; price: number | null; net_inflow: number }[];
  data_as_of: null;
  fetched_at: string;
  cached: boolean;
  scope: string;
  reason: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function parseThsFundResult(value: unknown, period: ThsFundPeriod): ThsFundResult {
  if (!thsFundPeriods.some(([key]) => key === period) || !isRecord(value)
    || value.source !== "ths" || value.metric !== "net_inflow" || value.period !== period
    || value.unit !== "CNY" || (value.status !== "partial" && value.status !== "unavailable")
    || !Array.isArray(value.data) || value.data.length > 50 || value.data_as_of !== null
    || typeof value.fetched_at !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value.fetched_at)
    || !Number.isFinite(Date.parse(value.fetched_at)) || typeof value.cached !== "boolean"
    || typeof value.scope !== "string" || typeof value.reason !== "string") {
    throw new Error("同花顺榜单口径校验失败");
  }
  if ((value.status === "unavailable" && value.data.length > 0)
    || (value.status === "partial" && value.data.length === 0)) {
    throw new Error("同花顺榜单状态与数据不一致");
  }
  const seen = new Set<string>();
  let previous = Infinity;
  for (const row of value.data) {
    if (!isRecord(row) || typeof row.code !== "string" || !/^\d{6}$/.test(row.code)
      || seen.has(row.code) || typeof row.name !== "string" || !row.name.trim()
      || typeof row.net_inflow !== "number" || !Number.isFinite(row.net_inflow)
      || row.net_inflow > previous
      || (row.price !== null && (typeof row.price !== "number" || !Number.isFinite(row.price) || row.price <= 0))) {
      throw new Error("同花顺榜单行校验失败");
    }
    seen.add(row.code);
    previous = row.net_inflow;
  }
  return value as unknown as ThsFundResult;
}

/** An unavailable HTTP 200 must not replace the last successful query value. */
export function requireThsFundData(value: unknown, period: ThsFundPeriod): ThsFundResult {
  const result = parseThsFundResult(value, period);
  if (result.status === "unavailable") throw new Error("同花顺资金净流入暂不可用");
  return result;
}

export const thsFundQueryPolicy = {
  retry: false,
  staleTime: 120000,
  refetchOnReconnect: true,
} as const;

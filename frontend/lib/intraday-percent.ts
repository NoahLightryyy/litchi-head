/** Percentage display uses the dated quote reference, never the first minute. */
export interface IntradayReferenceQuote {
  code: string;
  prev_close: number;
  fetched_at: string | null;
}

function tradingDay(value: string | null): string | null {
  if (!value || !/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(date);
}

export function intradayReferenceClose(
  code: string,
  quote: IntradayReferenceQuote | null | undefined,
  points: readonly { timestamp: string }[],
): number | null {
  if (!quote || quote.code !== code || !Number.isFinite(quote.prev_close) || quote.prev_close <= 0 || !points.length) return null;
  const day = tradingDay(quote.fetched_at);
  if (!day || points.some(point => tradingDay(point.timestamp) !== day)) return null;
  return quote.prev_close;
}

export function formatIntradayPercent(price: number, reference: number): string {
  if (!Number.isFinite(price) || !Number.isFinite(reference) || reference <= 0) return "—";
  const rounded = Number(((price / reference - 1) * 100).toFixed(2));
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(2)}%`;
}

/** Logical ranges refer to the same complete candle array in every pane. */
export interface ChartRange { from: number; to: number }
export function historyViewport(count: number, range: ChartRange) {
  const first = Math.max(0, Math.ceil(range.from - 1e-6));
  const last = Math.min(count - 1, Math.floor(range.to + 1e-6));
  const size = Math.min(count, Math.max(1, last - first + 1));
  const max = Math.max(0, count - size);
  const start = Math.max(0, Math.min(max, first));
  return { size, max, start, end: Math.min(count - 1, start + size - 1) };
}
export function historyRange(count: number, start: number, size: number): ChartRange {
  const width = Math.min(count, Math.max(1, size));
  const offset = Math.max(0, Math.min(count - width, start));
  return { from: offset - 0.5, to: offset + width - 0.5 };
}
export function candleChange(closes: number[], index: number): {amount: number; percent: number} | null {
  const previous = closes[index - 1], current = closes[index];
  if (!Number.isFinite(previous) || previous <= 0 || !Number.isFinite(current)) return null;
  return { amount: current - previous, percent: (current / previous - 1) * 100 };
}

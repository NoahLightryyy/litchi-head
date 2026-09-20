export function parseRawDaily(value: unknown, symbol: string) {
  const x = value as Record<string, unknown>;
  if (!x || x.symbol !== symbol || x.source !== "tencent" || x.price_basis !== "raw" ||
      x.verification !== "single_source" || !Array.isArray(x.bars)) throw new Error("备用日线格式不兼容");
  if (x.status !== "success_data" || !x.bars.length) throw new Error("腾讯备用日线暂不可用");
  let previous = "";
  const bars = x.bars.map((item: Record<string, unknown>) => {
    const date = String(item.trade_date);
    const numbers = [item.open, item.high, item.low, item.close].map(v =>
      typeof v === "number" || (typeof v === "string" && v.trim()) ? Number(v) : NaN);
    const [open, high, low, close] = numbers;
    if (item.code !== symbol || item.price_basis !== "raw" || item.period !== "1d" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) || date <= previous ||
        numbers.some(v => !Number.isFinite(v) || v <= 0) || high < Math.max(open, close, low) || low > Math.min(open, close) ||
        typeof item.volume !== "number" || !Number.isSafeInteger(item.volume) || item.volume < 0) throw new Error("备用日线内容无效");
    previous = date;
    return {date, open, high, low, close, volume: item.volume};
  });
  if (x.data_start !== bars[0].date || x.data_end !== bars.at(-1)!.date) throw new Error("备用日线日期不一致");
  return {bars, start: bars[0].date, end: bars.at(-1)!.date};
}

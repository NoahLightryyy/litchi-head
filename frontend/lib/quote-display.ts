export function formatQuoteOptionalNumber(value: number | null, decimals: number, suffix: string, signed = false): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${signed && value > 0 ? "+" : ""}${value.toFixed(decimals)}${suffix}`;
}

export function formatQuoteTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

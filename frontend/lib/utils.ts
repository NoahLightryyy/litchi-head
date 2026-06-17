import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/* ── shadcn/ui 工具函数 ── */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/* ── 格式化 ── */

/** 价格格式：256.80 */
export function formatPrice(price: number): string {
  return price.toFixed(2);
}

/** 涨跌幅格式：+2.34% / -1.23% */
export function formatChangePct(pct: number): string {
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

/** 成交量格式：12.3万 / 1.2亿 */
export function formatVolume(volume: number): string {
  if (volume >= 1_0000_0000) {
    return `${(volume / 1_0000_0000).toFixed(1)}亿`;
  }
  if (volume >= 1_0000) {
    return `${(volume / 1_0000).toFixed(1)}万`;
  }
  return volume.toLocaleString();
}

/** 资金流向格式：+12.5亿 / -2.1亿 */
export function formatFundFlow(flow: number): string {
  return `${flow >= 0 ? "+" : ""}${flow.toFixed(1)}亿`;
}

/** 时间戳 → 可读日期 */
export function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** 缩写长字符串 */
export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "...";
}

/* ── 颜色 ── */

/** 涨跌颜色 */
export function changeColor(pct: number): string {
  if (pct > 0) return "text-accent-green";
  if (pct < 0) return "text-accent-red";
  return "text-text-secondary";
}

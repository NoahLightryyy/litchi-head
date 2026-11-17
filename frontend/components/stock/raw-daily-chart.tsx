"use client";
import type { SemanticZoom } from "@/lib/chart-zoom";
import { useRawDaily } from "@/lib/hooks/use-raw-daily";
import { aggregateRawPeriod, periodLabels, type DisplayPeriod } from "@/lib/raw-period";
import { CandlestickChart } from "./candlestick-chart";

export function RawDailyChart({code, zoom, period = "daily"}: {code:string; zoom?: SemanticZoom; period?: DisplayPeriod}) {
  const label = periodLabels[period];
  const days = period === "daily" ? 240 : 900;
  const query = useRawDaily(code, days);
  return <section className="space-y-3" aria-label={`腾讯备用不复权${label}`}>
    <div className="flex flex-wrap items-start gap-3 text-xs text-text-muted">
      <span className="rounded bg-bg-tertiary px-2 py-1">不复权</span>
      <span className="py-1">腾讯 · {period === "daily" ? "备用日线" : `日线聚合${label}`}</span>
      <details className="ml-auto max-w-lg py-1">
        <summary className="cursor-pointer text-accent-blue">数据说明</summary>
        <p className="mt-2 leading-relaxed">原前复权{label}当前不可用，使用腾讯历史日线。不复权保留当日实际成交价格，除权除息可能形成价格跳空；不与前复权序列拼接，仅展示已结束交易日。</p>
      </details>
    </div>
    {query.isPending ? <p role="status">正在获取备用{label}…</p> : query.isError ? <p role="alert">备用{label}也未取得有效数据，请稍后重试。</p> : <>
      <p className="text-xs text-text-muted">{query.data.start} — {query.data.end} · {query.data.bars.length} 根日线</p>
      {period !== "daily" && <p className="text-xs text-text-muted">按已取得日线聚合为 {aggregateRawPeriod(query.data.bars, period).length} 根{label}；首尾周期可能不完整，交易日覆盖尚未核验，不含今日行情。</p>}
      <CandlestickChart data={aggregateRawPeriod(query.data.bars, period)} zoom={zoom} />
    </>}
    <button disabled={query.isFetching} className="text-sm text-accent-blue" onClick={() => void query.refetch()}>刷新备用{label}</button>
  </section>;
}

"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { requireEtfKline, type EtfKline } from "@/lib/etf-kline";
import { aggregateRawPeriod, periodLabels, type DisplayPeriod } from "@/lib/raw-period";
import { CandlestickChart } from "@/components/stock/candlestick-chart";

const sources = { tencent: "腾讯", sina: "新浪" };
export function EtfKlineContent({ data, pending, failed, paused, error, period }: {
  data?: EtfKline; pending: boolean; failed: boolean; paused: boolean; error?: string; period: DisplayPeriod;
}) {
  const bars = useMemo(() => data ? aggregateRawPeriod(data.bars, period) : [], [data, period]);
  const available = data?.status === "ready" && bars.length > 0;
  return <div className="space-y-3">
    {paused ? <p role="status" className="text-sm text-text-muted">当前离线。{available ? "保留上次取得的历史行情。" : "联网后可重试。"}</p>
      : pending ? <p role="status" className="py-6 text-sm text-text-muted">正在读取 ETF 历史行情…</p>
      : failed && <p role="alert" className="text-sm">{error || "ETF K线读取失败，请重试。"}{available && "下方保留上次成功的图表，行情日期未更新。"}</p>}
    {data?.status === "empty" && !failed && <p role="status" className="py-4 text-sm text-text-muted">所选区间暂无 ETF 日线，新上市基金可能尚无已结束交易日数据。</p>}
    {available && <>
      <p className="text-xs text-text-muted">{sources[data.source!]} · 不复权 · 成交量单位：份 · {data.data_start} — {data.data_end} · {bars.length} 根{periodLabels[period]}</p>
      <p className="text-xs text-text-muted">展示场内交易价格，非基金净值；不含今日行情。{period !== "daily" && "周线／月线由已取得日线聚合，首尾周期可能不完整。"}</p>
      <CandlestickChart data={bars} pricePrecision={3} priceUnit="元" volumeLabel="成交量（份）" />
    </>}
    {data && <details className="text-xs leading-6 text-text-muted">
      <summary className="cursor-pointer">K线来源与统计口径</summary>
      <div className="mt-2 space-y-1">
        <p>请求区间：{data.requested_start} — {data.requested_end}；采集时间：{new Date(data.fetched_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}（北京时间）。</p>
        {data.limitations.map((item, index) => <p key={index}>{item}</p>)}
        {data.diagnostics.map((item, index) => <p key={`${item.source}:${index}`}>{sources[item.source]}：{{ success: "可用", empty: "暂无数据", failed: "调用失败" }[item.status]}{item.error_code ? `（${item.error_code}）` : ""}</p>)}
      </div>
    </details>}
  </div>;
}

export function EtfKlinePanel({ code }: { code: string }) {
  const [period, setPeriod] = useState<DisplayPeriod>("daily");
  const query = useQuery({
    queryKey: ["etf", code, "kline", 730], retry: false, staleTime: 300_000,
    queryFn: async ({ signal }) => requireEtfKline(await api.getRaw<unknown>(`/etfs/${code}/kline`, { days: "730" },
      { signal: AbortSignal.any([signal, AbortSignal.timeout(22_000)]) }), code),
  });
  return <section aria-label="ETF K线" className="rounded-xl border border-bg-tertiary bg-bg-secondary p-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="font-semibold">ETF K线</h2>
      <div className="flex items-center gap-3">
        <div className="flex gap-1 rounded-md bg-bg-tertiary p-0.5">{(["daily", "weekly", "monthly"] as const).map(value => <button key={value} type="button" aria-pressed={period === value} onClick={() => setPeriod(value)} className={`rounded px-3 py-1 text-xs ${period === value ? "bg-accent-blue text-white" : "text-text-secondary"}`}>{periodLabels[value]}</button>)}</div>
        <button type="button" disabled={query.isFetching || query.isPaused} onClick={() => void query.refetch()} className="text-sm text-accent-blue disabled:opacity-50">{query.isFetching ? "正在读取…" : "刷新K线"}</button>
      </div>
    </div>
    <EtfKlineContent data={query.data} pending={query.isPending} failed={query.isError} paused={query.isPaused} error={query.error?.message} period={period} />
  </section>;
}

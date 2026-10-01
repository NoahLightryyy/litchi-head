"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { parseFiveDay } from "@/lib/five-day-display";
import type { SemanticZoom } from "@/lib/chart-zoom";
import { IntradayLineChart } from "./intraday-line-chart";

export function FiveDayChart({code, zoom}: {code: string; zoom: SemanticZoom}) {
  const query = useQuery({queryKey: ["stocks", code, "five-day-display"],
    queryFn: async ({signal}) => parseFiveDay(await api.getRaw(`/stocks/${code}/intraday-five-day-display`, undefined,
      {signal: AbortSignal.any([signal, AbortSignal.timeout(15000)])}), code),
    retry: false, staleTime: 30000});
  const data = query.data;
  return <div className="space-y-3">
    <div className="flex flex-wrap justify-between gap-2 text-xs text-text-muted"><span>五日分时 · 腾讯 · 未复权核验</span>
      <button className="text-accent-blue" disabled={query.isFetching} onClick={() => void query.refetch()}>刷新五日分时</button></div>
    {query.isPending && <p role="status" className="h-72 flex items-center justify-center">正在获取五日分钟走势…</p>}
    {(query.isError || data?.status === "failed") && <p role="alert" className="p-6 border border-accent-red/30 rounded">五日分钟数据暂不可用，可点击刷新重试，或切换日 K。</p>}
    {data?.status === "empty" && <p role="status" className="p-6">来源没有返回五日分钟记录。</p>}
    {data?.status === "partial" && <>
      <p className="text-xs text-text-muted">{data.days[0]} — {data.days.at(-1)} · 实际 {data.days.length} 个交易日 · {data.points.length} 个分钟点</p>
      {(data.days.length < 5 || data.incomplete_days.length > 0 || data.missing_days.length > 0) &&
        <p role="status" className="text-xs text-accent-gold">来源记录不完整：{data.days.length < 5 ? `仅返回 ${data.days.length} 日；` : ""}{data.incomplete_days.length ? `分钟不完整 ${data.incomplete_days.join("、")}；` : ""}{data.missing_days.length ? `缺交易日 ${data.missing_days.join("、")}` : ""}只画已返回的点。</p>}
      <IntradayLineChart points={data.points} multiDay zoom={zoom} />
      <p className="text-xs text-text-muted">日期标记分隔交易日；休市时间压缩，跨日连线仅连接端点，不代表夜间成交。单源价格尚未交叉验证。</p>
    </>}
  </div>;
}
